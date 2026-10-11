# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Unit tests for the real SqliteMemoryRepository (not the fake) — the one
# other test files exercise indirectly through FakeMemoryRepository, so this
# is the only place actually verifying the SQL access and cosine-similarity
# search work. Runs against its own in-memory engine, never the real
# DATABASE_URL: SqliteMemoryRepository opens its own session via
# app.memory.sqlite_long_term_repository.SessionLocal, so that name is
# monkeypatched to a sessionmaker bound to an isolated in-memory engine.

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  ensures every model is registered on Base.metadata
from app.db.base import Base
from app.memory.sqlite_long_term_repository import SqliteMemoryRepository


@pytest.fixture()
def repository(monkeypatch) -> SqliteMemoryRepository:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr("app.memory.sqlite_long_term_repository.SessionLocal", test_session_local)
    return SqliteMemoryRepository()


def test_get_summary_returns_none_when_absent(repository: SqliteMemoryRepository) -> None:
    assert repository.get_summary(999) is None


def test_upsert_then_get_summary_round_trips(repository: SqliteMemoryRepository) -> None:
    repository.upsert_summary(
        user_id=1,
        session_id=10,
        summary_text="Alice likes hiking.",
        vector=[1.0, 0.0, 0.0],
        covers_up_to_message_id=5,
    )

    summary = repository.get_summary(10)

    assert summary is not None
    assert summary.summary_text == "Alice likes hiking."
    assert summary.covers_up_to_message_id == 5


def test_upsert_replaces_existing_summary_for_same_session(
    repository: SqliteMemoryRepository,
) -> None:
    repository.upsert_summary(
        user_id=1,
        session_id=10,
        summary_text="First version.",
        vector=[1.0, 0.0, 0.0],
        covers_up_to_message_id=3,
    )
    repository.upsert_summary(
        user_id=1,
        session_id=10,
        summary_text="Second version.",
        vector=[0.0, 1.0, 0.0],
        covers_up_to_message_id=7,
    )

    summary = repository.get_summary(10)

    assert summary.summary_text == "Second version."
    assert summary.covers_up_to_message_id == 7


def test_delete_summary_removes_it(repository: SqliteMemoryRepository) -> None:
    repository.upsert_summary(
        user_id=1,
        session_id=10,
        summary_text="Something.",
        vector=[1.0, 0.0, 0.0],
        covers_up_to_message_id=1,
    )

    repository.delete_summary(10)

    assert repository.get_summary(10) is None


def test_delete_summary_is_safe_when_nothing_to_delete(
    repository: SqliteMemoryRepository,
) -> None:
    repository.delete_summary(999)  # must not raise


def test_search_memories_scopes_to_owner(repository: SqliteMemoryRepository) -> None:
    repository.upsert_summary(
        user_id=1,
        session_id=10,
        summary_text="User 1's memory",
        vector=[1.0, 0.0, 0.0],
        covers_up_to_message_id=1,
    )
    repository.upsert_summary(
        user_id=2,
        session_id=20,
        summary_text="User 2's memory",
        vector=[1.0, 0.0, 0.0],
        covers_up_to_message_id=1,
    )

    results = repository.search_memories(user_id=1, query_vector=[1.0, 0.0, 0.0], limit=10)

    assert len(results) == 1
    assert results[0].session_id == 10


def test_search_memories_ranks_by_cosine_similarity(repository: SqliteMemoryRepository) -> None:
    # Session 10's vector is identical to the query; session 20's is
    # orthogonal — 10 should rank strictly first with a near-1.0 score.
    repository.upsert_summary(
        user_id=1,
        session_id=10,
        summary_text="Closely related",
        vector=[1.0, 0.0, 0.0],
        covers_up_to_message_id=1,
    )
    repository.upsert_summary(
        user_id=1,
        session_id=20,
        summary_text="Unrelated",
        vector=[0.0, 1.0, 0.0],
        covers_up_to_message_id=1,
    )

    results = repository.search_memories(user_id=1, query_vector=[1.0, 0.0, 0.0], limit=10)

    assert [r.session_id for r in results] == [10, 20]
    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(0.0)


def test_search_memories_respects_limit(repository: SqliteMemoryRepository) -> None:
    for session_id in range(1, 6):
        repository.upsert_summary(
            user_id=1,
            session_id=session_id,
            summary_text=f"memory {session_id}",
            vector=[1.0, 0.0, 0.0],
            covers_up_to_message_id=1,
        )

    results = repository.search_memories(user_id=1, query_vector=[1.0, 0.0, 0.0], limit=2)

    assert len(results) == 2
