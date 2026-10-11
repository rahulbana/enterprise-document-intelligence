# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Department directory (any authenticated user can read) and department
# CRUD (admin-only writes). The directory changes rarely and is read on
# nearly every admin/document screen, so the full (unpaginated) list is
# cached for CACHE_TTL_SECONDS and sliced in Python for whatever page was
# requested — one cache key regardless of limit/offset, invalidated in
# department_service on any write.

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core import cache
from app.deps import get_current_user, get_db, require_admin
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.schemas.pagination import PageParams
from app.services import department_service
from app.services.department_service import (
    DEPARTMENTS_CACHE_KEY,
    DepartmentConflictError,
    DepartmentNotFoundError,
)

router = APIRouter(
    prefix="/departments", tags=["departments"], dependencies=[Depends(get_current_user)]
)

_CACHE_TTL_SECONDS = 60


@router.get("", response_model=list[DepartmentRead])
def list_departments(
    response: Response,
    q: str | None = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> list[DepartmentRead]:
    cached_items = cache.get_json(DEPARTMENTS_CACHE_KEY)
    if cached_items is None:
        departments = department_service.list_departments(db)
        cached_items = [
            DepartmentRead.model_validate(d).model_dump(mode="json") for d in departments
        ]
        cache.set_json(DEPARTMENTS_CACHE_KEY, cached_items, ttl_seconds=_CACHE_TTL_SECONDS)

    # Search filters the already-cached full directory in Python rather than
    # pushing `q` into the repository query — the whole thing is one cache
    # key regardless of params, and this directory is small enough that a
    # per-query cache key would be pure overhead for no benefit.
    items = cached_items
    if q:
        needle = q.lower()
        items = [
            item
            for item in cached_items
            if needle in item["name"].lower() or needle in (item.get("description") or "").lower()
        ]

    response.headers["X-Total-Count"] = str(len(items))
    return items[page.offset : page.offset + page.limit]


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(department_id: int, db: Session = Depends(get_db)) -> DepartmentRead:
    try:
        return department_service.get_department(db, department_id)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "",
    response_model=DepartmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)) -> DepartmentRead:
    try:
        return department_service.create_department(
            db, name=payload.name, description=payload.description
        )
    except DepartmentConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.patch(
    "/{department_id}", response_model=DepartmentRead, dependencies=[Depends(require_admin)]
)
def update_department(
    department_id: int, payload: DepartmentUpdate, db: Session = Depends(get_db)
) -> DepartmentRead:
    try:
        return department_service.update_department(
            db, department_id, name=payload.name, description=payload.description
        )
    except DepartmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except DepartmentConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_department(department_id: int, db: Session = Depends(get_db)) -> None:
    try:
        department_service.delete_department(db, department_id)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
