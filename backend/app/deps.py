# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# FastAPI dependency wiring: DB sessions plus auth/RBAC dependencies that
# translate token/role failures into HTTP responses.

import logging
from collections.abc import Callable, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.jwt import TokenError, decode_token
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.repositories import user_repository
from app.vectorstore.base import VectorRepository

IngestionEnqueuer = Callable[[int], None]
MemoryEnqueuer = Callable[[int], None]
SessionFactory = Callable[[], Session]
VectorRepositoryFactory = Callable[[], VectorRepository]

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> SessionFactory:
    """A callable that opens a fresh, independently-lifecycled DB session.

    For SSE endpoints: FastAPI closes a request-scoped `Depends(get_db)`
    session as soon as the endpoint function returns the StreamingResponse,
    not once the stream body finishes being consumed — so a generator that
    writes to the DB mid-stream needs to open (and close) its own session
    instead of reusing one from Depends(get_db). Overridden in tests to
    return sessions bound to the same in-memory test engine.
    """
    return SessionLocal


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    return user


def require_roles(*roles: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return current_user

    return dependency


require_admin = require_roles(UserRole.ADMIN)


def get_ingestion_enqueuer() -> IngestionEnqueuer:
    def enqueue(version_id: int) -> None:
        if not settings.CELERY_ENABLED:
            logger.info(
                "CELERY_ENABLED=false; skipping ingestion enqueue for document_version=%s",
                version_id,
            )
            return

        from app.workers.ingestion_tasks import process_document_version

        process_document_version.delay(version_id)

    return enqueue


def get_memory_enqueuer() -> MemoryEnqueuer:
    def enqueue(session_id: int) -> None:
        if not settings.CELERY_ENABLED:
            logger.info(
                "CELERY_ENABLED=false; skipping memory summarization enqueue for session=%s",
                session_id,
            )
            return

        from app.workers.memory_tasks import summarize_session

        summarize_session.delay(session_id)

    return enqueue


def get_vector_repository_factory() -> VectorRepositoryFactory:
    """A lazy getter for the vector repository, not the repository itself.

    Most routes should keep using Depends(get_vector_repository) directly —
    a broken vector store means there's nothing sensible to return anyway,
    so failing loudly at the dependency-resolution stage is correct there.
    Chat's send-message flow is the exception: it's explicitly designed to
    degrade to an answer with no document context when retrieval fails (see
    chat_service.stream_reply's try/except around retrieve_context), but
    that fallback never ran when Weaviate was unreachable — Depends(get_
    vector_repository) resolves (and can raise) before the route body even
    starts, well outside that try/except. Depending on this lazy getter
    instead, and calling it *inside* stream_reply's existing try/except,
    means a connection failure degrades the same way a search failure
    already does.
    """
    from app.vectorstore.factory import get_vector_repository

    return get_vector_repository
