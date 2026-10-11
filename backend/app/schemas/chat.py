# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Request/response shapes for chat sessions/messages. The streaming reply
# itself isn't a JSON response (it's text/event-stream, see chat_router), so
# there's no "ChatReplyRead" schema here.

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.chat_message import ChatMessageRole


class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionRead(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageRead(BaseModel):
    id: int
    role: ChatMessageRole
    content: str
    # validation_alias (not alias): read from the ORM attribute
    # citations_json, but still serialize as "citations" in the API response
    # — a plain `alias=` would apply to both directions and defeat the point.
    citations: list[dict] | None = Field(validation_alias="citations_json", default=None)
    duration_ms: int | None = None
    tools_used: list[str] | None = Field(validation_alias="tools_used_json", default=None)
    created_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)
