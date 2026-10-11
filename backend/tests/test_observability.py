# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Integration tests for the Phase 7 observability/rate-limit stack: the
# request-ID middleware, the /metrics endpoint, and slowapi enforcement —
# through the real API, since these are all cross-cutting middleware/app
# wiring rather than something a unit test on one function could cover.

from fastapi.testclient import TestClient


def test_response_carries_a_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_request_id_is_echoed_back_when_provided(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-request-123"})

    assert response.headers["X-Request-ID"] == "test-request-123"


def test_different_requests_get_different_request_ids(client: TestClient) -> None:
    first = client.get("/api/v1/health").headers["X-Request-ID"]
    second = client.get("/api/v1/health").headers["X-Request-ID"]

    assert first != second


def test_metrics_endpoint_exposes_request_counters(client: TestClient) -> None:
    client.get("/api/v1/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text


def test_default_rate_limit_returns_429_once_exceeded(client: TestClient) -> None:
    # RATE_LIMIT_DEFAULT is "100/minute" — exercise the real configured
    # value end-to-end rather than monkeypatching it (the Limiter bakes its
    # default_limits in at construction time, so patching settings after
    # import wouldn't affect the already-built limiter anyway).
    responses = [client.get("/api/v1/health") for _ in range(101)]

    assert [r.status_code for r in responses[:100]] == [200] * 100
    assert responses[100].status_code == 429


def test_login_has_a_stricter_rate_limit_than_default(client: TestClient) -> None:
    # RATE_LIMIT_AUTH is "10/minute", well below the 100/minute default —
    # confirms the per-route override actually takes effect, not just the
    # global default.
    responses = [
        client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "wrong"})
        for _ in range(11)
    ]

    assert 429 not in [r.status_code for r in responses[:10]]
    assert responses[10].status_code == 429
