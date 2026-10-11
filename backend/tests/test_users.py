# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import register_and_login


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_non_admin_cannot_list_users(client: TestClient, user_tokens: dict) -> None:
    response = client.get("/api/v1/users", headers=_auth_header(user_tokens))

    assert response.status_code == 403


def test_admin_can_list_users(client: TestClient, admin_tokens: dict, user_tokens: dict) -> None:
    response = client.get("/api/v1/users", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert {"admin@example.com", "user@example.com"} <= emails


def test_get_missing_user_returns_404(client: TestClient, admin_tokens: dict) -> None:
    response = client.get("/api/v1/users/999999", headers=_auth_header(admin_tokens))

    assert response.status_code == 404


def test_list_users_reports_total_count_and_respects_limit(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    # admin + user = 2 users already registered by the fixtures.
    response = client.get("/api/v1/users?limit=1", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["X-Total-Count"] == "2"


def test_list_users_filters_by_search(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    response = client.get("/api/v1/users?q=regular", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert emails == ["user@example.com"]
    assert response.headers["X-Total-Count"] == "1"


def test_list_users_filters_by_role(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    response = client.get("/api/v1/users?role=admin", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert emails == ["admin@example.com"]


def test_list_users_filters_by_active_status(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    me = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()
    client.patch(
        f"/api/v1/users/{me['id']}", json={"is_active": False}, headers=_auth_header(admin_tokens)
    )

    response = client.get("/api/v1/users?is_active=false", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert emails == ["user@example.com"]


def test_admin_can_deactivate_user(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    me = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()

    response = client.patch(
        f"/api/v1/users/{me['id']}", json={"is_active": False}, headers=_auth_header(admin_tokens)
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # A deactivated user's existing access token is rejected on the next call.
    blocked = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens))
    assert blocked.status_code == 401


def test_admin_can_assign_departments_to_user(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    me = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()
    department = client.post(
        "/api/v1/departments", json={"name": "Finance"}, headers=_auth_header(admin_tokens)
    ).json()

    response = client.put(
        f"/api/v1/users/{me['id']}/departments",
        json={"department_ids": [department["id"]]},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 200
    assert response.json()["department_ids"] == [department["id"]]


def test_assigning_unknown_department_id_fails(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    me = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()

    response = client.put(
        f"/api/v1/users/{me['id']}/departments",
        json={"department_ids": [999999]},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 400


def test_assigning_departments_to_unknown_user_returns_404(
    client: TestClient, admin_tokens: dict
) -> None:
    response = client.put(
        "/api/v1/users/999999/departments",
        json={"department_ids": []},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 404


def test_bulk_deactivate_users(
    client: TestClient, db_session: Session, admin_tokens: dict, user_tokens: dict
) -> None:
    second_tokens = register_and_login(
        client, db_session, email="second@example.com", password="SecondPass123", full_name="Second"
    )
    user_id = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()["id"]
    second_id = client.get("/api/v1/auth/me", headers=_auth_header(second_tokens)).json()["id"]

    response = client.post(
        "/api/v1/users/bulk-status",
        json={"user_ids": [user_id, second_id], "is_active": False},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert {u["id"]: u["is_active"] for u in body} == {user_id: False, second_id: False}

    # Both existing sessions are revoked immediately, same as the single-user path.
    assert client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=_auth_header(second_tokens)).status_code == 401


def test_bulk_activate_users(
    client: TestClient, db_session: Session, admin_tokens: dict, user_tokens: dict
) -> None:
    second_tokens = register_and_login(
        client, db_session, email="reactivate@example.com", password="ReactPass123", full_name="R"
    )
    user_id = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()["id"]
    second_id = client.get("/api/v1/auth/me", headers=_auth_header(second_tokens)).json()["id"]
    client.post(
        "/api/v1/users/bulk-status",
        json={"user_ids": [user_id, second_id], "is_active": False},
        headers=_auth_header(admin_tokens),
    )

    response = client.post(
        "/api/v1/users/bulk-status",
        json={"user_ids": [user_id, second_id], "is_active": True},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 200
    assert all(u["is_active"] for u in response.json())


def test_bulk_status_update_requires_admin(client: TestClient, user_tokens: dict) -> None:
    response = client.post(
        "/api/v1/users/bulk-status",
        json={"user_ids": [1], "is_active": False},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 403


def test_bulk_status_update_with_unknown_id_applies_nothing(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    user_id = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()["id"]

    response = client.post(
        "/api/v1/users/bulk-status",
        json={"user_ids": [user_id, 999999], "is_active": False},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 404
    # All-or-nothing: the valid id in the same batch must not have been
    # toggled just because a later id in the list didn't exist.
    still_active = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens))
    assert still_active.status_code == 200
