# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Many-to-many association table between users and departments. A plain
# Core Table (not a mapped class) since it carries no data of its own.

from sqlalchemy import Column, ForeignKey, Table

from app.db.base import Base

user_departments = Table(
    "user_departments",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("department_id", ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True),
)
