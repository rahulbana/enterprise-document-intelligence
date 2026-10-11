# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Admin-only read access to the auth audit log: paginated listing plus a
# tamper-check endpoint that recomputes the hash chain end to end.

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models.auth_audit_log import AuthEventType
from app.repositories import auth_audit_repository
from app.schemas.audit_log import AuditChainVerification, AuthAuditLogRead
from app.schemas.pagination import PageParams
from app.services import audit_log_service

router = APIRouter(
    prefix="/audit-log", tags=["audit-log"], dependencies=[Depends(require_admin)]
)


@router.get("", response_model=list[AuthAuditLogRead])
def list_audit_log(
    response: Response,
    q: str | None = None,
    event_type: AuthEventType | None = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> list[AuthAuditLogRead]:
    entries = auth_audit_repository.list_all(
        db, event_type=event_type, q=q, limit=page.limit, offset=page.offset
    )
    total = auth_audit_repository.count_all(db, event_type=event_type, q=q)
    response.headers["X-Total-Count"] = str(total)
    return entries


@router.get("/verify", response_model=AuditChainVerification)
def verify_audit_log(db: Session = Depends(get_db)) -> AuditChainVerification:
    valid, broken_at_id = audit_log_service.verify_chain(db)
    total = auth_audit_repository.count_all(db)
    return AuditChainVerification(valid=valid, broken_at_id=broken_at_id, total_entries=total)
