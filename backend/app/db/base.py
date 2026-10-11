# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Shared declarative base every ORM model inherits from. Alembic's env.py
# imports Base.metadata for autogeneration, so every model module must be
# imported somewhere reachable from here once models exist (Phase 1+).

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
