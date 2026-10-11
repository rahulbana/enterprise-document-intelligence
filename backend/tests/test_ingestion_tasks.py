# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# The Celery task itself is called directly here (not via .delay()) — that
# executes it synchronously in-process, the standard way to unit test a
# Celery task without a broker. SessionLocal is monkeypatched to the same
# in-memory engine the test's db_session uses.

import io

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.document import DocumentVisibility
from app.models.document_version import IngestionStatus
from app.models.user import UserRole
from app.repositories import document_repository, user_repository
from app.storage.local_storage import LocalStorageBackend
from app.workers import ingestion_tasks
from tests.fakes import FakeEmbeddingProvider, FakeVectorRepository


def _create_version(db_session, storage: LocalStorageBackend):
    owner = user_repository.create(
        db_session,
        email="owner@example.com",
        hashed_password="hashed",
        full_name="Owner",
        role=UserRole.USER,
    )
    document = document_repository.create(
        db_session,
        title="Doc",
        owner_id=owner.id,
        visibility=DocumentVisibility.PRIVATE,
        departments=[],
    )
    size, checksum = storage.save("key.txt", io.BytesIO(b"some content here"))
    return document_repository.add_version(
        db_session,
        document,
        storage_key="key.txt",
        original_filename="file.txt",
        file_type="txt",
        content_type="text/plain",
        size_bytes=size,
        checksum_sha256=checksum,
        uploaded_by=owner.id,
    )


@pytest.fixture()
def patched_session_local(db_session, monkeypatch: pytest.MonkeyPatch):
    # A fresh Session per call, bound to the same underlying connection as
    # the test's db_session (StaticPool keeps it to one connection for
    # in-memory SQLite, so commits from either session are visible to both).
    # It must NOT be db_session itself — the task closes whatever session it
    # gets in its `finally`, which would kill the test's own session too.
    session_factory = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(ingestion_tasks, "SessionLocal", session_factory)
    return session_factory


def test_task_marks_version_failed_when_dependencies_are_unavailable(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch, patched_session_local
) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    version = _create_version(db_session, storage)

    def broken_vector_repository():
        raise ConnectionError("could not connect to Weaviate")

    monkeypatch.setattr(ingestion_tasks, "get_storage_backend", lambda: storage)
    monkeypatch.setattr(ingestion_tasks, "get_vector_repository", broken_vector_repository)

    # Called directly (not .delay()) — runs synchronously, no broker needed.
    ingestion_tasks.process_document_version(version.id)

    db_session.refresh(version)
    assert version.status == IngestionStatus.FAILED
    assert "Weaviate" in version.status_message


def test_task_is_a_no_op_for_missing_version(
    db_session, monkeypatch: pytest.MonkeyPatch, patched_session_local
) -> None:
    def broken_storage():
        raise RuntimeError("should not be reached meaningfully")

    monkeypatch.setattr(ingestion_tasks, "get_storage_backend", broken_storage)

    # Dependency construction fails before the version lookup even matters;
    # this just proves a missing version doesn't crash the task either way.
    ingestion_tasks.process_document_version(999_999)


def test_processing_same_version_twice_is_idempotent(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch, patched_session_local
) -> None:
    # Simulates Celery redelivering the task (task_acks_late=True: a worker
    # crash after committing but before acking re-runs the whole task) —
    # the end result must be identical to running it once, not duplicated.
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    version = _create_version(db_session, storage)
    vector_repository = FakeVectorRepository()

    monkeypatch.setattr(ingestion_tasks, "get_storage_backend", lambda: storage)
    monkeypatch.setattr(ingestion_tasks, "get_embedding_provider", FakeEmbeddingProvider)
    monkeypatch.setattr(ingestion_tasks, "get_vector_repository", lambda: vector_repository)

    ingestion_tasks.process_document_version(version.id)
    ingestion_tasks.process_document_version(version.id)

    db_session.refresh(version)
    assert version.status == IngestionStatus.READY
    stored_chunks = vector_repository._stored[version.document_id]["chunks"]
    assert len(stored_chunks) == version.chunk_count
    # replace_document_chunks is delete-then-insert, so a second run leaves
    # exactly the chunks from that run, not the first run's plus the
    # second's.
    assert len(vector_repository.replace_calls) == 2
    assert (
        vector_repository.replace_calls[0]["chunks"] == vector_repository.replace_calls[1]["chunks"]
    )
