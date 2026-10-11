# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Chat session/message CRUD plus the streaming reply pipeline: persist the
# user's message, retrieve+rerank relevant chunks (Phase 4's
# retrieval_service), assemble a prompt from system instructions + short-term
# memory + retrieved context, stream the LLM's answer token-by-token, then
# persist the assistant's message with citations.
#
# stream_reply is a generator, not a plain function: FastAPI closes a
# request-scoped `Depends(get_db)` session as soon as the endpoint returns
# the StreamingResponse, before the generator has produced a single token —
# so this takes a session_factory and manages its own DB session lifecycle
# for the duration of the stream (see app/deps.py:get_session_factory).

import json
import logging
import time
from collections.abc import Callable, Generator, Iterator
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import MemoryEnqueuer, SessionFactory
from app.memory import short_term
from app.memory.long_term_base import MemoryRepository
from app.models.chat_message import ChatMessage, ChatMessageRole
from app.models.chat_session import ChatSession
from app.models.user import User
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider, ToolCallRequest
from app.providers.reranker.base import Reranker
from app.providers.websearch.base import WebSearchProvider, WebSearchResponse, WebSearchResult
from app.repositories import chat_repository, document_repository, user_repository
from app.services.retrieval_service import ContextItem, retrieve_context
from app.vectorstore.base import VectorRepository

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TITLE = "New conversation"
_AUTO_TITLE_MAX_LENGTH = 60

_SYSTEM_PROMPT_NO_CONTEXT = (
    "You are a helpful assistant. Today's date is {today}. No relevant "
    "documents were found for this question — answer from general knowledge "
    "if you reasonably can, and say plainly that you found nothing in the "
    "user's documents if you can't."
)
_SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful assistant answering questions using the user's own "
    "documents and, where relevant, your memory of earlier conversations with "
    "them. Today's date is {today}. Use the numbered sources below when "
    "they're relevant, citing them inline like [1] or [2]. If the sources "
    "don't contain the answer, say so rather than guessing."
    "{tools_note}\n\nSources:\n{context}"
)
# Explicit and unambiguous on purpose, not "use when appropriate": a model
# with a training cutoff has no way to tell, on its own, that a query like
# "today's cricket match" is asking about something after that cutoff — it
# will confidently answer from a real memorized event and just be wrong
# about which day it happened (confirmed in production: gpt-4o-mini
# answered a same-day India vs West Indies ODI question with a real Oct
# 2023 match's stats, relabeled as "today"). Pairing this with {today} above
# gives it the date anchor needed to actually notice the mismatch.
_WEB_SEARCH_NOTE = (
    " Your own knowledge has a training cutoff and cannot be trusted for "
    "anything that could have changed since then — live scores and match "
    "results, current news, prices, schedules, or anything else tied to "
    "'today' or 'now'. For a question like that, you MUST call the "
    "web_search tool rather than answering from memory, even if you recall "
    "something that looks relevant — treat that recollection as probably "
    "outdated or about the wrong date entirely, not as an answer."
)
# The initial retrieval above already ran once, automatically, against the
# user's raw message — this tool is for when that one shot wasn't enough:
# a follow-up question, a more specific or differently-worded query than the
# original message, or the initial retrieval simply missing something. Kept
# additive (auto-retrieval still always runs) rather than replacing
# auto-retrieval outright, so a document question that never triggers this
# tool still gets its context exactly as before.
_SEARCH_DOCUMENTS_NOTE = (
    " You also have a search_documents tool to search the user's own "
    "documents again with a different or more specific query, if the sources "
    "above don't fully answer the question — useful for follow-up questions "
    "or when the initial search missed something relevant."
)

# OpenAI function-calling schemas (see providers/llm/base.py's ToolCallRequest
# and openai_provider.py's stream_chat). web_search is only offered when a
# WebSearchProvider is actually configured (see providers/websearch/factory.py);
# search_documents is always offered — retrieval is core to this app, not an
# optional integration — chat works fine without either, the model just
# never sees the missing one.
_WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the public web. Use this for questions the sources above "
            "don't cover — current events, external/general knowledge, or "
            "anything outside the user's own documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query."}},
            "required": ["query"],
        },
    },
}
_SEARCH_DOCUMENTS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the user's own documents again with a new query. Use this "
            "for a follow-up question, or when the sources already provided "
            "don't fully cover what's being asked and a more specific or "
            "differently-worded search might find it."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query."}},
            "required": ["query"],
        },
    },
}

# Citation grounding (see chat_service._ground_citations): forced via
# tool_choice on a separate, non-streaming call made *after* the answer is
# already fully streamed — not offered to the model during normal answering.
# Structured output (a list of integers) rather than parsing the model's own
# inline [1]/[2] markers out of free text: the model can't format those
# inconsistently or skip them, and a source it never mentions can't slip
# through as a citation just because it was retrieved/searched.
_CITE_SOURCES_TOOL = {
    "type": "function",
    "function": {
        "name": "cite_sources",
        "description": (
            "Report which of the numbered sources were actually used to write "
            "the given answer. Omit any source that was merely available but "
            "not actually drawn on."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "used_source_numbers": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "The numbers (e.g. 1, 2) of sources actually used. "
                        "Empty array if the answer didn't draw on any of them."
                    ),
                }
            },
            "required": ["used_source_numbers"],
        },
    },
}


class ChatServiceError(Exception):
    pass


class ChatSessionNotFoundError(ChatServiceError):
    pass


def _get_owned_session_or_raise(db: Session, current_user: User, session_id: int) -> ChatSession:
    session = chat_repository.get_session_by_id(db, session_id)
    if session is None or session.user_id != current_user.id:
        raise ChatSessionNotFoundError(f"Chat session {session_id} not found")
    return session


def create_session(db: Session, *, current_user: User, title: str | None) -> ChatSession:
    return chat_repository.create_session(
        db, user_id=current_user.id, title=title or DEFAULT_SESSION_TITLE
    )


def list_sessions(
    db: Session, current_user: User, *, limit: int | None = None, offset: int = 0
) -> list[ChatSession]:
    return chat_repository.list_sessions_for_user(db, current_user.id, limit=limit, offset=offset)


def count_sessions(db: Session, current_user: User) -> int:
    return chat_repository.count_sessions_for_user(db, current_user.id)


def get_session(db: Session, current_user: User, session_id: int) -> ChatSession:
    return _get_owned_session_or_raise(db, current_user, session_id)


def delete_session(
    db: Session, current_user: User, session_id: int, *, memory_repository: MemoryRepository
) -> None:
    session = _get_owned_session_or_raise(db, current_user, session_id)
    chat_repository.delete_session(db, session)
    short_term.clear_session(session_id)
    memory_repository.delete_summary(session_id)


def list_messages(
    db: Session,
    current_user: User,
    session_id: int,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[ChatMessage]:
    _get_owned_session_or_raise(db, current_user, session_id)
    return chat_repository.list_messages(db, session_id, limit=limit, offset=offset)


def count_messages(db: Session, current_user: User, session_id: int) -> int:
    _get_owned_session_or_raise(db, current_user, session_id)
    return chat_repository.count_messages(db, session_id)


def _recent_turns(db: Session, session_id: int) -> list[dict[str, str]]:
    max_turns = settings.SHORT_TERM_MEMORY_TURNS
    cached = short_term.get_buffered_turns(session_id, max_turns=max_turns)
    if cached is not None:
        return cached

    messages = chat_repository.list_recent_messages(db, session_id, limit=max_turns)
    turns = [{"role": message.role.value, "content": message.content} for message in messages]
    short_term.replace_buffer(session_id, turns, max_turns=max_turns)
    return turns


def _location_label(metadata: dict) -> str | None:
    if "page" in metadata:
        label = f"page {metadata['page']}"
    elif "slide" in metadata:
        label = f"slide {metadata['slide']}"
    elif "sheet" in metadata:
        label = f"sheet '{metadata['sheet']}'"
    elif "heading" in metadata and metadata["heading"]:
        label = f"section '{metadata['heading']}'"
    elif "folder" in metadata:
        label = f"folder '{metadata['folder']}'"
    elif "path" in metadata:
        label = f"element {metadata['path']}"
    else:
        return None

    kind = metadata.get("kind")
    if kind and kind not in ("text", "sheet", "body"):
        label += f" ({kind})"
    return label


def _label_context_item(item: ContextItem, index: int) -> str:
    if item.source == "memory":
        prefix = "from your chat history"
    else:
        location = _location_label(item.metadata)
        prefix = f"from a document, {location}" if location else "from a document"
    return f"[{index + 1}] ({prefix}) {item.content}"


def _build_system_prompt(items: list[ContextItem], *, tools_note: str) -> str:
    # The model's own training data has no notion of "today" — without this,
    # it can't tell a live/current-events question apart from one its
    # training already answered, and will confidently answer from a stale
    # memorized event instead of recognizing it needs to search. See
    # _WEB_SEARCH_NOTE's comment for the production case this fixed.
    today = date.today().isoformat()
    if not items:
        return _SYSTEM_PROMPT_NO_CONTEXT.format(today=today) + tools_note

    context = "\n\n".join(_label_context_item(item, index) for index, item in enumerate(items))
    return _SYSTEM_PROMPT_TEMPLATE.format(today=today, tools_note=tools_note, context=context)


def _format_web_results(response: WebSearchResponse) -> str:
    parts = []
    # The synthesized answer goes first and labeled plainly — see
    # WebSearchResponse.answer's docstring for why this isn't redundant
    # with the raw results below (it fixed a real production case where the
    # model ignored generic/historical snippets and answered from stale
    # training knowledge instead).
    if response.answer:
        parts.append(f"Direct answer: {response.answer}")
    if response.results:
        parts.append(
            "\n\n".join(
                f"[{i + 1}] {r.title}\n{r.url}\n{r.content}"
                for i, r in enumerate(response.results)
            )
        )
    return "\n\n".join(parts) if parts else "No web results found."


def _format_document_results(items: list[ContextItem]) -> str:
    if not items:
        return "No matching document passages found."
    return "\n\n".join(_label_context_item(item, index) for index, item in enumerate(items))


def _citations_for(db: Session, items: list[ContextItem]) -> list[dict]:
    # Resolve titles in one batch query rather than per-citation, then title
    # each document citation so the UI can show "Q3 Report.pdf" instead of a
    # raw "doc #9" — the ID alone means nothing to a user reading a citation.
    document_ids = {item.document_id for item in items if item.source == "document"}
    titles = {doc.id: doc.title for doc in document_repository.get_by_ids(db, list(document_ids))}

    citations = []
    for item in items:
        if item.source == "memory":
            citations.append({"source": "memory", "session_id": item.session_id})
        else:
            citations.append(
                {
                    "source": "document",
                    "document_id": item.document_id,
                    "document_title": titles.get(item.document_id),
                    "document_version_id": item.document_version_id,
                    "chunk_index": item.chunk_index,
                    "metadata": item.metadata,
                }
            )
    return citations


_GROUNDING_SYSTEM_PROMPT = (
    "You are grounding-checking an answer that was already written. Given the "
    "answer and the numbered sources below (which the writer had available, "
    "not necessarily all used), call cite_sources with the numbers of "
    "sources the answer actually draws on. Leave out any source that was "
    "merely available but not actually used. If the answer doesn't draw on "
    "any of them (e.g. it's a general-knowledge or off-topic reply), call it "
    "with an empty list.\n\nSources:\n{sources}"
)


def _build_grounding_sources(context_items: list[ContextItem], web_results: list[WebSearchResult]) -> str:
    # Same order as `_citations_for(...) + web_citations` in stream_reply, so
    # source number N here is exactly citations[N-1] there — that's what
    # lets _ground_citations turn "used_source_numbers" straight into a
    # citations-list filter with no extra bookkeeping. A fresh numbering
    # made just for this grounding call, independent of whatever numbering
    # the model saw earlier in the conversation (system prompt sources,
    # each tool result's own [1..]) — the model doesn't need to remember
    # that; it's re-reading its own answer against a fresh source list.
    lines = [f"[{i + 1}] {item.content[:500]}" for i, item in enumerate(context_items)]
    offset = len(context_items)
    lines.extend(
        f"[{offset + i + 1}] {r.title}: {r.content[:500]}" for i, r in enumerate(web_results)
    )
    return "\n\n".join(lines)


def _ground_citations(
    llm_provider: LLMProvider,
    *,
    answer: str,
    context_items: list[ContextItem],
    web_results: list[WebSearchResult],
    citations: list[dict],
    session_id: int,
) -> list[dict]:
    """Filters `citations` down to the ones the model reports it actually
    used, via a forced cite_sources tool call — rather than trusting that
    every retrieved/searched source ended up grounding the answer. Degrades
    to returning `citations` unfiltered (the old behavior) on any failure —
    a broken grounding check should never break the turn or hide an answer
    the user already got."""
    if not citations or not settings.CHAT_GROUNDING_ENABLED:
        return citations

    messages = [
        {
            "role": "system",
            "content": _GROUNDING_SYSTEM_PROMPT.format(
                sources=_build_grounding_sources(context_items, web_results)
            ),
        },
        {"role": "user", "content": f"Answer to check:\n{answer}"},
    ]
    try:
        call = llm_provider.request_tool_call(messages, _CITE_SOURCES_TOOL)
    except Exception:
        logger.warning("Citation grounding call failed for chat session=%s", session_id, exc_info=True)
        return citations
    if call is None:
        return citations

    try:
        used_numbers = json.loads(call.arguments or "{}").get("used_source_numbers", [])
        used_indices = {n - 1 for n in used_numbers if isinstance(n, int)}
    except Exception:
        logger.warning(
            "Citation grounding returned unparseable arguments for chat session=%s: %r",
            session_id,
            call.arguments,
        )
        return citations

    return [citation for i, citation in enumerate(citations) if i in used_indices]


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _title_from_message(content: str) -> str:
    # Sessions start out titled DEFAULT_SESSION_TITLE; the first real user
    # message replaces that placeholder so the sidebar shows what the
    # conversation is actually about, matching ChatGPT-style auto-titling.
    collapsed = " ".join(content.split())
    if len(collapsed) <= _AUTO_TITLE_MAX_LENGTH:
        return collapsed
    return collapsed[:_AUTO_TITLE_MAX_LENGTH].rstrip() + "…"


def _run_llm_stream(
    llm_provider: LLMProvider, messages: list[dict], tools: list[dict] | None
) -> Generator[str, None, tuple[str, list[ToolCallRequest] | None]]:
    """Runs one streaming LLM call: yields SSE token events for any content
    produced, then returns (content, tool_calls) — tool_calls is None unless
    the model called a tool instead of (or before) answering. A plain
    `return` inside a generator becomes the value `yield from` captures at
    the call site, which is how stream_reply gets both without buffering
    the whole response first."""
    content = ""
    tool_calls: list[ToolCallRequest] | None = None
    for delta in llm_provider.stream_chat(messages, tools=tools):
        if isinstance(delta, list):
            tool_calls = delta
        else:
            content += delta
            yield _sse_event({"type": "token", "content": delta})
    return content, tool_calls


def _execute_tool_calls(
    tool_calls: list[ToolCallRequest],
    *,
    web_search_provider: WebSearchProvider | None,
    current_user: User,
    embedding_provider: EmbeddingProvider,
    vector_repository_factory: Callable[[], VectorRepository],
    reranker: Reranker,
    fallback_query: str,
    session_id: int,
) -> tuple[list[dict], list[dict], list[ContextItem], list[WebSearchResult]]:
    """Runs each requested tool call and returns (tool_messages, web_citations,
    doc_context_items, web_results) — tool_messages are appended to the
    conversation as-is, one per call, so the next LLM call can see what each
    tool returned. doc_context_items/web_results are folded into the turn's
    citations and (see _ground_citations) into the grounding-check prompt,
    which needs the actual snippet text, not just the citation dict's
    title/url/document_id."""
    tool_messages: list[dict] = []
    web_citations: list[dict] = []
    doc_context_items: list[ContextItem] = []
    web_results: list[WebSearchResult] = []
    for call in tool_calls:
        if call.name == "web_search" and web_search_provider is not None:
            response = WebSearchResponse()
            try:
                query = json.loads(call.arguments or "{}").get("query", fallback_query)
                response = web_search_provider.search(
                    query, max_results=settings.WEB_SEARCH_MAX_RESULTS
                )
            except Exception:
                logger.warning(
                    "web_search tool call failed for chat session=%s", session_id, exc_info=True
                )
            web_citations.extend(
                {"source": "web", "url": r.url, "title": r.title} for r in response.results
            )
            web_results.extend(response.results)
            tool_messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": _format_web_results(response)}
            )
        elif call.name == "search_documents":
            items: list[ContextItem] = []
            try:
                query = json.loads(call.arguments or "{}").get("query", fallback_query)
                items = retrieve_context(
                    current_user=current_user,
                    query=query,
                    embedding_provider=embedding_provider,
                    vector_repository=vector_repository_factory(),
                    reranker=reranker,
                    top_k=settings.CHAT_RETRIEVAL_TOP_K,
                    candidate_limit=settings.CHAT_RETRIEVAL_CANDIDATE_LIMIT,
                    alpha=settings.CHAT_RETRIEVAL_ALPHA,
                )
            except Exception:
                logger.warning(
                    "search_documents tool call failed for chat session=%s",
                    session_id,
                    exc_info=True,
                )
            doc_context_items.extend(items)
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": _format_document_results(items),
                }
            )
        else:
            # Model requested a tool that isn't offered/available this turn
            # (e.g. web_search with no provider configured) — a result is
            # still required per tool_call_id or the next LLM call errors.
            tool_messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": "Tool unavailable."}
            )
    return tool_messages, web_citations, doc_context_items, web_results


def stream_reply(
    *,
    session_factory: SessionFactory,
    session_id: int,
    current_user_id: int,
    content: str,
    embedding_provider: EmbeddingProvider,
    vector_repository_factory: Callable[[], VectorRepository],
    reranker: Reranker,
    llm_provider: LLMProvider,
    web_search_provider: WebSearchProvider | None,
    memory_enqueuer: MemoryEnqueuer,
) -> Iterator[str]:
    db = session_factory()
    try:
        current_user = user_repository.get_by_id(db, current_user_id)
        session = chat_repository.get_session_by_id(db, session_id)
        if current_user is None or session is None or session.user_id != current_user.id:
            yield _sse_event({"type": "error", "message": "Chat session not found"})
            return

        start_time = time.monotonic()
        chat_repository.add_message(db, session=session, role=ChatMessageRole.USER, content=content)
        if session.title == DEFAULT_SESSION_TITLE:
            chat_repository.set_title(db, session, _title_from_message(content))
        short_term.append_turn(
            session_id, role="user", content=content, max_turns=settings.SHORT_TERM_MEMORY_TURNS
        )

        retrieval_start = time.monotonic()
        try:
            # vector_repository_factory() is called *inside* this try, not
            # resolved by FastAPI's Depends() before this function even
            # starts — a Weaviate connection failure needs to degrade the
            # same way a search failure already does below, not 500 the
            # whole request before this fallback ever gets a chance to run.
            context_items = retrieve_context(
                current_user=current_user,
                query=content,
                embedding_provider=embedding_provider,
                vector_repository=vector_repository_factory(),
                reranker=reranker,
                top_k=settings.CHAT_RETRIEVAL_TOP_K,
                candidate_limit=settings.CHAT_RETRIEVAL_CANDIDATE_LIMIT,
                alpha=settings.CHAT_RETRIEVAL_ALPHA,
            )
            logger.info(
                "Chat session=%s: retrieval took %.3fs (%d context items) — see"
                " app.services.retrieval_service logs at DEBUG for the embed/"
                "search/rerank breakdown",
                session_id,
                time.monotonic() - retrieval_start,
                len(context_items),
            )
        except Exception:
            logger.warning(
                "Retrieval failed for chat session=%s after %.3fs; answering with no context",
                session_id,
                time.monotonic() - retrieval_start,
                exc_info=True,
            )
            context_items = []

        # search_documents is always offered (retrieval is core to this app);
        # web_search only when a provider is actually configured.
        tools: list[dict] = [_SEARCH_DOCUMENTS_TOOL]
        tools_note = _SEARCH_DOCUMENTS_NOTE
        if web_search_provider is not None:
            tools.append(_WEB_SEARCH_TOOL)
            tools_note += _WEB_SEARCH_NOTE
        messages = [
            {"role": "system", "content": _build_system_prompt(context_items, tools_note=tools_note)}
        ]
        messages.extend(_recent_turns(db, session_id))

        # Agent loop: each hop lets the model call a tool, see the result, and
        # either call another tool or answer. Bounded by CHAT_MAX_TOOL_HOPS —
        # once that many rounds have happened, tools=None forces a final
        # answer from whatever's been gathered so far, so a model that keeps
        # requesting searches can't loop forever.
        web_citations: list[dict] = []
        web_results: list[WebSearchResult] = []
        # dict, not set: needs to preserve first-called order for a
        # readable "tools used" display, but still de-duplicate a tool
        # called across multiple hops.
        tools_used: dict[str, None] = {}
        hop = 0
        while True:
            force_final = hop >= settings.CHAT_MAX_TOOL_HOPS
            try:
                full_response, tool_calls = yield from _run_llm_stream(
                    llm_provider, messages, None if force_final else tools
                )
            except Exception as exc:
                logger.warning(
                    "LLM streaming failed for chat session=%s (hop %d)",
                    session_id,
                    hop,
                    exc_info=True,
                )
                yield _sse_event({"type": "error", "message": f"Answer generation failed: {exc}"})
                return

            # force_final also breaks the loop unconditionally, not just when
            # tool_calls is empty — a real OpenAI call with tools=None never
            # returns tool_calls, but this guards against a provider that
            # ignores that and would otherwise loop forever past the cap.
            if not tool_calls or force_final:
                break

            for call in tool_calls:
                tools_used[call.name] = None
            called_names = {call.name for call in tool_calls}
            if called_names == {"search_documents"}:
                status_message = "Searching your documents…"
            elif called_names == {"web_search"}:
                status_message = "Searching the web…"
            else:
                status_message = "Searching…"
            yield _sse_event({"type": "status", "message": status_message})
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": call.arguments},
                        }
                        for call in tool_calls
                    ],
                }
            )
            tool_messages, hop_citations, doc_items, hop_web_results = _execute_tool_calls(
                tool_calls,
                web_search_provider=web_search_provider,
                current_user=current_user,
                embedding_provider=embedding_provider,
                vector_repository_factory=vector_repository_factory,
                reranker=reranker,
                fallback_query=content,
                session_id=session_id,
            )
            messages.extend(tool_messages)
            web_citations.extend(hop_citations)
            web_results.extend(hop_web_results)
            context_items = context_items + doc_items
            hop += 1

        citations = _citations_for(db, context_items) + web_citations
        citations_before_grounding = len(citations)
        citations = _ground_citations(
            llm_provider,
            answer=full_response,
            context_items=context_items,
            web_results=web_results,
            citations=citations,
            session_id=session_id,
        )

        # Computed after grounding, not before: the grounding call is a real
        # extra round-trip blocking the "done" event, so it belongs in the
        # duration the user sees, not hidden inside it.
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("Chat session=%s: full turn took %dms end to end", session_id, duration_ms)

        # Tool-selection telemetry: one structured line per turn (queryable
        # via LOG_FORMAT=json — see app.core.logging) covering which tools
        # actually fired, how many hops that took, and what grounding did to
        # the citations list. Not tied to any one tool's success/failure
        # path above (those already log their own warnings) — this is the
        # turn-level summary for tuning the system prompt and gauging how
        # often each tool actually gets used.
        logger.info(
            "Chat session=%s: tool selection — tools_used=%s hops=%d citations=%d->%d",
            session_id,
            list(tools_used),
            hop,
            citations_before_grounding,
            len(citations),
            extra={
                "event": "chat_tool_selection",
                "session_id": session_id,
                "tools_used": list(tools_used),
                "tool_hops": hop,
                "web_search_offered": web_search_provider is not None,
                "citations_before_grounding": citations_before_grounding,
                "citations_after_grounding": len(citations),
                "grounding_enabled": settings.CHAT_GROUNDING_ENABLED,
                "duration_ms": duration_ms,
            },
        )

        assistant_message = chat_repository.add_message(
            db,
            session=session,
            role=ChatMessageRole.ASSISTANT,
            content=full_response,
            citations=citations,
            duration_ms=duration_ms,
            tools_used=list(tools_used) or None,
        )
        short_term.append_turn(
            session_id,
            role="assistant",
            content=full_response,
            max_turns=settings.SHORT_TERM_MEMORY_TURNS,
        )

        # Long-term memory: once a session has more messages than the
        # short-term buffer keeps, some have fallen out of that window and
        # are worth folding into the rolling summary. memory_service itself
        # re-checks this and no-ops if there's nothing new to summarize, so
        # it's safe (if slightly wasteful) to enqueue on every turn past the
        # threshold rather than tracking a "did we already trigger" flag.
        message_count = chat_repository.count_messages(db, session_id)
        if message_count > settings.SHORT_TERM_MEMORY_TURNS:
            memory_enqueuer(session_id)

        yield _sse_event(
            {
                "type": "done",
                "message_id": assistant_message.id,
                "citations": citations,
                "duration_ms": duration_ms,
                "tools_used": list(tools_used) or None,
            }
        )
    finally:
        db.close()
