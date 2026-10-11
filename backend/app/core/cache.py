# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Generic Redis-backed cache for hot, rarely-changing reads (Phase 7) — e.g.
# the department directory, read on nearly every admin/document screen.
# Same graceful-degradation contract as app/memory/short_term.py: Redis is
# an accelerator, not a source of truth. get_json returns None on a miss AND
# on any Redis error, so callers always have a correct (if slower) fallback
# path to the database; set_json/delete are best-effort and never raise.

import json
from functools import lru_cache
from typing import Any

import redis

from app.core.config import settings


@lru_cache
def _get_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def get_json(key: str) -> Any | None:
    try:
        raw = _get_client().get(key)
    except redis.RedisError:
        return None
    if raw is None:
        return None
    return json.loads(raw)


def set_json(key: str, value: Any, *, ttl_seconds: int) -> None:
    try:
        _get_client().set(key, json.dumps(value), ex=ttl_seconds)
    except redis.RedisError:
        pass


def delete(key: str) -> None:
    try:
        _get_client().delete(key)
    except redis.RedisError:
        pass
