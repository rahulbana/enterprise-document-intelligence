# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Parse -> chunk -> embed -> upsert for a single document version. Kept
# framework-agnostic (no Celery import) so it's directly unit-testable and
# so the Celery task (app/workers/ingestion_tasks.py) stays a thin wrapper
# that just wires up real dependencies.

from sqlalchemy.orm import Session

from app.core.config import settings
from app.ingestion.chunking.factory import get_chunking_strategy
from app.ingestion.parsers.factory import get_parser
from app.models.document_version import DocumentVersion, IngestionStatus
from app.providers.embeddings.base import EmbeddingProvider
from app.storage.base import StorageBackend
from app.vectorstore.base import VectorRepository


def ingest_document_version(
    db: Session,
    *,
    storage: StorageBackend,
    embedding_provider: EmbeddingProvider,
    vector_repository: VectorRepository,
    version_id: int,
) -> None:
    version = db.get(DocumentVersion, version_id)
    if version is None:
        return

    version.status = IngestionStatus.PROCESSING
    version.status_message = None
    db.commit()

    try:
        parser = get_parser(version.file_type)
        with storage.open(version.storage_key) as file:
            elements = parser.extract_elements(file)

        chunk_pairs = get_chunking_strategy().chunk(
            elements, chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
        )
        if not chunk_pairs:
            raise ValueError("No extractable text found in this document")

        chunks = [chunk for chunk, _ in chunk_pairs]
        metadatas = [metadata for _, metadata in chunk_pairs]
        vectors = embedding_provider.embed_documents(chunks)

        document = version.document
        vector_repository.replace_document_chunks(
            document_id=document.id,
            document_version_id=version.id,
            owner_id=document.owner_id,
            department_ids=[department.id for department in document.departments],
            chunks=chunks,
            vectors=vectors,
            metadatas=metadatas,
        )

        version.status = IngestionStatus.READY
        version.status_message = None
        version.chunk_count = len(chunks)
    except Exception as exc:
        # Any failure here (bad file content, embedding call failure, vector
        # store unreachable, ...) must land in status_message, not crash the
        # worker or leave the version stuck in PROCESSING forever.
        version.status = IngestionStatus.FAILED
        version.status_message = str(exc)[:1000]
        version.chunk_count = 0

    db.commit()
