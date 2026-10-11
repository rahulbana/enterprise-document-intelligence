# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# ChatMessage ORM model — one turn in a ChatSession. citations_json holds the
# retrieved chunks an assistant reply was grounded on (empty/null for user
# messages), as a plain JSON list so the frontend can render "from document
# X" without a second round-trip. duration_ms is how long the LLM took to
# stream the full reply (null for user messages), so the UI can show it in
# the response footer without re-deriving it from SSE timing on every load.
# tools_used_json is the distinct tool names (e.g. "web_search",
# "search_documents") the agent loop actually called this turn — null/empty
# for user messages and for assistant replies that never called a tool.

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession


class ChatMessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[ChatMessageRole] = mapped_column(
        SQLEnum(ChatMessageRole, native_enum=False, length=20), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tools_used_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
