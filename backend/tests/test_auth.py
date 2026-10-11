# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from fastapi.testclient import TestClient


def test_register_creates_user_with_user_role(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "NewPass123", "full_name": "New Person"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "user"
    # Admin-approval gate: new accounts start inactive and in no department —
    # see auth_service.register_user.
    assert body["is_active"] is False
    assert body["department_ids"] == []
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email_fails(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "DupPass123", "full_name": "Dup"}
    client.post("/api/v1/auth/register", json=payload)

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 400


def test_login_returns_access_and_refresh_tokens(client: TestClient, admin_tokens: dict) -> None:
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "LoginPass123", "full_name": "L"},
    )
    department = client.post(
        "/api/v1/departments", json={"name": "Login Dept"}, headers=admin_headers
    ).json()
    users = client.get("/api/v1/users", headers=admin_headers).json()
    new_user = next(u for u in users if u["email"] == "login@example.com")
    client.patch(f"/api/v1/users/{new_user['id']}", json={"is_active": True}, headers=admin_headers)
    client.put(
        f"/api/v1/users/{new_user['id']}/departments",
        json={"department_ids": [department["id"]]},
        headers=admin_headers,
    )

    response = client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "LoginPass123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_fails_while_pending_admin_approval(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "pending@example.com", "password": "PendingPass123", "full_name": "P"},
    )

    response = client.post(
        "/api/v1/auth/login", json={"email": "pending@example.com", "password": "PendingPass123"}
    )

    assert response.status_code == 401
    assert "pending admin approval" in response.json()["detail"]


def test_login_fails_when_active_but_no_department(client: TestClient, admin_tokens: dict) -> None:
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    client.post(
        "/api/v1/auth/register",
        json={"email": "nodept@example.com", "password": "NoDeptPass123", "full_name": "N"},
    )
    users = client.get("/api/v1/users", headers=admin_headers).json()
    new_user = next(u for u in users if u["email"] == "nodept@example.com")
    client.patch(f"/api/v1/users/{new_user['id']}", json={"is_active": True}, headers=admin_headers)

    response = client.post(
        "/api/v1/auth/login", json={"email": "nodept@example.com", "password": "NoDeptPass123"}
    )

    assert response.status_code == 401
    assert "department" in response.json()["detail"]


def test_deactivating_a_user_revokes_their_existing_session_immediately(
    client: TestClient, user_tokens: dict, admin_tokens: dict
) -> None:
    # user_tokens is already approved (see conftest.register_and_login) and
    # signed in — this proves that deactivating them mid-session invalidates
    # their still-unexpired access token on its very next use, not just
    # future logins.
    me_before = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {user_tokens['access_token']}"}
    )
    assert me_before.status_code == 200
    user_id = me_before.json()["id"]

    client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )

    me_after = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {user_tokens['access_token']}"}
    )
    assert me_after.status_code == 401


def test_login_wrong_password_fails(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "RightPass123", "full_name": "W"},
    )

    response = client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPass123"}
    )

    assert response.status_code == 401


def test_login_unknown_email_fails(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "Whatever123"}
    )

    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, user_tokens: dict) -> None:
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {user_tokens['access_token']}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_refresh_issues_new_access_token(client: TestClient, user_tokens: dict) -> None:
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": user_tokens["refresh_token"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["access_token"] != user_tokens["access_token"]


def test_refresh_rejects_access_token(client: TestClient, user_tokens: dict) -> None:
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": user_tokens["access_token"]}
    )

    assert response.status_code == 401
