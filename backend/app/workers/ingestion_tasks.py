# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Thin Celery wrapper around app.services.ingestion_service: wires up real
# dependencies (a fresh DB session per task, the configured storage/
# embedding/vector-store backends) and calls the framework-agnostic logic.
#
# Idempotency (Phase 7): safe to run twice for the same version_id — e.g. if
# Celery redelivers after a worker crashes mid-task (task_acks_late=True) or
# an operator manually re-enqueues after a transient failure.
# ingest_document_version sets PROCESSING then either READY or FAILED each
# run, and replace_document_chunks is delete-then-insert, so a second full
# run always converges to the same end state rather than duplicating chunks
# or leaving stale ones behind — see
# tests/test_ingestion_tasks.py::test_processing_same_version_twice_is_idempotent.

from app.db.session import SessionLocal
from app.models.document_version import DocumentVersion, IngestionStatus
from app.providers.embeddings.factory import get_embedding_provider
from app.services import ingestion_service
from app.storage.factory import get_storage_backend
from app.vectorstore.factory import get_vector_repository
from app.workers.celery_app import celery_app


@celery_app.task(name="ingestion.process_document_version")
def process_document_version(version_id: int) -> None:
    db = SessionLocal()
    try:
        # Building these can fail on its own (Weaviate unreachable, a
        # misconfigured embedding provider, ...), separately from anything
        # ingest_document_version already handles. Without this, such a
        # failure would crash the task outright and leave the version stuck
        # in PENDING/PROCESSING forever with no visible reason in the UI.
        try:
            storage = get_storage_backend()
            embedding_provider = get_embedding_provider()
            vector_repository = get_vector_repository()
        except Exception as exc:
            version = db.get(DocumentVersion, version_id)
            if version is not None:
                version.status = IngestionStatus.FAILED
                version.status_message = f"Ingestion dependencies unavailable: {exc}"[:1000]
                db.commit()
            return

        ingestion_service.ingest_document_version(
            db,
            storage=storage,
            embedding_provider=embedding_provider,
            vector_repository=vector_repository,
            version_id=version_id,
        )
    finally:
        db.close()
