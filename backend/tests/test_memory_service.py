# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Unit tests for the long-term memory summarization pipeline: real DB
# session, fake embedding/LLM/memory-store — no network, no live Weaviate or
# LLM needed.

from app.models.chat_message import ChatMessageRole
from app.models.user import UserRole
from app.repositories import chat_repository, user_repository
from app.services import chat_service, memory_service
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeMemoryRepository


def _create_user(db_session, email: str):
    return user_repository.create(
        db_session, email=email, hashed_password="hashed", full_name="Test", role=UserRole.USER
    )


def _add_turns(db_session, session, count: int) -> None:
    for i in range(count):
        chat_repository.add_message(
            db_session, session=session, role=ChatMessageRole.USER, content=f"user turn {i}"
        )
        chat_repository.add_message(
            db_session,
            session=session,
            role=ChatMessageRole.ASSISTANT,
            content=f"assistant turn {i}",
        )


def test_summarize_does_nothing_below_threshold(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.memory_service.settings.SHORT_TERM_MEMORY_TURNS", 10)
    user = _create_user(db_session, "u1@example.com")
    session = chat_service.create_session(db_session, current_user=user, title="Chat")
    _add_turns(db_session, session, count=2)  # 4 messages, below threshold
    memory_repository = FakeMemoryRepository()

    memory_service.summarize_session_memory(
        db_session,
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=FakeLLMProvider(),
        memory_repository=memory_repository,
        session_id=session.id,
    )

    assert memory_repository.get_summary(session.id) is None


def test_summarize_creates_summary_once_over_threshold(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.memory_service.settings.SHORT_TERM_MEMORY_TURNS", 2)
    user = _create_user(db_session, "u2@example.com")
    session = chat_service.create_session(db_session, current_user=user, title="Chat")
    _add_turns(db_session, session, count=3)  # 6 messages, threshold=2 -> 4 "older"
    memory_repository = FakeMemoryRepository()
    llm = FakeLLMProvider(reply="Alice likes hiking.")

    memory_service.summarize_session_memory(
        db_session,
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=llm,
        memory_repository=memory_repository,
        session_id=session.id,
    )

    summary = memory_repository.get_summary(session.id)
    assert summary is not None
    assert summary.summary_text == "Alice likes hiking."
    assert len(llm.calls) == 1


def test_summarize_is_idempotent_when_nothing_new_fell_out(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.memory_service.settings.SHORT_TERM_MEMORY_TURNS", 2)
    user = _create_user(db_session, "u3@example.com")
    session = chat_service.create_session(db_session, current_user=user, title="Chat")
    _add_turns(db_session, session, count=3)
    memory_repository = FakeMemoryRepository()
    llm = FakeLLMProvider(reply="Summary one.")

    memory_service.summarize_session_memory(
        db_session,
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=llm,
        memory_repository=memory_repository,
        session_id=session.id,
    )
    # Running again with no new messages should be a no-op (nothing new has
    # fallen out of the short-term window since last time).
    memory_service.summarize_session_memory(
        db_session,
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=llm,
        memory_repository=memory_repository,
        session_id=session.id,
    )

    assert len(llm.calls) == 1


def test_summarize_folds_new_turns_into_existing_summary(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.memory_service.settings.SHORT_TERM_MEMORY_TURNS", 2)
    user = _create_user(db_session, "u4@example.com")
    session = chat_service.create_session(db_session, current_user=user, title="Chat")
    _add_turns(db_session, session, count=3)
    memory_repository = FakeMemoryRepository()

    memory_service.summarize_session_memory(
        db_session,
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=FakeLLMProvider(reply="First summary."),
        memory_repository=memory_repository,
        session_id=session.id,
    )
    first = memory_repository.get_summary(session.id)

    _add_turns(db_session, session, count=1)  # 2 more messages fall into "older"
    llm2 = FakeLLMProvider(reply="Updated summary.")
    memory_service.summarize_session_memory(
        db_session,
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=llm2,
        memory_repository=memory_repository,
        session_id=session.id,
    )
    second = memory_repository.get_summary(session.id)

    assert first is not None
    assert second is not None
    assert second.covers_up_to_message_id > first.covers_up_to_message_id
    assert "Previous summary:\nFirst summary." in llm2.calls[0][1]["content"]
    assert second.summary_text == "Updated summary."
