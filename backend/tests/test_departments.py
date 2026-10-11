# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from fastapi.testclient import TestClient


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_list_departments_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/departments")

    assert response.status_code == 401


def test_non_admin_cannot_create_department(client: TestClient, user_tokens: dict) -> None:
    response = client.post(
        "/api/v1/departments", json={"name": "Engineering"}, headers=_auth_header(user_tokens)
    )

    assert response.status_code == 403


def test_admin_can_create_and_list_department(client: TestClient, admin_tokens: dict) -> None:
    create_response = client.post(
        "/api/v1/departments",
        json={"name": "Engineering", "description": "Eng dept"},
        headers=_auth_header(admin_tokens),
    )
    assert create_response.status_code == 201
    department = create_response.json()
    assert department["name"] == "Engineering"

    list_response = client.get("/api/v1/departments", headers=_auth_header(admin_tokens))
    assert list_response.status_code == 200
    assert any(d["id"] == department["id"] for d in list_response.json())


def test_create_department_duplicate_name_fails(client: TestClient, admin_tokens: dict) -> None:
    client.post("/api/v1/departments", json={"name": "Sales"}, headers=_auth_header(admin_tokens))

    response = client.post(
        "/api/v1/departments", json={"name": "Sales"}, headers=_auth_header(admin_tokens)
    )

    assert response.status_code == 409


def test_admin_can_update_department(client: TestClient, admin_tokens: dict) -> None:
    created = client.post(
        "/api/v1/departments", json={"name": "Support"}, headers=_auth_header(admin_tokens)
    ).json()

    response = client.patch(
        f"/api/v1/departments/{created['id']}",
        json={"description": "Updated description"},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"


def test_admin_can_delete_department(client: TestClient, admin_tokens: dict) -> None:
    created = client.post(
        "/api/v1/departments", json={"name": "Temp"}, headers=_auth_header(admin_tokens)
    ).json()

    delete_response = client.delete(
        f"/api/v1/departments/{created['id']}", headers=_auth_header(admin_tokens)
    )
    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/departments/{created['id']}", headers=_auth_header(admin_tokens)
    )
    assert get_response.status_code == 404


def test_get_missing_department_returns_404(client: TestClient, admin_tokens: dict) -> None:
    response = client.get("/api/v1/departments/999999", headers=_auth_header(admin_tokens))

    assert response.status_code == 404


def test_list_departments_reports_total_count_header(
    client: TestClient, admin_tokens: dict
) -> None:
    # admin_tokens itself needs a department to log in at all (see the
    # admin-approval gate in auth_service.py), so the table isn't
    # necessarily empty before this test creates its own three — read the
    # baseline instead of assuming a pristine table.
    baseline = int(
        client.get("/api/v1/departments?limit=1", headers=_auth_header(admin_tokens)).headers[
            "X-Total-Count"
        ]
    )
    for name in ("Alpha", "Beta", "Gamma"):
        client.post("/api/v1/departments", json={"name": name}, headers=_auth_header(admin_tokens))

    response = client.get("/api/v1/departments?limit=2", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["X-Total-Count"] == str(baseline + 3)


def test_list_departments_filters_by_search(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    for name in ("Alpha", "Beta", "Gamma"):
        client.post("/api/v1/departments", json={"name": name}, headers=_auth_header(admin_tokens))

    response = client.get("/api/v1/departments?q=alp", headers=_auth_header(user_tokens))

    assert response.status_code == 200
    names = [d["name"] for d in response.json()]
    assert names == ["Alpha"]
    assert response.headers["X-Total-Count"] == "1"


def test_list_departments_offset_paginates_correctly(
    client: TestClient, admin_tokens: dict
) -> None:
    for name in ("Alpha", "Beta", "Gamma"):
        client.post("/api/v1/departments", json={"name": name}, headers=_auth_header(admin_tokens))

    # Same baseline caveat as the total-count test above — establish the
    # actual sorted order rather than assuming these three are the only
    # rows in the table.
    all_departments = client.get(
        "/api/v1/departments?limit=200", headers=_auth_header(admin_tokens)
    ).json()
    expected_order = [d["name"] for d in all_departments]

    page1 = client.get(
        "/api/v1/departments?limit=2&offset=0", headers=_auth_header(admin_tokens)
    ).json()
    page2 = client.get(
        "/api/v1/departments?limit=2&offset=2", headers=_auth_header(admin_tokens)
    ).json()

    assert [d["name"] for d in page1] == expected_order[0:2]
    assert [d["name"] for d in page2] == expected_order[2:4]


def test_created_department_is_visible_despite_list_caching(
    client: TestClient, admin_tokens: dict
) -> None:
    # Populate the cache with a list call, then create a new department —
    # if invalidation didn't work, this next list would still show the
    # pre-create (cached) set and miss "Newcomer".
    client.get("/api/v1/departments", headers=_auth_header(admin_tokens))

    client.post(
        "/api/v1/departments", json={"name": "Newcomer"}, headers=_auth_header(admin_tokens)
    )

    response = client.get("/api/v1/departments", headers=_auth_header(admin_tokens))
    assert any(d["name"] == "Newcomer" for d in response.json())
