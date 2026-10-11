# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Document upload/listing/read/update/delete business rules, including
# access control. Kept framework-agnostic: routers translate FastAPI's
# UploadFile into plain (file, filename, content_type) arguments here.
#
# Access rules (deliberately asymmetric so "private" stays private even
# from admins):
#   - read:  owner, OR any member of a department the document targets,
#            OR an admin (for department-visibility documents only).
#   - write: owner, OR an admin (for department-visibility documents only).
# A private document is never readable or writable by anyone but its owner.

import logging
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.deps import IngestionEnqueuer
from app.models.document import Document, DocumentVisibility
from app.models.document_version import DocumentVersion, IngestionStatus
from app.models.user import User, UserRole
from app.repositories import department_repository, document_repository
from app.schemas.document import DocumentDetailRead, DocumentRead, DocumentVersionRead
from app.storage.base import StorageBackend
from app.vectorstore.base import RetrievedChunk, VectorRepository

logger = logging.getLogger(__name__)

ALLOWED_FILE_EXTENSIONS = {
    # Core documents
    "pdf",
    "docx",
    "rtf",
    "odt",
    "txt",
    "md",
    "markdown",
    "htm",
    "html",
    "xhtml",
    "mhtml",
    "mht",
    "xml",
    "epub",
    "json",
    "yaml",
    "yml",
    # Presentations
    "pptx",
    "ppsx",
    "odp",
    # Spreadsheets
    "xlsx",
    "xlsm",
    "xls",
    "csv",
    "tsv",
    "ods",
    "jsonl",
    # Images
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "bmp",
    "webp",
    "gif",
    "heic",
    # Email
    "eml",
    "msg",
    "mbox",
    "pst",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MiB


class DocumentServiceError(Exception):
    pass


class DocumentNotFoundError(DocumentServiceError):
    pass


class DocumentAccessDeniedError(DocumentServiceError):
    pass


class DocumentValidationError(DocumentServiceError):
    pass


def _can_read(user: User, document: Document) -> bool:
    if document.owner_id == user.id:
        return True
    if document.visibility != DocumentVisibility.DEPARTMENT:
        return False
    if user.role == UserRole.ADMIN:
        return True
    user_department_ids = {department.id for department in user.departments}
    return any(department.id in user_department_ids for department in document.departments)


def _can_write(user: User, document: Document) -> bool:
    if document.owner_id == user.id:
        return True
    return document.visibility == DocumentVisibility.DEPARTMENT and user.role == UserRole.ADMIN


def _get_readable_or_raise(db: Session, user: User, document_id: int) -> Document:
    document = document_repository.get_by_id(db, document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found")
    if not _can_read(user, document):
        raise DocumentAccessDeniedError("You don't have access to this document")
    return document


def _validate_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_FILE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
        raise DocumentValidationError(f"Unsupported file type '.{extension}'. Allowed: {allowed}")
    return extension


def upload_document(
    db: Session,
    storage: StorageBackend,
    enqueue_ingestion: IngestionEnqueuer,
    *,
    current_user: User,
    file: BinaryIO,
    filename: str,
    content_type: str,
    document_id: int | None,
    title: str | None,
    visibility: str | None,
    department_ids: list[int],
) -> Document:
    extension = _validate_extension(filename)

    if document_id is not None:
        document = _get_readable_or_raise(db, current_user, document_id)
        if not _can_write(current_user, document):
            raise DocumentAccessDeniedError("You don't have permission to add a version")
    else:
        if not title:
            raise DocumentValidationError("title is required when creating a new document")
        try:
            visibility_enum = DocumentVisibility(visibility)
        except ValueError as exc:
            raise DocumentValidationError("visibility must be 'private' or 'department'") from exc

        departments = []
        if visibility_enum == DocumentVisibility.DEPARTMENT:
            if current_user.role != UserRole.ADMIN:
                raise DocumentAccessDeniedError(
                    "Only admins can upload department-visibility documents"
                )
            if not department_ids:
                raise DocumentValidationError(
                    "department_ids is required for department-visibility documents"
                )
            departments = department_repository.get_by_ids(db, department_ids)
            if len(departments) != len(set(department_ids)):
                raise DocumentValidationError("One or more department IDs are invalid")

        document = document_repository.create(
            db,
            title=title,
            owner_id=current_user.id,
            visibility=visibility_enum,
            departments=departments,
        )

    storage_key = f"{uuid.uuid4().hex}.{extension}"
    size_bytes, checksum = storage.save(storage_key, file)
    if size_bytes > MAX_UPLOAD_BYTES:
        storage.delete(storage_key)
        raise DocumentValidationError(
            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB upload limit"
        )
    if size_bytes == 0:
        storage.delete(storage_key)
        raise DocumentValidationError("Uploaded file is empty")

    try:
        version = document_repository.add_version(
            db,
            document,
            storage_key=storage_key,
            original_filename=filename,
            file_type=extension,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            uploaded_by=current_user.id,
        )
    except Exception:
        storage.delete(storage_key)
        raise

    try:
        enqueue_ingestion(version.id)
    except Exception:
        # Broker unreachable (e.g. Redis not running in dev) shouldn't fail
        # an otherwise-successful upload — the file and DB row are already
        # committed. Leave the version PENDING; it'll need a manual re-enqueue
        # once the broker's back (no automatic retry-on-reconnect exists yet).
        logger.warning(
            "Failed to enqueue ingestion for document_version=%s; leaving status=pending",
            version.id,
            exc_info=True,
        )

    return document


def list_documents(
    db: Session,
    current_user: User,
    *,
    visibility: DocumentVisibility | None,
    q: str | None = None,
    status: IngestionStatus | None = None,
    department_id: int | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[Document], int]:
    items = document_repository.list_readable_by(
        db,
        current_user,
        visibility=visibility,
        q=q,
        status=status,
        department_id=department_id,
        limit=limit,
        offset=offset,
    )
    total = document_repository.count_readable_by(
        db, current_user, visibility=visibility, q=q, status=status, department_id=department_id
    )
    return items, total


def get_document(db: Session, current_user: User, document_id: int) -> Document:
    return _get_readable_or_raise(db, current_user, document_id)


def update_document(
    db: Session,
    current_user: User,
    document_id: int,
    *,
    title: str | None,
    department_ids: list[int] | None,
) -> Document:
    document = _get_readable_or_raise(db, current_user, document_id)
    if not _can_write(current_user, document):
        raise DocumentAccessDeniedError("You don't have permission to edit this document")

    departments = None
    if department_ids is not None:
        if document.visibility != DocumentVisibility.DEPARTMENT:
            raise DocumentValidationError(
                "department_ids only applies to department-visibility documents"
            )
        departments = department_repository.get_by_ids(db, department_ids)
        if len(departments) != len(set(department_ids)):
            raise DocumentValidationError("One or more department IDs are invalid")

    return document_repository.update(db, document, title=title, departments=departments)


def delete_document(
    db: Session,
    storage: StorageBackend,
    vector_repository: VectorRepository,
    current_user: User,
    document_id: int,
) -> None:
    document = _get_readable_or_raise(db, current_user, document_id)
    if not _can_write(current_user, document):
        raise DocumentAccessDeniedError("You don't have permission to delete this document")

    storage_keys = [version.storage_key for version in document.versions]
    document_repository.delete(db, document)
    for storage_key in storage_keys:
        storage.delete(storage_key)
    vector_repository.delete_document_chunks(document_id)


def bulk_delete_documents(
    db: Session,
    storage: StorageBackend,
    vector_repository: VectorRepository,
    current_user: User,
    document_ids: list[int],
) -> None:
    # Same all-or-nothing shape as user_service.bulk_set_active: check every
    # id is readable and writable *before* deleting any of them, so a bad id
    # partway through a multi-select never leaves the selection half-deleted.
    documents = []
    for document_id in document_ids:
        document = _get_readable_or_raise(db, current_user, document_id)
        if not _can_write(current_user, document):
            raise DocumentAccessDeniedError(
                f"You don't have permission to delete document {document_id}"
            )
        documents.append(document)

    for document in documents:
        storage_keys = [version.storage_key for version in document.versions]
        document_repository.delete(db, document)
        for storage_key in storage_keys:
            storage.delete(storage_key)
        vector_repository.delete_document_chunks(document.id)


def get_document_preview(
    db: Session,
    vector_repository: VectorRepository,
    current_user: User,
    document_id: int,
) -> list[RetrievedChunk]:
    """The active version's stored chunks, in order — reconstructs a
    readable (not pixel-perfect) preview from the same content chat
    citations are drawn from, rather than rendering the original file.
    Returns [] if there's nothing ingested yet (pending/processing/failed),
    which the frontend shows as "no preview available" rather than an error."""
    document = _get_readable_or_raise(db, current_user, document_id)
    active_version = next((v for v in document.versions if v.is_active), None)
    if active_version is None or active_version.status != IngestionStatus.READY:
        return []
    return vector_repository.get_document_chunks(document_id)


def get_version_for_download(
    db: Session, current_user: User, document_id: int, version_id: int | None
) -> tuple[Document, DocumentVersion]:
    document = _get_readable_or_raise(db, current_user, document_id)

    if version_id is None:
        version = next((v for v in document.versions if v.is_active), None)
    else:
        version = next((v for v in document.versions if v.id == version_id), None)

    if version is None:
        raise DocumentNotFoundError("Document version not found")
    return document, version


def _to_version_read(version: DocumentVersion) -> DocumentVersionRead:
    return DocumentVersionRead(
        id=version.id,
        version_no=version.version_no,
        original_filename=version.original_filename,
        file_type=version.file_type,
        size_bytes=version.size_bytes,
        is_active=version.is_active,
        uploaded_by=version.uploaded_by,
        uploaded_at=version.uploaded_at,
        status=version.status,
        status_message=version.status_message,
        chunk_count=version.chunk_count,
    )


def to_document_read(document: Document) -> DocumentRead:
    active_version = next((v for v in document.versions if v.is_active), None)
    return DocumentRead(
        id=document.id,
        title=document.title,
        owner_id=document.owner_id,
        visibility=document.visibility,
        department_ids=[department.id for department in document.departments],
        created_at=document.created_at,
        active_version=_to_version_read(active_version) if active_version else None,
        version_count=len(document.versions),
    )


def to_document_detail_read(document: Document) -> DocumentDetailRead:
    base = to_document_read(document)
    return DocumentDetailRead(
        **base.model_dump(),
        versions=[_to_version_read(v) for v in document.versions],
    )
