# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Department CRUD business rules (name uniqueness, existence checks). The
# department directory is read on nearly every admin/document screen and
# changes rarely, so reads are cached at the router (see departments_router)
# — this module owns invalidation, since it's the one place writes happen.

from sqlalchemy.orm import Session

from app.core import cache
from app.models.department import Department
from app.repositories import department_repository

DEPARTMENTS_CACHE_KEY = "cache:departments:all"


class DepartmentError(Exception):
    pass


class DepartmentNotFoundError(DepartmentError):
    pass


class DepartmentConflictError(DepartmentError):
    pass


def list_departments(db: Session, *, limit: int | None = None, offset: int = 0) -> list[Department]:
    return department_repository.list_all(db, limit=limit, offset=offset)


def count_departments(db: Session) -> int:
    return department_repository.count_all(db)


def get_department(db: Session, department_id: int) -> Department:
    return _get_or_raise(db, department_id)


def create_department(db: Session, *, name: str, description: str | None) -> Department:
    if department_repository.get_by_name(db, name) is not None:
        raise DepartmentConflictError("A department with this name already exists")
    department = department_repository.create(db, name=name, description=description)
    cache.delete(DEPARTMENTS_CACHE_KEY)
    return department


def update_department(
    db: Session, department_id: int, *, name: str | None, description: str | None
) -> Department:
    department = _get_or_raise(db, department_id)
    if name is not None and name != department.name:
        if department_repository.get_by_name(db, name) is not None:
            raise DepartmentConflictError("A department with this name already exists")
    department = department_repository.update(db, department, name=name, description=description)
    cache.delete(DEPARTMENTS_CACHE_KEY)
    return department


def delete_department(db: Session, department_id: int) -> None:
    department = _get_or_raise(db, department_id)
    department_repository.delete(db, department)
    cache.delete(DEPARTMENTS_CACHE_KEY)


def _get_or_raise(db: Session, department_id: int) -> Department:
    department = department_repository.get_by_id(db, department_id)
    if department is None:
        raise DepartmentNotFoundError("Department not found")
    return department
