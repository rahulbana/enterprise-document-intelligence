# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Admin-facing user management: listing, role/status updates, department
# assignment, and mapping the User model to its API response shape.

from sqlalchemy.orm import Session

from app.models.auth_audit_log import AuthEventType
from app.models.user import User, UserRole
from app.repositories import department_repository, user_repository
from app.schemas.user import UserRead
from app.services import audit_log_service


class UserServiceError(Exception):
    pass


class UserNotFoundError(UserServiceError):
    pass


class InvalidDepartmentsError(UserServiceError):
    pass


def list_users(
    db: Session,
    *,
    q: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[User]:
    return user_repository.list_all(
        db, q=q, role=role, is_active=is_active, limit=limit, offset=offset
    )


def count_users(
    db: Session,
    *,
    q: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> int:
    return user_repository.count_all(db, q=q, role=role, is_active=is_active)


def get_user(db: Session, user_id: int) -> User:
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError("User not found")
    return user


def update_user(
    db: Session,
    user_id: int,
    *,
    role: UserRole | None,
    is_active: bool | None,
    actor_id: int | None = None,
) -> User:
    user = get_user(db, user_id)
    is_active_changed = is_active is not None and is_active != user.is_active
    updated = user_repository.update(db, user, role=role, is_active=is_active)
    if is_active_changed:
        event_type = (
            AuthEventType.ACCOUNT_ACTIVATED if is_active else AuthEventType.ACCOUNT_DEACTIVATED
        )
        audit_log_service.record_event(
            db,
            event_type=event_type,
            email=updated.email,
            user_id=updated.id,
            detail=f"By admin user_id={actor_id}" if actor_id is not None else None,
        )
    return updated


def bulk_set_active(
    db: Session, user_ids: list[int], *, is_active: bool, actor_id: int | None = None
) -> list[User]:
    # Validate every id up front rather than updating-as-we-go: failing
    # partway through a loop would leave some users already toggled (and
    # audit-logged) while the request as a whole reports an error — a bulk
    # action should be all-or-nothing, not silently partial.
    users = user_repository.get_by_ids(db, user_ids)
    found_ids = {user.id for user in users}
    missing = sorted(set(user_ids) - found_ids)
    if missing:
        raise UserNotFoundError(f"Users not found: {missing}")
    return [
        update_user(db, user.id, role=None, is_active=is_active, actor_id=actor_id)
        for user in users
    ]


def set_user_departments(db: Session, user_id: int, department_ids: list[int]) -> User:
    user = get_user(db, user_id)
    departments = department_repository.get_by_ids(db, department_ids)
    if len(departments) != len(set(department_ids)):
        raise InvalidDepartmentsError("One or more department IDs are invalid")
    return user_repository.set_departments(db, user, departments)


def to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        department_ids=[department.id for department in user.departments],
    )
