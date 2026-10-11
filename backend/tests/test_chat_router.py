# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Integration tests for chat session CRUD + the SSE streaming reply
# endpoint, through the real API with fakes (LLM/embeddings/vector
# store/reranker) standing in for live services.

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.deps import get_vector_repository_factory
from app.main import app
from app.providers.llm.base import ToolCallRequest
from app.providers.websearch.base import WebSearchResult
from app.providers.websearch.factory import get_web_search_provider
from tests.fakes import FakeLLMProvider, FakeMemoryRepository, FakeWebSearchProvider
from tests.test_documents import _auth_header, _upload


def _create_session(client: TestClient, tokens: dict, *, title: str | None = None) -> dict:
    return client.post(
        "/api/v1/chat/sessions", json={"title": title}, headers=_auth_header(tokens)
    ).json()


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def test_create_session_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/chat/sessions", json={"title": "Hi"})

    assert response.status_code == 401


def test_create_and_list_sessions(client: TestClient, user_tokens: dict) -> None:
    _create_session(client, user_tokens, title="First")

    response = client.get("/api/v1/chat/sessions", headers=_auth_header(user_tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "First"


def test_create_session_defaults_title_when_omitted(client: TestClient, user_tokens: dict) -> None:
    session = _create_session(client, user_tokens)

    assert session["title"] == "New conversation"


def test_user_cannot_see_another_users_session(
    client: TestClient, user_tokens: dict, admin_tokens: dict
) -> None:
    session = _create_session(client, admin_tokens, title="Admin's")

    response = client.get(
        f"/api/v1/chat/sessions/{session['id']}/messages", headers=_auth_header(user_tokens)
    )

    assert response.status_code == 404


def test_list_sessions_reports_total_count_and_respects_limit(
    client: TestClient, user_tokens: dict
) -> None:
    for title in ("First", "Second", "Third"):
        _create_session(client, user_tokens, title=title)

    response = client.get("/api/v1/chat/sessions?limit=2", headers=_auth_header(user_tokens))

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["X-Total-Count"] == "3"


def test_delete_session(client: TestClient, user_tokens: dict) -> None:
    session = _create_session(client, user_tokens, title="To delete")

    delete_response = client.delete(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth_header(user_tokens)
    )
    get_response = client.get(
        f"/api/v1/chat/sessions/{session['id']}/messages", headers=_auth_header(user_tokens)
    )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_delete_session_cleans_up_memory_summary(
    client: TestClient, user_tokens: dict, fake_memory_repository: FakeMemoryRepository
) -> None:
    session = _create_session(client, user_tokens, title="To delete")
    fake_memory_repository.upsert_summary(
        user_id=1,
        session_id=session["id"],
        summary_text="Some summary",
        vector=[0.1],
        covers_up_to_message_id=1,
    )

    client.delete(f"/api/v1/chat/sessions/{session['id']}", headers=_auth_header(user_tokens))

    assert fake_memory_repository.get_summary(session["id"]) is None


def test_send_message_streams_tokens_and_persists_history(
    client: TestClient, user_tokens: dict, fake_llm_provider: FakeLLMProvider
) -> None:
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Hello there"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]
    assert len(token_events) == len(fake_llm_provider.reply.split(" "))
    assert "".join(e["content"] for e in token_events) == fake_llm_provider.reply + " "
    assert len(done_events) == 1
    assert done_events[0]["citations"] == []

    history = client.get(
        f"/api/v1/chat/sessions/{session['id']}/messages", headers=_auth_header(user_tokens)
    ).json()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello there"


def test_send_message_degrades_gracefully_when_vector_store_is_unreachable(
    client: TestClient, user_tokens: dict, fake_llm_provider: FakeLLMProvider
) -> None:
    # A dead Weaviate connection must not 500 the whole chat request — the
    # vector repository factory is invoked lazily, inside stream_reply's own
    # try/except, specifically so this degrades to a no-context answer the
    # same way a failed *search* already did before this fix.
    def _broken_factory():
        raise RuntimeError("Weaviate unreachable")

    app.dependency_overrides[get_vector_repository_factory] = lambda: _broken_factory
    try:
        session = _create_session(client, user_tokens, title="Chat")

        response = client.post(
            f"/api/v1/chat/sessions/{session['id']}/messages",
            json={"content": "Hello there"},
            headers=_auth_header(user_tokens),
        )
    finally:
        del app.dependency_overrides[get_vector_repository_factory]

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["citations"] == []


def test_send_message_to_missing_session_returns_404(client: TestClient, user_tokens: dict) -> None:
    response = client.post(
        "/api/v1/chat/sessions/999/messages",
        json={"content": "Hello"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 404


def test_send_message_includes_citations_from_own_documents(
    client: TestClient, user_tokens: dict
) -> None:
    _upload(
        client,
        user_tokens,
        title="Vacation Policy",
        content=b"Employees get 20 days of paid vacation per year",
    )
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "paid vacation days per year"},
        headers=_auth_header(user_tokens),
    )

    events = _parse_sse_events(response.text)
    done_event = next(e for e in events if e["type"] == "done")
    assert len(done_event["citations"]) == 1
    assert done_event["citations"][0]["document_id"] is not None
    assert done_event["citations"][0]["document_title"] == "Vacation Policy"

    history = client.get(
        f"/api/v1/chat/sessions/{session['id']}/messages", headers=_auth_header(user_tokens)
    ).json()
    assistant_message = history[1]
    assert "citations_json" not in assistant_message
    assert len(assistant_message["citations"]) == 1
    assert assistant_message["citations"][0]["document_id"] is not None
    assert assistant_message["citations"][0]["document_title"] == "Vacation Policy"


def test_citation_grounding_filters_to_sources_the_model_reports_using(
    client: TestClient, user_tokens: dict, fake_llm_provider: FakeLLMProvider
) -> None:
    _upload(
        client, user_tokens, title="Vacation Policy", content=b"Employees get 20 days of vacation"
    )
    _upload(
        client, user_tokens, title="Sick Leave Policy", content=b"Employees get 10 days of sick leave"
    )
    # Both documents get retrieved as candidates (2 citations pre-grounding),
    # but the grounding call reports only source 1 was actually used —
    # proves the forced cite_sources call, not just "return everything
    # retrieved", is what decides the final citations list.
    fake_llm_provider.tool_call_response = ToolCallRequest(
        id="ground_1", name="cite_sources", arguments=json.dumps({"used_source_numbers": [1]})
    )
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "how many vacation and sick days do employees get?"},
        headers=_auth_header(user_tokens),
    )

    events = _parse_sse_events(response.text)
    done_event = next(e for e in events if e["type"] == "done")
    assert len(done_event["citations"]) == 1

    # The grounding call was made with a forced cite_sources tool, and saw
    # the model's own final answer to judge against.
    assert len(fake_llm_provider.tool_call_requests) == 1
    grounding_messages, grounding_tool = fake_llm_provider.tool_call_requests[0]
    assert grounding_tool["function"]["name"] == "cite_sources"
    assert any("Answer to check" in m["content"] for m in grounding_messages if m["content"])


def test_citation_grounding_returns_no_citations_when_model_reports_none_used(
    client: TestClient, user_tokens: dict, fake_llm_provider: FakeLLMProvider
) -> None:
    _upload(client, user_tokens, title="Vacation Policy", content=b"Employees get 20 days of vacation")
    fake_llm_provider.tool_call_response = ToolCallRequest(
        id="ground_1", name="cite_sources", arguments=json.dumps({"used_source_numbers": []})
    )
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "vacation days"},
        headers=_auth_header(user_tokens),
    )

    done_event = next(e for e in _parse_sse_events(response.text) if e["type"] == "done")
    assert done_event["citations"] == []


def test_citation_grounding_degrades_to_unfiltered_when_provider_returns_none(
    client: TestClient, user_tokens: dict, fake_llm_provider: FakeLLMProvider
) -> None:
    # Default FakeLLMProvider behavior (tool_call_response left as None,
    # matching the real base class's "no forced-tool-call support")  — a
    # grounding-unavailable provider must never hide an otherwise-good
    # answer's citations.
    _upload(client, user_tokens, title="Vacation Policy", content=b"Employees get 20 days of vacation")
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "vacation days"},
        headers=_auth_header(user_tokens),
    )

    done_event = next(e for e in _parse_sse_events(response.text) if e["type"] == "done")
    assert len(done_event["citations"]) == 1


def test_citation_grounding_can_be_disabled(
    client: TestClient, user_tokens: dict, fake_llm_provider: FakeLLMProvider, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "CHAT_GROUNDING_ENABLED", False)
    fake_llm_provider.tool_call_response = ToolCallRequest(
        id="ground_1", name="cite_sources", arguments=json.dumps({"used_source_numbers": []})
    )
    _upload(client, user_tokens, title="Vacation Policy", content=b"Employees get 20 days of vacation")
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "vacation days"},
        headers=_auth_header(user_tokens),
    )

    done_event = next(e for e in _parse_sse_events(response.text) if e["type"] == "done")
    # Grounding was skipped entirely (never called, so its "use nothing"
    # response never took effect) — citations pass through unfiltered.
    assert len(done_event["citations"]) == 1
    assert fake_llm_provider.tool_call_requests == []


def test_send_message_reports_duration_in_done_event_and_history(
    client: TestClient, user_tokens: dict
) -> None:
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Hello there"},
        headers=_auth_header(user_tokens),
    )

    done_event = next(e for e in _parse_sse_events(response.text) if e["type"] == "done")
    assert isinstance(done_event["duration_ms"], int)
    assert done_event["duration_ms"] >= 0

    history = client.get(
        f"/api/v1/chat/sessions/{session['id']}/messages", headers=_auth_header(user_tokens)
    ).json()
    assert history[0]["duration_ms"] is None  # user message
    assert history[1]["duration_ms"] == done_event["duration_ms"]  # assistant message


def test_send_message_renames_default_titled_session_from_first_message(
    client: TestClient, user_tokens: dict
) -> None:
    session = _create_session(client, user_tokens)
    assert session["title"] == "New conversation"

    client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "What is our vacation policy?"},
        headers=_auth_header(user_tokens),
    )

    updated = client.get("/api/v1/chat/sessions", headers=_auth_header(user_tokens)).json()
    assert updated[0]["title"] == "What is our vacation policy?"


def test_send_message_does_not_rename_a_custom_titled_session(
    client: TestClient, user_tokens: dict
) -> None:
    session = _create_session(client, user_tokens, title="My custom title")

    client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Hello there"},
        headers=_auth_header(user_tokens),
    )

    updated = client.get("/api/v1/chat/sessions", headers=_auth_header(user_tokens)).json()
    assert updated[0]["title"] == "My custom title"


def test_long_term_memory_still_summarizes_but_is_no_longer_cited_in_chat(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
    fake_memory_repository: FakeMemoryRepository,
    monkeypatch,
) -> None:
    # Long-term memory recall was removed from retrieve_context (this is a
    # RAG-over-documents app, not chat-history recall, and searching it on
    # every message added a DB round-trip nobody benefited from — see
    # retrieval_service.py). The summarization worker itself is left running
    # (in case this comes back), so this test now checks: the summary still
    # gets written, but a later turn no longer cites it or sees it in the
    # prompt.
    monkeypatch.setattr("app.core.config.settings.SHORT_TERM_MEMORY_TURNS", 2)
    session = _create_session(client, user_tokens, title="Chat")

    client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "My favorite color is blue"},
        headers=_auth_header(user_tokens),
    )
    # 2 messages so far (below/at threshold) — no summary yet.
    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "What's the weather like?"},
        headers=_auth_header(user_tokens),
    )
    # 4 messages now (> threshold=2) — this turn should have triggered
    # summarization of the first exchange (synchronous in tests).
    assert response.status_code == 200
    assert fake_memory_repository.get_summary(session["id"]) is not None

    third_response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Anything else?"},
        headers=_auth_header(user_tokens),
    )
    events = _parse_sse_events(third_response.text)
    done_event = next(e for e in events if e["type"] == "done")
    memory_citations = [c for c in done_event["citations"] if c["source"] == "memory"]
    assert memory_citations == []

    chat_calls = [
        call
        for call in fake_llm_provider.calls
        if "Update the rolling summary" not in call[0]["content"]
    ]
    assert not any("from your chat history" in call[0]["content"] for call in chat_calls)


def test_second_message_includes_short_term_memory_in_prompt(
    client: TestClient, user_tokens: dict, fake_llm_provider: FakeLLMProvider
) -> None:
    session = _create_session(client, user_tokens, title="Chat")

    client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "My name is Alice"},
        headers=_auth_header(user_tokens),
    )
    client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "What is my name?"},
        headers=_auth_header(user_tokens),
    )

    second_call_messages = fake_llm_provider.calls[-1]
    roles_and_content = [(m["role"], m["content"]) for m in second_call_messages]
    assert ("user", "My name is Alice") in roles_and_content
    assert ("user", "What is my name?") in roles_and_content


def test_web_search_tool_is_offered_and_cited_when_model_calls_it(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
    fake_web_search_provider: FakeWebSearchProvider,
) -> None:
    fake_web_search_provider.results = [
        WebSearchResult(title="Example Result", url="https://example.com/a", content="Some snippet.")
    ]
    fake_llm_provider.tool_calls_to_request = [
        ToolCallRequest(
            id="call_1", name="web_search", arguments=json.dumps({"query": "current weather"})
        )
    ]
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "what's the weather like today?"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_event = next(e for e in events if e["type"] == "done")

    # The tool actually got called with the model's query, not the raw
    # user message, and the final answer (from the FakeLLMProvider's
    # second, post-tool-result pass) is the persisted content.
    assert fake_web_search_provider.calls == [("current weather", 5)]
    web_citations = [c for c in done_event["citations"] if c["source"] == "web"]
    assert web_citations == [{"source": "web", "url": "https://example.com/a", "title": "Example Result"}]
    assert done_event["type"] == "done"

    # First call offered the tool; the tool-result round-trip messages
    # (assistant tool_calls + tool result) got appended before the second
    # call, which is still offered the tool (the agent loop only forces
    # tools=None once CHAT_MAX_TOOL_HOPS is reached) but this fake model
    # just answers instead of calling it again.
    assert fake_llm_provider.tools_received[0] is not None
    assert fake_llm_provider.tools_received[1] is not None
    second_call_messages = fake_llm_provider.calls[1]
    assert second_call_messages[-2]["role"] == "assistant"
    assert second_call_messages[-2]["tool_calls"][0]["function"]["name"] == "web_search"
    assert second_call_messages[-1]["role"] == "tool"
    assert "Example Result" in second_call_messages[-1]["content"]

    status_events = [e for e in events if e.get("type") == "status"]
    assert any("Searching the web" in e["message"] for e in status_events)

    assert done_event["tools_used"] == ["web_search"]


def test_tools_used_is_persisted_and_returned_on_history_reload(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
    fake_web_search_provider: FakeWebSearchProvider,
) -> None:
    fake_web_search_provider.results = [
        WebSearchResult(title="Example Result", url="https://example.com/a", content="Some snippet.")
    ]
    fake_llm_provider.tool_calls_to_request = [
        ToolCallRequest(id="call_1", name="web_search", arguments=json.dumps({"query": "weather"}))
    ]
    session = _create_session(client, user_tokens, title="Chat")
    client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "what's the weather like today?"},
        headers=_auth_header(user_tokens),
    )

    history = client.get(
        f"/api/v1/chat/sessions/{session['id']}/messages", headers=_auth_header(user_tokens)
    ).json()

    assistant_message = next(m for m in history if m["role"] == "assistant")
    assert assistant_message["tools_used"] == ["web_search"]

    user_message = next(m for m in history if m["role"] == "user")
    assert user_message["tools_used"] is None


def test_tool_selection_telemetry_is_logged_per_turn(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
    fake_web_search_provider: FakeWebSearchProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_web_search_provider.results = [
        WebSearchResult(title="Example Result", url="https://example.com/a", content="Some snippet.")
    ]
    fake_llm_provider.tool_calls_to_request = [
        ToolCallRequest(id="call_1", name="web_search", arguments=json.dumps({"query": "weather"}))
    ]
    session = _create_session(client, user_tokens, title="Chat")

    with caplog.at_level(logging.INFO, logger="app.services.chat_service"):
        client.post(
            f"/api/v1/chat/sessions/{session['id']}/messages",
            json={"content": "what's the weather like today?"},
            headers=_auth_header(user_tokens),
        )

    telemetry_records = [
        r for r in caplog.records if getattr(r, "event", None) == "chat_tool_selection"
    ]
    assert len(telemetry_records) == 1
    record = telemetry_records[0]
    assert record.tools_used == ["web_search"]
    assert record.tool_hops == 1
    assert record.web_search_offered is True
    assert isinstance(record.duration_ms, int)


def test_web_search_tool_not_offered_when_provider_unavailable(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    app.dependency_overrides[get_web_search_provider] = lambda: None
    try:
        session = _create_session(client, user_tokens, title="Chat")
        response = client.post(
            f"/api/v1/chat/sessions/{session['id']}/messages",
            json={"content": "hi"},
            headers=_auth_header(user_tokens),
        )
    finally:
        del app.dependency_overrides[get_web_search_provider]

    assert response.status_code == 200
    # search_documents is still offered — retrieval is core to this app, not
    # gated on a WebSearchProvider — but web_search itself must not be.
    tool_names_offered = {
        tool["function"]["name"] for tool in fake_llm_provider.tools_received[0]
    }
    assert tool_names_offered == {"search_documents"}


def test_search_documents_tool_is_offered_and_cited_when_model_calls_it(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    # No WebSearchProvider involved at all here — proves search_documents
    # works standalone, unconditionally, the additive design's whole point.
    fake_llm_provider.tool_calls_to_request = [
        ToolCallRequest(
            id="call_1", name="search_documents", arguments=json.dumps({"query": "refund policy"})
        )
    ]
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "what's our refund policy?"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["type"] == "done"

    # No documents/chunks exist in this test's fake vector store, so the
    # tool legitimately finds nothing — the point here is the plumbing
    # (tool offered, called, result fed back, turn completes cleanly), not
    # retrieval quality.
    second_call_messages = fake_llm_provider.calls[1]
    assert second_call_messages[-2]["tool_calls"][0]["function"]["name"] == "search_documents"
    assert second_call_messages[-1]["role"] == "tool"
    assert "No matching document passages found" in second_call_messages[-1]["content"]

    status_events = [e for e in events if e.get("type") == "status"]
    assert any("Searching your documents" in e["message"] for e in status_events)


def test_web_search_tool_supports_multiple_hops(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
    fake_web_search_provider: FakeWebSearchProvider,
) -> None:
    # The model calls web_search, gets a result, and calls it *again* with a
    # refined query before finally answering — this is the behavior a
    # single-hop loop couldn't allow (it forced tools=None after one round).
    fake_web_search_provider.results = [
        WebSearchResult(title="Example Result", url="https://example.com/a", content="Some snippet.")
    ]
    fake_llm_provider.tool_calls_to_request = [
        ToolCallRequest(id="call_1", name="web_search", arguments=json.dumps({"query": "weather"}))
    ]
    fake_llm_provider.tool_call_hops = 2
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "what's the weather like today?"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["type"] == "done"

    # Two tool-calling hops, then a third, final call.
    assert fake_web_search_provider.calls == [("weather", 5), ("weather", 5)]
    assert len(fake_llm_provider.calls) == 3
    assert fake_llm_provider.tools_received[0] is not None
    assert fake_llm_provider.tools_received[1] is not None
    # Still under CHAT_MAX_TOOL_HOPS, so the final call was offered the tool
    # too — the model just chose to answer instead of calling it again.
    assert fake_llm_provider.tools_received[2] is not None

    status_events = [e for e in events if e.get("type") == "status"]
    assert len(status_events) == 2


def test_web_search_tool_hops_are_capped(
    client: TestClient,
    user_tokens: dict,
    fake_llm_provider: FakeLLMProvider,
    fake_web_search_provider: FakeWebSearchProvider,
) -> None:
    # A model that never stops requesting the tool must still get forced to
    # a final answer once CHAT_MAX_TOOL_HOPS rounds have happened, rather
    # than looping forever.
    fake_web_search_provider.results = [
        WebSearchResult(title="Example Result", url="https://example.com/a", content="Some snippet.")
    ]
    fake_llm_provider.tool_calls_to_request = [
        ToolCallRequest(id="call_1", name="web_search", arguments=json.dumps({"query": "weather"}))
    ]
    fake_llm_provider.tool_call_hops = settings.CHAT_MAX_TOOL_HOPS + 5
    session = _create_session(client, user_tokens, title="Chat")

    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "what's the weather like today?"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["type"] == "done"

    # CHAT_MAX_TOOL_HOPS tool-calling rounds, plus one final tools=None call.
    assert len(fake_llm_provider.calls) == settings.CHAT_MAX_TOOL_HOPS + 1
    assert fake_web_search_provider.calls == [("weather", 5)] * settings.CHAT_MAX_TOOL_HOPS
    assert fake_llm_provider.tools_received[-1] is None
