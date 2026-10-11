# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Response shapes for the auth audit log.

from datetime import datetime

from pydantic import BaseModel

from app.models.auth_audit_log import AuthEventType


class AuthAuditLogRead(BaseModel):
    id: int
    created_at: datetime
    event_type: AuthEventType
    email: str
    user_id: int | None
    detail: str | None
    prev_hash: str | None
    entry_hash: str

    model_config = {"from_attributes": True}


class AuditChainVerification(BaseModel):
    valid: bool
    broken_at_id: int | None
    total_entries: int
