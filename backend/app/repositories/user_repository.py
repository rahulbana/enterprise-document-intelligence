# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Database access for users. No business rules here — that's user_service.

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.department import Department
from app.models.user import User, UserRole


def get_by_id(db: Session, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id).options(selectinload(User.departments))
    return db.scalars(stmt).first()


def get_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email).options(selectinload(User.departments))
    return db.scalars(stmt).first()


def get_by_ids(db: Session, user_ids: list[int]) -> list[User]:
    if not user_ids:
        return []
    stmt = select(User).where(User.id.in_(user_ids)).options(selectinload(User.departments))
    return list(db.scalars(stmt).all())


def _search_and_role_filters(stmt, *, q: str | None, role: UserRole | None, is_active: bool | None):
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    return stmt


def list_all(
    db: Session,
    *,
    q: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[User]:
    stmt = select(User).options(selectinload(User.departments)).order_by(User.id)
    stmt = _search_and_role_filters(stmt, q=q, role=role, is_active=is_active)
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_all(
    db: Session,
    *,
    q: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> int:
    stmt = select(func.count()).select_from(User)
    stmt = _search_and_role_filters(stmt, q=q, role=role, is_active=is_active)
    return db.scalar(stmt) or 0


def create(
    db: Session,
    *,
    email: str,
    hashed_password: str,
    full_name: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update(
    db: Session, user: User, *, role: UserRole | None = None, is_active: bool | None = None
) -> User:
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def set_departments(db: Session, user: User, departments: list[Department]) -> User:
    user.departments = departments
    db.commit()
    db.refresh(user)
    return user
