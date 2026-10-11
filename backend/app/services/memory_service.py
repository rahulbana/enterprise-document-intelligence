# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Rolling long-term memory summarization for a chat session. Kept
# framework-agnostic (no Celery import) so it's directly unit-testable and
# so the Celery task (app/workers/memory_tasks.py) stays a thin wrapper that
# just wires up real dependencies — same split as ingestion_service.
#
# Triggered (from chat_service) once a session has more messages than the
# short-term buffer keeps. Only the messages that have fallen out of that
# window and aren't already folded into the existing summary
# (StoredSummary.covers_up_to_message_id) get summarized each run, so a
# steady-state conversation folds in ~1 new turn per call, not the whole
# history every time.

from sqlalchemy.orm import Session

from app.core.config import settings
from app.memory.long_term_base import MemoryRepository
from app.models.chat_session import ChatSession
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.repositories import chat_repository

_SUMMARY_SYSTEM_PROMPT = (
    "Update the rolling summary of this conversation. Fold the new messages "
    "into the existing summary, preserving names, preferences, decisions, and "
    "facts that might matter later. Be concise — a few sentences, not a "
    "transcript."
)


def summarize_session_memory(
    db: Session,
    *,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    memory_repository: MemoryRepository,
    session_id: int,
) -> None:
    session = db.get(ChatSession, session_id)
    if session is None:
        return

    messages = chat_repository.list_messages(db, session_id)
    recent_cutoff = len(messages) - settings.SHORT_TERM_MEMORY_TURNS
    if recent_cutoff <= 0:
        return  # nothing has fallen out of the short-term window yet

    older_messages = messages[:recent_cutoff]

    existing = memory_repository.get_summary(session_id)
    already_covered_id = existing.covers_up_to_message_id if existing else 0
    new_older = [message for message in older_messages if message.id > already_covered_id]
    if not new_older:
        return  # already summarized everything that's fallen out so far

    turns_text = "\n".join(f"{message.role.value}: {message.content}" for message in new_older)
    previous_summary = existing.summary_text if existing else "(none yet)"

    prompt = [
        {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Previous summary:\n{previous_summary}\n\nNew messages:\n{turns_text}",
        },
    ]
    new_summary = "".join(llm_provider.stream_chat(prompt)).strip()
    if not new_summary:
        return

    vector = embedding_provider.embed_documents([new_summary])[0]
    memory_repository.upsert_summary(
        user_id=session.user_id,
        session_id=session_id,
        summary_text=new_summary,
        vector=vector,
        covers_up_to_message_id=new_older[-1].id,
    )
