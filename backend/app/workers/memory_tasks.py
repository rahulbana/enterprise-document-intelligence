# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Thin Celery wrapper around app.services.memory_service: wires up real
# dependencies (a fresh DB session per task, the configured embedding/LLM/
# memory-store backends) and calls the framework-agnostic logic.

import logging

from app.db.session import SessionLocal
from app.memory.long_term_factory import get_memory_repository
from app.providers.embeddings.factory import get_embedding_provider
from app.providers.llm.factory import get_llm_provider
from app.services import memory_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="memory.summarize_session")
def summarize_session(session_id: int) -> None:
    db = SessionLocal()
    try:
        # Long-term memory is best-effort: a summarization failure (LLM/
        # embedding/vector-store unreachable) should never affect chat
        # itself, which has already answered by the time this runs.
        try:
            embedding_provider = get_embedding_provider()
            llm_provider = get_llm_provider()
            memory_repository = get_memory_repository()
        except Exception:
            logger.warning(
                "Memory summarization dependencies unavailable for session=%s",
                session_id,
                exc_info=True,
            )
            return

        try:
            memory_service.summarize_session_memory(
                db,
                embedding_provider=embedding_provider,
                llm_provider=llm_provider,
                memory_repository=memory_repository,
                session_id=session_id,
            )
        except Exception:
            logger.warning("Memory summarization failed for session=%s", session_id, exc_info=True)
    finally:
        db.close()
