# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Records auth events into a hash-chained, append-only log and verifies the
# chain on demand. Chaining relies on reading the current last row and
# writing the next one without another writer interleaving between the two —
# safe here because SQLite serializes writers on a single global lock, so
# there's never a real gap between "read last row" and "insert next row"
# for this app's single-process/single-db-writer deployment. A multi-writer
# Postgres deployment would need an explicit row lock (SELECT ... FOR UPDATE
# on the last row, or a dedicated sequence table) to keep this guarantee.

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.audit_hash import compute_entry_hash
from app.models.auth_audit_log import AuthAuditLog, AuthEventType
from app.repositories import auth_audit_repository


def record_event(
    db: Session,
    *,
    event_type: AuthEventType,
    email: str,
    user_id: int | None = None,
    detail: str | None = None,
) -> AuthAuditLog:
    last = auth_audit_repository.get_last(db)
    created_at = datetime.now(UTC)
    entry_hash = compute_entry_hash(
        prev_hash=last.entry_hash if last else None,
        created_at=created_at,
        event_type=event_type.value,
        email=email,
        user_id=user_id,
        detail=detail,
    )
    entry = AuthAuditLog(
        created_at=created_at,
        event_type=event_type,
        email=email,
        user_id=user_id,
        detail=detail,
        prev_hash=last.entry_hash if last else None,
        entry_hash=entry_hash,
    )
    return auth_audit_repository.create(db, entry)


def verify_chain(db: Session) -> tuple[bool, int | None]:
    """Recomputes every entry's hash in order and checks it against what's
    stored, and that each row's prev_hash matches the previous row's
    entry_hash. Returns (True, None) if intact, else (False, id of the
    first row that no longer matches).
    """
    previous_hash: str | None = None
    for row in auth_audit_repository.list_all_ascending(db):
        if row.prev_hash != previous_hash:
            return False, row.id
        expected = compute_entry_hash(
            prev_hash=row.prev_hash,
            created_at=row.created_at,
            event_type=row.event_type.value,
            email=row.email,
            user_id=row.user_id,
            detail=row.detail,
        )
        if expected != row.entry_hash:
            return False, row.id
        previous_hash = row.entry_hash
    return True, None
