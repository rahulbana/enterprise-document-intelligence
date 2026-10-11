# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Many-to-many association between documents and the departments they're
# shared with. Only meaningful for visibility=department documents.

from sqlalchemy import Column, ForeignKey, Table

from app.db.base import Base

document_departments = Table(
    "document_departments",
    Base.metadata,
    Column("document_id", ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("department_id", ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True),
)
