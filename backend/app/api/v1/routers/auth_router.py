# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Registration, login, token refresh, and "who am I" endpoints. Register/
# login carry a stricter rate limit than the app default — they're the
# brute-force/credential-stuffing surface.

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service, user_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = auth_service.register_user(
            db, email=payload.email, password=payload.password, full_name=payload.full_name
        )
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return user_service.to_user_read(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = auth_service.authenticate_user(db, email=payload.email, password=payload.password)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return auth_service.issue_tokens(user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    try:
        return auth_service.refresh_access_token(db, payload.refresh_token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return user_service.to_user_read(current_user)
