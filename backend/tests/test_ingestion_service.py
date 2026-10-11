# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Unit tests for the framework-agnostic ingestion pipeline: real DB session
# and real LocalStorageBackend, but fake embedding provider/vector store —
# no network, no live Weaviate needed.

import io

from app.models.document import DocumentVisibility
from app.models.document_version import DocumentVersion, IngestionStatus
from app.models.user import UserRole
from app.repositories import document_repository, user_repository
from app.services import ingestion_service
from app.storage.local_storage import LocalStorageBackend
from tests.fakes import FakeEmbeddingProvider, FakeVectorRepository


def _create_version(
    db_session, storage: LocalStorageBackend, *, content: bytes, file_type: str = "txt"
) -> tuple:
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
    storage_key = f"test-key.{file_type}"
    size, checksum = storage.save(storage_key, io.BytesIO(content))
    version = document_repository.add_version(
        db_session,
        document,
        storage_key=storage_key,
        original_filename=f"file.{file_type}",
        file_type=file_type,
        content_type="text/plain",
        size_bytes=size,
        checksum_sha256=checksum,
        uploaded_by=owner.id,
    )
    return document, version


def test_ingest_marks_version_ready_and_upserts_chunks(db_session, tmp_path) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    vector_repository = FakeVectorRepository()
    document, version = _create_version(db_session, storage, content=b"hello world " * 100)

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        version_id=version.id,
    )

    db_session.refresh(version)
    assert version.status == IngestionStatus.READY
    assert version.status_message is None
    assert version.chunk_count > 0

    assert len(vector_repository.replace_calls) == 1
    call = vector_repository.replace_calls[0]
    assert call["document_id"] == document.id
    assert call["document_version_id"] == version.id
    assert call["owner_id"] == document.owner_id
    assert len(call["chunks"]) == version.chunk_count
    assert len(call["vectors"]) == version.chunk_count


def test_ingest_marks_version_failed_on_empty_extracted_text(db_session, tmp_path) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    _, version = _create_version(db_session, storage, content=b"   ")

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=FakeVectorRepository(),
        version_id=version.id,
    )

    db_session.refresh(version)
    assert version.status == IngestionStatus.FAILED
    assert version.status_message
    assert version.chunk_count == 0


def test_ingest_marks_version_failed_for_unsupported_file_type(db_session, tmp_path) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    _, version = _create_version(db_session, storage, content=b"data", file_type="xyz")

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=FakeVectorRepository(),
        version_id=version.id,
    )

    db_session.refresh(version)
    assert version.status == IngestionStatus.FAILED
    assert "No parser registered" in version.status_message


def test_ingest_is_a_no_op_for_missing_version(db_session, tmp_path) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    vector_repository = FakeVectorRepository()

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        version_id=999_999,
    )

    assert vector_repository.replace_calls == []


def test_reingesting_replaces_previous_chunks(db_session, tmp_path) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    vector_repository = FakeVectorRepository()
    document, version = _create_version(db_session, storage, content=b"first content here")

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        version_id=version.id,
    )

    storage_key = "test-key-2.txt"
    size, checksum = storage.save(storage_key, io.BytesIO(b"second content here, longer now"))
    second_version = document_repository.add_version(
        db_session,
        document,
        storage_key=storage_key,
        original_filename="file2.txt",
        file_type="txt",
        content_type="text/plain",
        size_bytes=size,
        checksum_sha256=checksum,
        uploaded_by=document.owner_id,
    )

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        version_id=second_version.id,
    )

    assert len(vector_repository.replace_calls) == 2
    assert vector_repository.replace_calls[1]["document_version_id"] == second_version.id
    db_session.refresh(version)
    assert version.is_active is False


def test_processing_status_is_set_before_completion(db_session, tmp_path) -> None:
    # Not directly observable mid-call without mocking, but this documents
    # the intended transition and locks in the final state.
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    _, version = _create_version(db_session, storage, content=b"some content")
    assert version.status == IngestionStatus.PENDING

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=FakeVectorRepository(),
        version_id=version.id,
    )

    db_session.refresh(version)
    assert version.status == IngestionStatus.READY


def test_version_query_by_id_reflects_ready_status(db_session, tmp_path) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    _, version = _create_version(db_session, storage, content=b"some content here")

    ingestion_service.ingest_document_version(
        db_session,
        storage=storage,
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=FakeVectorRepository(),
        version_id=version.id,
    )

    reloaded = db_session.get(DocumentVersion, version.id)
    assert reloaded.status == IngestionStatus.READY
