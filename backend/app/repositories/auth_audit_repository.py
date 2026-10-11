# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Database access for the auth audit log. No hashing here — that's
# audit_log_service, which reads get_last() to chain the new row before
# calling create().

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth_audit_log import AuthAuditLog, AuthEventType


def get_last(db: Session) -> AuthAuditLog | None:
    stmt = select(AuthAuditLog).order_by(AuthAuditLog.id.desc()).limit(1)
    return db.scalars(stmt).first()


def create(db: Session, entry: AuthAuditLog) -> AuthAuditLog:
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_all(
    db: Session,
    *,
    event_type: AuthEventType | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[AuthAuditLog]:
    stmt = select(AuthAuditLog).order_by(AuthAuditLog.id.desc())
    if event_type is not None:
        stmt = stmt.where(AuthAuditLog.event_type == event_type)
    if q:
        stmt = stmt.where(AuthAuditLog.email.ilike(f"%{q}%"))
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_all(
    db: Session, *, event_type: AuthEventType | None = None, q: str | None = None
) -> int:
    stmt = select(func.count()).select_from(AuthAuditLog)
    if event_type is not None:
        stmt = stmt.where(AuthAuditLog.event_type == event_type)
    if q:
        stmt = stmt.where(AuthAuditLog.email.ilike(f"%{q}%"))
    return db.scalar(stmt) or 0


def list_all_ascending(db: Session) -> list[AuthAuditLog]:
    stmt = select(AuthAuditLog).order_by(AuthAuditLog.id.asc())
    return list(db.scalars(stmt).all())
