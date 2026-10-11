# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.audit_hash import compute_entry_hash
from app.repositories import user_repository
from tests.conftest import register_and_login


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _entries(client: TestClient, admin_tokens: dict, **params) -> list[dict]:
    response = client.get("/api/v1/audit-log", params=params, headers=_auth_header(admin_tokens))
    assert response.status_code == 200
    return response.json()


# --- pure hash math -------------------------------------------------------


def test_compute_entry_hash_is_deterministic() -> None:
    from datetime import datetime

    created_at = datetime(2026, 1, 1, 12, 0, 0)
    kwargs = dict(
        prev_hash="abc123",
        created_at=created_at,
        event_type="login_success",
        email="a@example.com",
        user_id=1,
        detail=None,
    )
    assert compute_entry_hash(**kwargs) == compute_entry_hash(**kwargs)


def test_compute_entry_hash_changes_with_prev_hash() -> None:
    from datetime import datetime

    created_at = datetime(2026, 1, 1, 12, 0, 0)
    base = dict(
        created_at=created_at,
        event_type="login_success",
        email="a@example.com",
        user_id=1,
        detail=None,
    )
    assert compute_entry_hash(prev_hash="one", **base) != compute_entry_hash(prev_hash="two", **base)


def test_compute_entry_hash_ignores_tzinfo_presence() -> None:
    # SQLite drops tzinfo on read-back (see audit_hash.py comment) — a
    # tz-aware and the equivalent naive datetime must hash identically so
    # verify_chain still matches after a round trip through the DB.
    from datetime import UTC, datetime

    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = naive.replace(tzinfo=UTC)
    base = dict(prev_hash=None, event_type="login_success", email="a@example.com", user_id=1, detail=None)
    assert compute_entry_hash(created_at=naive, **base) == compute_entry_hash(created_at=aware, **base)


# --- event recording -------------------------------------------------------


def test_register_logs_audit_event(client: TestClient, db_session: Session, admin_tokens: dict) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "newlogged@example.com", "password": "NewPass123", "full_name": "N"},
    )

    entries = _entries(client, admin_tokens, q="newlogged@example.com")
    assert len(entries) == 1
    assert entries[0]["event_type"] == "register"
    assert entries[0]["user_id"] is not None


def test_login_success_logs_audit_event(client: TestClient, user_tokens: dict, admin_tokens: dict) -> None:
    entries = _entries(client, admin_tokens, q="user@example.com", event_type="login_success")
    assert len(entries) >= 1
    assert entries[0]["email"] == "user@example.com"


def test_login_failure_wrong_password_logs_audit_event(
    client: TestClient, user_tokens: dict, admin_tokens: dict
) -> None:
    client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "WrongPassword1"}
    )

    entries = _entries(client, admin_tokens, q="user@example.com", event_type="login_failure")
    assert len(entries) == 1
    assert entries[0]["detail"] == "Invalid email or password"
    assert entries[0]["user_id"] is not None


def test_login_failure_unknown_email_has_no_user_id(client: TestClient, admin_tokens: dict) -> None:
    client.post(
        "/api/v1/auth/login", json={"email": "ghost404@example.com", "password": "Whatever123"}
    )

    entries = _entries(client, admin_tokens, q="ghost404@example.com")
    assert len(entries) == 1
    assert entries[0]["user_id"] is None
    assert entries[0]["event_type"] == "login_failure"


def test_login_failure_pending_approval_logs_audit_event(
    client: TestClient, admin_tokens: dict
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "stillpending@example.com", "password": "PendingPass123", "full_name": "P"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "stillpending@example.com", "password": "PendingPass123"},
    )

    entries = _entries(client, admin_tokens, q="stillpending@example.com", event_type="login_failure")
    assert len(entries) == 1
    assert entries[0]["detail"] == "Pending admin approval"


def test_login_failure_no_department_logs_audit_event(
    client: TestClient, admin_tokens: dict
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "nodeptaudit@example.com", "password": "NoDeptPass123", "full_name": "N"},
    )
    users = client.get("/api/v1/users", headers=_auth_header(admin_tokens)).json()
    target = next(u for u in users if u["email"] == "nodeptaudit@example.com")
    client.patch(
        f"/api/v1/users/{target['id']}", json={"is_active": True}, headers=_auth_header(admin_tokens)
    )

    client.post(
        "/api/v1/auth/login", json={"email": "nodeptaudit@example.com", "password": "NoDeptPass123"}
    )

    entries = _entries(client, admin_tokens, q="nodeptaudit@example.com", event_type="login_failure")
    assert len(entries) == 1
    assert entries[0]["detail"] == "No department assigned"


def test_activate_and_deactivate_log_audit_events(
    client: TestClient, db_session: Session, admin_tokens: dict
) -> None:
    register_and_login(
        client, db_session, email="gateduser@example.com", password="GatedPass123", full_name="G"
    )
    users = client.get("/api/v1/users", headers=_auth_header(admin_tokens)).json()
    target = next(u for u in users if u["email"] == "gateduser@example.com")

    client.patch(
        f"/api/v1/users/{target['id']}", json={"is_active": False}, headers=_auth_header(admin_tokens)
    )
    client.patch(
        f"/api/v1/users/{target['id']}", json={"is_active": True}, headers=_auth_header(admin_tokens)
    )

    entries = _entries(client, admin_tokens, q="gateduser@example.com")
    event_types = [e["event_type"] for e in entries]
    assert "account_deactivated" in event_types
    assert "account_activated" in event_types
    deactivated = next(e for e in entries if e["event_type"] == "account_deactivated")
    admin = user_repository.get_by_email(db_session, "admin@example.com")
    assert f"admin user_id={admin.id}" in deactivated["detail"]


def test_updating_role_only_does_not_log_an_event(
    client: TestClient, db_session: Session, admin_tokens: dict
) -> None:
    register_and_login(
        client, db_session, email="rolechangeonly@example.com", password="RolePass123", full_name="R"
    )
    users = client.get("/api/v1/users", headers=_auth_header(admin_tokens)).json()
    target = next(u for u in users if u["email"] == "rolechangeonly@example.com")

    before = len(_entries(client, admin_tokens, q="rolechangeonly@example.com"))
    client.patch(
        f"/api/v1/users/{target['id']}", json={"role": "admin"}, headers=_auth_header(admin_tokens)
    )
    after = len(_entries(client, admin_tokens, q="rolechangeonly@example.com"))

    assert after == before


# --- chain verification ----------------------------------------------------


def test_verify_chain_is_valid_after_normal_activity(
    client: TestClient, user_tokens: dict, admin_tokens: dict
) -> None:
    response = client.get("/api/v1/audit-log/verify", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["broken_at_id"] is None
    assert body["total_entries"] >= 1


def test_verify_chain_detects_direct_db_tampering(
    client: TestClient, db_session: Session, user_tokens: dict, admin_tokens: dict
) -> None:
    from app.models.auth_audit_log import AuthAuditLog

    first_entry = db_session.query(AuthAuditLog).order_by(AuthAuditLog.id.asc()).first()
    first_entry.detail = "tampered by attacker"
    db_session.commit()

    response = client.get("/api/v1/audit-log/verify", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["broken_at_id"] == first_entry.id


def test_audit_log_requires_admin(client: TestClient, user_tokens: dict) -> None:
    response = client.get("/api/v1/audit-log", headers=_auth_header(user_tokens))

    assert response.status_code == 403


def test_verify_audit_log_requires_admin(client: TestClient, user_tokens: dict) -> None:
    response = client.get("/api/v1/audit-log/verify", headers=_auth_header(user_tokens))

    assert response.status_code == 403
