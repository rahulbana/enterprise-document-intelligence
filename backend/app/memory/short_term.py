# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Short-term chat memory: a Redis list per session holding the last N
# messages, so prompt assembly doesn't hit the DB on every turn. Redis is an
# accelerator, not the source of truth — chat_messages (Postgres/SQLite) is;
# every read here can return None (Redis down, or a cold/new session) and
# every write is best-effort, so a missing/unreachable Redis degrades to a
# DB read in chat_service rather than breaking chat.

import json
from functools import lru_cache

import redis

from app.core.config import settings

_KEY_PREFIX = "chat:short_term:"


@lru_cache
def _get_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _key(session_id: int) -> str:
    return f"{_KEY_PREFIX}{session_id}"


def get_buffered_turns(session_id: int, *, max_turns: int) -> list[dict[str, str]] | None:
    """Last max_turns {"role", "content"} dicts, oldest-first. None means
    "ask the DB instead" — either Redis is unreachable or this session has
    no cached turns yet."""
    try:
        raw = _get_client().lrange(_key(session_id), -max_turns, -1)
    except redis.RedisError:
        return None
    if not raw:
        return None
    return [json.loads(item) for item in raw]


def append_turn(session_id: int, *, role: str, content: str, max_turns: int) -> None:
    try:
        client = _get_client()
        key = _key(session_id)
        client.rpush(key, json.dumps({"role": role, "content": content}))
        client.ltrim(key, -max_turns, -1)
    except redis.RedisError:
        pass


def replace_buffer(session_id: int, turns: list[dict[str, str]], *, max_turns: int) -> None:
    """Used to repopulate the cache after a DB fallback read, so the next
    turn in this same session doesn't fall back again."""
    try:
        client = _get_client()
        key = _key(session_id)
        pipe = client.pipeline()
        pipe.delete(key)
        if turns:
            pipe.rpush(key, *(json.dumps(turn) for turn in turns[-max_turns:]))
        pipe.execute()
    except redis.RedisError:
        pass


def clear_session(session_id: int) -> None:
    try:
        _get_client().delete(_key(session_id))
    except redis.RedisError:
        pass
