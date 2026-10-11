# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Admin-only user management: list/get/update users, assign departments.

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models.user import User, UserRole
from app.schemas.pagination import PageParams
from app.schemas.user import UserBulkStatusUpdate, UserDepartmentsUpdate, UserRead, UserUpdate
from app.services import user_service
from app.services.user_service import InvalidDepartmentsError, UserNotFoundError

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
def list_users(
    response: Response,
    q: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> list[UserRead]:
    users = user_service.list_users(
        db, q=q, role=role, is_active=is_active, limit=page.limit, offset=page.offset
    )
    total = user_service.count_users(db, q=q, role=role, is_active=is_active)
    response.headers["X-Total-Count"] = str(total)
    return [user_service.to_user_read(user) for user in users]


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = user_service.get_user(db, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return user_service.to_user_read(user)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserRead:
    try:
        user = user_service.update_user(
            db, user_id, role=payload.role, is_active=payload.is_active, actor_id=admin.id
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return user_service.to_user_read(user)


@router.post("/bulk-status", response_model=list[UserRead])
def bulk_update_status(
    payload: UserBulkStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[UserRead]:
    try:
        users = user_service.bulk_set_active(
            db, payload.user_ids, is_active=payload.is_active, actor_id=admin.id
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return [user_service.to_user_read(user) for user in users]


@router.put("/{user_id}/departments", response_model=UserRead)
def set_user_departments(
    user_id: int, payload: UserDepartmentsUpdate, db: Session = Depends(get_db)
) -> UserRead:
    try:
        user = user_service.set_user_departments(db, user_id, payload.department_ids)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidDepartmentsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return user_service.to_user_read(user)
