# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# ChatMemory ORM model — backs SqliteMemoryRepository (app/memory). One row
# per chat session's rolling long-term summary. No FK constraint to
# chat_sessions: MemoryRepository implementations are meant to be fully
# swappable (a real vector store has no notion of a SQL foreign key either),
# so session_id here is an app-level reference only — cleanup on session
# delete is explicit (chat_service.delete_session), not DB-cascaded.

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatMemory(Base):
    __tablename__ = "chat_memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    vector_json: Mapped[list] = mapped_column(JSON, nullable=False)
    covers_up_to_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
