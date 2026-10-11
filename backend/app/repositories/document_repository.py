# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Database access for documents and their versions. No business rules or
# access control here — that's document_service.

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.department import Department
from app.models.document import Document, DocumentVisibility
from app.models.document_version import DocumentVersion, IngestionStatus
from app.models.user import User

_EAGER_LOAD = (selectinload(Document.versions), selectinload(Document.departments))


def get_by_id(db: Session, document_id: int) -> Document | None:
    stmt = select(Document).where(Document.id == document_id).options(*_EAGER_LOAD)
    return db.scalars(stmt).first()


def get_by_ids(db: Session, document_ids: list[int]) -> list[Document]:
    if not document_ids:
        return []
    stmt = select(Document).where(Document.id.in_(document_ids))
    return list(db.scalars(stmt).all())


def _readable_filter(user: User):
    department_ids = [department.id for department in user.departments]
    return or_(
        Document.owner_id == user.id,
        Document.departments.any(Department.id.in_(department_ids)) if department_ids else false(),
    )


def _search_and_status_filters(
    stmt, *, q: str | None, status: IngestionStatus | None, department_id: int | None
):
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    if status is not None:
        stmt = stmt.where(
            Document.versions.any(
                and_(DocumentVersion.is_active.is_(True), DocumentVersion.status == status)
            )
        )
    if department_id is not None:
        stmt = stmt.where(Document.departments.any(Department.id == department_id))
    return stmt


def list_readable_by(
    db: Session,
    user: User,
    *,
    visibility: DocumentVisibility | None,
    q: str | None = None,
    status: IngestionStatus | None = None,
    department_id: int | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Document]:
    stmt = (
        select(Document)
        .where(_readable_filter(user))
        .options(*_EAGER_LOAD)
        .order_by(Document.created_at.desc())
    )
    if visibility is not None:
        stmt = stmt.where(Document.visibility == visibility)
    stmt = _search_and_status_filters(stmt, q=q, status=status, department_id=department_id)
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)

    return list(db.scalars(stmt).unique().all())


def count_readable_by(
    db: Session,
    user: User,
    *,
    visibility: DocumentVisibility | None,
    q: str | None = None,
    status: IngestionStatus | None = None,
    department_id: int | None = None,
) -> int:
    stmt = select(func.count()).select_from(Document).where(_readable_filter(user))
    if visibility is not None:
        stmt = stmt.where(Document.visibility == visibility)
    stmt = _search_and_status_filters(stmt, q=q, status=status, department_id=department_id)
    return db.scalar(stmt) or 0


def create(
    db: Session,
    *,
    title: str,
    owner_id: int,
    visibility: DocumentVisibility,
    departments: list[Department],
) -> Document:
    document = Document(
        title=title, owner_id=owner_id, visibility=visibility, departments=departments
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def add_version(
    db: Session,
    document: Document,
    *,
    storage_key: str,
    original_filename: str,
    file_type: str,
    content_type: str,
    size_bytes: int,
    checksum_sha256: str,
    uploaded_by: int,
) -> DocumentVersion:
    for existing in document.versions:
        existing.is_active = False

    next_version_no = max((v.version_no for v in document.versions), default=0) + 1
    version = DocumentVersion(
        document_id=document.id,
        version_no=next_version_no,
        storage_key=storage_key,
        original_filename=original_filename,
        file_type=file_type,
        content_type=content_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum_sha256,
        uploaded_by=uploaded_by,
        is_active=True,
    )
    db.add(version)
    db.commit()
    db.refresh(document)
    return version


def update(
    db: Session,
    document: Document,
    *,
    title: str | None,
    departments: list[Department] | None,
) -> Document:
    if title is not None:
        document.title = title
    if departments is not None:
        document.departments = departments
    db.commit()
    db.refresh(document)
    return document


def delete(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()
