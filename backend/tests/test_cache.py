# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Unit tests for app/core/cache.py: the hit/miss/error paths, using a fake
# in-memory client (monkeypatched in place of the real Redis connection) so
# these run without any live Redis — including a client that raises
# redis.RedisError, to verify the graceful-degrade-to-None/no-op contract.

import redis

from app.core import cache


class _FakeRedisClient:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _AlwaysFailsClient:
    def get(self, key: str) -> str:
        raise redis.RedisError("simulated connection failure")

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise redis.RedisError("simulated connection failure")

    def delete(self, key: str) -> None:
        raise redis.RedisError("simulated connection failure")


def test_get_json_returns_none_on_miss(monkeypatch) -> None:
    monkeypatch.setattr(cache, "_get_client", lambda: _FakeRedisClient())

    assert cache.get_json("missing-key") is None


def test_set_json_then_get_json_round_trips(monkeypatch) -> None:
    client = _FakeRedisClient()
    monkeypatch.setattr(cache, "_get_client", lambda: client)

    cache.set_json("k", {"a": 1, "b": [1, 2, 3]}, ttl_seconds=60)

    assert cache.get_json("k") == {"a": 1, "b": [1, 2, 3]}


def test_delete_removes_cached_value(monkeypatch) -> None:
    client = _FakeRedisClient()
    monkeypatch.setattr(cache, "_get_client", lambda: client)
    cache.set_json("k", {"a": 1}, ttl_seconds=60)

    cache.delete("k")

    assert cache.get_json("k") is None


def test_get_json_returns_none_when_redis_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(cache, "_get_client", lambda: _AlwaysFailsClient())

    assert cache.get_json("k") is None


def test_set_json_is_a_silent_noop_when_redis_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(cache, "_get_client", lambda: _AlwaysFailsClient())

    cache.set_json("k", {"a": 1}, ttl_seconds=60)  # must not raise


def test_delete_is_a_silent_noop_when_redis_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(cache, "_get_client", lambda: _AlwaysFailsClient())

    cache.delete("k")  # must not raise
