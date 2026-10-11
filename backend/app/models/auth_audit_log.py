# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Append-only authentication audit log. Each row's entry_hash covers its own
# fields plus the previous row's entry_hash, forming a hash chain: editing or
# deleting any past row (including via direct DB access) breaks every hash
# from that point forward, which audit_log_service.verify_chain detects.
# created_at is assigned in Python (not server_default) so the exact value
# hashed is the exact value stored — a DB-computed default would let the
# stored timestamp differ from what went into the hash.

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthEventType(str, enum.Enum):
    REGISTER = "register"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    ACCOUNT_ACTIVATED = "account_activated"
    ACCOUNT_DEACTIVATED = "account_deactivated"


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[AuthEventType] = mapped_column(
        SQLEnum(AuthEventType, native_enum=False, length=30), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
