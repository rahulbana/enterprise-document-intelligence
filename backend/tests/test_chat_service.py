# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Unit tests for chat session/message CRUD and ownership rules — the
# streaming reply pipeline itself is covered end-to-end via the API in
# tests/test_chat_router.py (SSE needs a real request/response cycle).

from datetime import date

import pytest

from app.models.user import UserRole
from app.repositories import user_repository
from app.services import chat_service
from app.services.chat_service import ChatSessionNotFoundError
from tests.fakes import FakeMemoryRepository


def _create_user(db_session, email: str):
    return user_repository.create(
        db_session, email=email, hashed_password="hashed", full_name="Test", role=UserRole.USER
    )


def test_create_session_defaults_title(db_session) -> None:
    user = _create_user(db_session, "u1@example.com")

    session = chat_service.create_session(db_session, current_user=user, title=None)

    assert session.title == "New conversation"
    assert session.user_id == user.id


def test_create_session_uses_given_title(db_session) -> None:
    user = _create_user(db_session, "u2@example.com")

    session = chat_service.create_session(db_session, current_user=user, title="My chat")

    assert session.title == "My chat"


def test_list_sessions_only_returns_owners(db_session) -> None:
    owner = _create_user(db_session, "owner@example.com")
    other = _create_user(db_session, "other@example.com")
    chat_service.create_session(db_session, current_user=owner, title="Mine")
    chat_service.create_session(db_session, current_user=other, title="Not mine")

    sessions = chat_service.list_sessions(db_session, owner)

    assert len(sessions) == 1
    assert sessions[0].title == "Mine"


def test_get_session_raises_for_other_users_session(db_session) -> None:
    owner = _create_user(db_session, "owner2@example.com")
    other = _create_user(db_session, "other2@example.com")
    session = chat_service.create_session(db_session, current_user=owner, title="Mine")

    with pytest.raises(ChatSessionNotFoundError):
        chat_service.get_session(db_session, other, session.id)


def test_get_session_raises_for_nonexistent_session(db_session) -> None:
    user = _create_user(db_session, "u3@example.com")

    with pytest.raises(ChatSessionNotFoundError):
        chat_service.get_session(db_session, user, 999)


def test_delete_session_removes_it(db_session) -> None:
    user = _create_user(db_session, "u4@example.com")
    session = chat_service.create_session(db_session, current_user=user, title="Mine")

    chat_service.delete_session(
        db_session, user, session.id, memory_repository=FakeMemoryRepository()
    )

    with pytest.raises(ChatSessionNotFoundError):
        chat_service.get_session(db_session, user, session.id)


def test_system_prompt_includes_todays_date_with_no_context() -> None:
    # A model with a training cutoff can't otherwise tell a live/current
    # question apart from one it already "knows" — without an actual date
    # anchor it will confidently answer from stale training data instead of
    # recognizing it needs to search (see chat_service._WEB_SEARCH_NOTE).
    prompt = chat_service._build_system_prompt([], tools_note="")

    assert date.today().isoformat() in prompt


def test_system_prompt_includes_todays_date_with_context() -> None:
    from app.services.retrieval_service import ContextItem

    item = ContextItem(source="document", content="Some text", rerank_score=1.0, document_id=1)

    prompt = chat_service._build_system_prompt([item], tools_note="")

    assert date.today().isoformat() in prompt


def test_web_search_note_requires_tool_for_current_events() -> None:
    prompt = chat_service._build_system_prompt([], tools_note=chat_service._WEB_SEARCH_NOTE)

    assert "MUST call the web_search tool" in prompt


def test_delete_session_raises_for_other_users_session(db_session) -> None:
    owner = _create_user(db_session, "owner3@example.com")
    other = _create_user(db_session, "other3@example.com")
    session = chat_service.create_session(db_session, current_user=owner, title="Mine")

    with pytest.raises(ChatSessionNotFoundError):
        chat_service.delete_session(
            db_session, other, session.id, memory_repository=FakeMemoryRepository()
        )


def test_delete_session_removes_memory_summary(db_session) -> None:
    user = _create_user(db_session, "u5@example.com")
    session = chat_service.create_session(db_session, current_user=user, title="Mine")
    memory_repository = FakeMemoryRepository()
    memory_repository.upsert_summary(
        user_id=user.id,
        session_id=session.id,
        summary_text="Some summary",
        vector=[0.1],
        covers_up_to_message_id=1,
    )

    chat_service.delete_session(db_session, user, session.id, memory_repository=memory_repository)

    assert memory_repository.get_summary(session.id) is None
