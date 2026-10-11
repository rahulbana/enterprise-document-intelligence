# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Role-checking logic, kept framework-agnostic (no FastAPI/HTTPException
# here) so it's reusable outside a request context, e.g. from Celery tasks
# in later phases. app/deps.py translates PermissionDeniedError to a 403.

from app.models.user import User, UserRole


class PermissionDeniedError(Exception):
    pass


def ensure_role(user: User, *allowed_roles: UserRole) -> None:
    if user.role not in allowed_roles:
        allowed = ", ".join(role.value for role in allowed_roles)
        raise PermissionDeniedError(f"Requires one of roles: {allowed}")
