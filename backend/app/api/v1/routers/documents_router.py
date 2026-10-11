# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Document upload, listing, detail, update, delete, and download. Upload is
# a synchronous (not async def) handler on purpose: it does blocking disk
# I/O via StorageBackend, and a sync route lets FastAPI run it in its
# threadpool instead of blocking the event loop.

from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.deps import IngestionEnqueuer, get_current_user, get_db, get_ingestion_enqueuer
from app.models.document import DocumentVisibility
from app.models.document_version import IngestionStatus
from app.models.user import User
from app.schemas.document import (
    DocumentBulkDelete,
    DocumentDetailRead,
    DocumentPreviewChunk,
    DocumentRead,
    DocumentUpdate,
)
from app.schemas.pagination import PageParams
from app.services import document_service
from app.services.document_service import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
    DocumentValidationError,
)
from app.storage.base import StorageBackend
from app.storage.factory import get_storage_backend
from app.vectorstore.base import VectorRepository
from app.vectorstore.factory import get_vector_repository

router = APIRouter(
    prefix="/documents", tags=["documents"], dependencies=[Depends(get_current_user)]
)


def _parse_department_ids(raw: str) -> list[int]:
    return [int(value) for value in raw.split(",") if value.strip()]


def _content_disposition(filename: str) -> str:
    # filename comes from user input (the uploaded file's name) and is
    # reflected straight into a response header, so it must be sanitized
    # against CRLF header injection and quoted-string escaping — an ASCII
    # fallback plus an RFC 5987 filename* covers non-ASCII names too.
    safe = filename.replace("\r", "").replace("\n", "")
    ascii_fallback = safe.encode("ascii", "ignore").decode("ascii").replace('"', "'") or "download"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(safe)}"


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    visibility: str | None = Form(None),
    department_ids: str = Form(""),
    document_id: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
    enqueue_ingestion: IngestionEnqueuer = Depends(get_ingestion_enqueuer),
) -> DocumentRead:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A filename is required")

    try:
        document = document_service.upload_document(
            db,
            storage,
            enqueue_ingestion,
            current_user=current_user,
            file=file.file,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            document_id=document_id,
            title=title,
            visibility=visibility,
            department_ids=_parse_department_ids(department_ids),
        )
    except DocumentValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return document_service.to_document_read(document)


@router.get("", response_model=list[DocumentRead])
def list_documents(
    response: Response,
    visibility: DocumentVisibility | None = None,
    q: str | None = None,
    status_filter: IngestionStatus | None = Query(None, alias="status"),
    department_id: int | None = None,
    page: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentRead]:
    documents, total = document_service.list_documents(
        db,
        current_user,
        visibility=visibility,
        q=q,
        status=status_filter,
        department_id=department_id,
        limit=page.limit,
        offset=page.offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return [document_service.to_document_read(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentDetailRead)
def get_document(
    document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentDetailRead:
    try:
        document = document_service.get_document(db, current_user, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return document_service.to_document_detail_read(document)


@router.get("/{document_id}/preview", response_model=list[DocumentPreviewChunk])
def get_document_preview(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_repository: VectorRepository = Depends(get_vector_repository),
) -> list[DocumentPreviewChunk]:
    try:
        chunks = document_service.get_document_preview(
            db, vector_repository, current_user, document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return [
        DocumentPreviewChunk(chunk_index=c.chunk_index, content=c.content, metadata=c.metadata)
        for c in chunks
    ]


@router.patch("/{document_id}", response_model=DocumentDetailRead)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentDetailRead:
    try:
        document = document_service.update_document(
            db,
            current_user,
            document_id,
            title=payload.title,
            department_ids=payload.department_ids,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return document_service.to_document_detail_read(document)


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
def bulk_delete_documents(
    payload: DocumentBulkDelete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
    vector_repository: VectorRepository = Depends(get_vector_repository),
) -> None:
    try:
        document_service.bulk_delete_documents(
            db, storage, vector_repository, current_user, payload.document_ids
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
    vector_repository: VectorRepository = Depends(get_vector_repository),
) -> None:
    try:
        document_service.delete_document(db, storage, vector_repository, current_user, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    version_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> StreamingResponse:
    try:
        _, version = document_service.get_version_for_download(
            db, current_user, document_id, version_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc

    return StreamingResponse(
        storage.open(version.storage_key),
        media_type=version.content_type,
        headers={"Content-Disposition": _content_disposition(version.original_filename)},
    )
