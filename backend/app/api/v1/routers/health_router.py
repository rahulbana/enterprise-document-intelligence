# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Liveness/readiness endpoint used by orchestrators and local dev checks.

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
