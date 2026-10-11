# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Registration, authentication, and token issuance/refresh.
#
# Registration is admin-gated: a new account is created is_active=False and
# in no department, so it can be created by anyone but can't sign in until
# an admin both activates it and assigns it to at least one department
# (PATCH /users/{id} and PUT /users/{id}/departments — see users_router.py).
# The department requirement only applies to role=USER — admins aren't
# scoped by department anywhere else in this app's RBAC (they manage every
# department/user regardless of their own membership), and exempting them
# here avoids a bootstrap lockout: scripts/create_admin.py creates the very
# first admin into a database that by definition has zero departments yet,
# and that admin has to be able to log in to create the first one.
#
# Deactivating an existing user takes effect immediately, not just at next
# login: get_current_user (app/deps.py) re-checks is_active from the DB on
# every request, so there's no separate "revoke" action needed beyond
# flipping is_active — the user's very next API call, even mid-session,
# gets a 401 regardless of how much longer their JWT would otherwise be
# valid for.

from sqlalchemy.orm import Session

from app.core.jwt import TokenError, create_access_token, create_refresh_token, decode_token
from app.core.security import hash_password, verify_password
from app.models.auth_audit_log import AuthEventType
from app.models.user import User, UserRole
from app.repositories import user_repository
from app.schemas.auth import AccessTokenResponse, TokenResponse
from app.services import audit_log_service


class AuthError(Exception):
    pass


def register_user(db: Session, *, email: str, password: str, full_name: str) -> User:
    if user_repository.get_by_email(db, email) is not None:
        raise AuthError("Email already registered")
    user = user_repository.create(
        db,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.USER,
        is_active=False,
    )
    audit_log_service.record_event(
        db, event_type=AuthEventType.REGISTER, email=email, user_id=user.id
    )
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    user = user_repository.get_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        audit_log_service.record_event(
            db,
            event_type=AuthEventType.LOGIN_FAILURE,
            email=email,
            user_id=user.id if user else None,
            detail="Invalid email or password",
        )
        raise AuthError("Invalid email or password")
    if not user.is_active:
        audit_log_service.record_event(
            db,
            event_type=AuthEventType.LOGIN_FAILURE,
            email=email,
            user_id=user.id,
            detail="Pending admin approval",
        )
        raise AuthError("Your account is pending admin approval.")
    if user.role == UserRole.USER and not user.departments:
        audit_log_service.record_event(
            db,
            event_type=AuthEventType.LOGIN_FAILURE,
            email=email,
            user_id=user.id,
            detail="No department assigned",
        )
        raise AuthError("Your account has not been assigned to a department yet.")
    audit_log_service.record_event(
        db, event_type=AuthEventType.LOGIN_SUCCESS, email=email, user_id=user.id
    )
    return user


def issue_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


def refresh_access_token(db: Session, refresh_token: str) -> AccessTokenResponse:
    try:
        user_id = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise AuthError(str(exc)) from exc

    user = user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")

    return AccessTokenResponse(access_token=create_access_token(user.id))
