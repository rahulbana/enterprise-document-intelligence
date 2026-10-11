# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Document ORM model — the logical document. Actual file content and
# metadata live on DocumentVersion; a Document just groups versions and
# carries ownership/visibility.

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.document_department import document_departments

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.document_version import DocumentVersion
    from app.models.user import User


class DocumentVisibility(str, enum.Enum):
    PRIVATE = "private"
    DEPARTMENT = "department"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    visibility: Mapped[DocumentVisibility] = mapped_column(
        SQLEnum(DocumentVisibility, native_enum=False, length=20), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship()
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_no",
    )
    departments: Mapped[list["Department"]] = relationship(
        secondary=document_departments, back_populates="documents"
    )
