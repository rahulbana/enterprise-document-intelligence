# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Database access for departments. No business rules here — that's
# department_service.

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department


def get_by_id(db: Session, department_id: int) -> Department | None:
    return db.get(Department, department_id)


def get_by_name(db: Session, name: str) -> Department | None:
    stmt = select(Department).where(Department.name == name)
    return db.scalars(stmt).first()


def get_by_ids(db: Session, department_ids: list[int]) -> list[Department]:
    if not department_ids:
        return []
    stmt = select(Department).where(Department.id.in_(department_ids))
    return list(db.scalars(stmt).all())


def list_all(db: Session, *, limit: int | None = None, offset: int = 0) -> list[Department]:
    stmt = select(Department).order_by(Department.name)
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_all(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Department)) or 0


def create(db: Session, *, name: str, description: str | None) -> Department:
    department = Department(name=name, description=description)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def update(
    db: Session, department: Department, *, name: str | None = None, description: str | None = None
) -> Department:
    if name is not None:
        department.name = name
    if description is not None:
        department.description = description
    db.commit()
    db.refresh(department)
    return department


def delete(db: Session, department: Department) -> None:
    db.delete(department)
    db.commit()
