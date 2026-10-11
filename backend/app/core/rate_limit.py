# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Per-IP rate limiting (Phase 7). Default storage is in-process memory —
# fine for a single uvicorn worker (this app's current deployment) but not
# shared across processes/workers; point RATE_LIMIT_STORAGE_URI at Redis
# (e.g. "redis://localhost:6379/1") once running with more than one worker.
# swallow_errors=True: if the storage backend (Redis) is unreachable, checks
# fail open (requests are allowed) rather than taking the API down — rate
# limiting is a protective layer, not a feature the app depends on to work.
#
# headers_enabled=False: with it on, @limiter.limit()'s per-route decorator
# tries to inject X-RateLimit-* headers directly onto the endpoint's return
# value, which requires that value to already be a starlette.responses.
# Response — ours are typed Pydantic models serialized later via
# response_model, so every decorated route (register/login/send_chat_message)
# would crash on every call. 429 enforcement itself doesn't need this.

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=False,
    swallow_errors=True,
)
