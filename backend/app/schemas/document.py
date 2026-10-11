# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Request/response shapes for document resources. Upload itself is
# multipart/form-data (handled with FastAPI's File/Form in the router), not
# a JSON body, so there's no "DocumentCreate" schema here.

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.document import DocumentVisibility
from app.models.document_version import IngestionStatus


class DocumentVersionRead(BaseModel):
    id: int
    version_no: int
    original_filename: str
    file_type: str
    size_bytes: int
    is_active: bool
    uploaded_by: int | None
    uploaded_at: datetime
    status: IngestionStatus
    status_message: str | None
    chunk_count: int


class DocumentRead(BaseModel):
    id: int
    title: str
    owner_id: int
    visibility: DocumentVisibility
    department_ids: list[int]
    created_at: datetime
    active_version: DocumentVersionRead | None
    version_count: int


class DocumentDetailRead(DocumentRead):
    versions: list[DocumentVersionRead]


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    department_ids: list[int] | None = None


class DocumentBulkDelete(BaseModel):
    document_ids: list[int] = Field(min_length=1)


class DocumentPreviewChunk(BaseModel):
    chunk_index: int
    content: str
    metadata: dict
