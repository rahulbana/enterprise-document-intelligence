# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Database access for chat sessions and messages. No business rules or
# access control here — that's chat_service.

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage, ChatMessageRole
from app.models.chat_session import ChatSession


def get_session_by_id(db: Session, session_id: int) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def list_sessions_for_user(
    db: Session, user_id: int, *, limit: int | None = None, offset: int = 0
) -> list[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_sessions_for_user(db: Session, user_id: int) -> int:
    stmt = select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
    return db.scalar(stmt) or 0


def create_session(db: Session, *, user_id: int, title: str) -> ChatSession:
    session = ChatSession(user_id=user_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session: ChatSession) -> None:
    db.delete(session)
    db.commit()


def set_title(db: Session, session: ChatSession, title: str) -> None:
    session.title = title
    db.add(session)
    db.commit()


def list_messages(
    db: Session, session_id: int, *, limit: int | None = None, offset: int = 0
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_messages(db: Session, session_id: int) -> int:
    stmt = select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    return db.scalar(stmt) or 0


def list_recent_messages(db: Session, session_id: int, *, limit: int) -> list[ChatMessage]:
    """Most recent `limit` messages, oldest-first (i.e. ready to feed a
    prompt in chronological order) — the DB-backed fallback/source of truth
    behind the Redis short-term buffer."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed(db.scalars(stmt).all()))


def add_message(
    db: Session,
    *,
    session: ChatSession,
    role: ChatMessageRole,
    content: str,
    citations: list[dict] | None = None,
    duration_ms: int | None = None,
    tools_used: list[str] | None = None,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        citations_json=citations,
        duration_ms=duration_ms,
        tools_used_json=tools_used,
    )
    db.add(message)
    # Touch the session so the "most recently active" ordering in
    # list_sessions_for_user reflects new activity, not just renames.
    session.updated_at = datetime.now(UTC)
    db.add(session)
    db.commit()
    db.refresh(message)
    return message
