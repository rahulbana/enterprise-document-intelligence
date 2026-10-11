# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Integration tests for the /retrieval/debug endpoint: real upload -> ingest
# -> retrieve pipeline through the test client, fakes standing in for
# embeddings/vector store/reranker (see tests/conftest.py overrides).

from fastapi.testclient import TestClient

from tests.test_documents import _auth_header, _create_department, _upload


def test_debug_retrieve_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/retrieval/debug", json={"query": "anything"})

    assert response.status_code == 401


def test_debug_retrieve_finds_own_uploaded_document(client: TestClient, user_tokens: dict) -> None:
    _upload(
        client,
        user_tokens,
        content=b"The quick brown fox jumps over the lazy dog",
    )

    response = client.post(
        "/api/v1/retrieval/debug",
        json={"query": "quick brown fox"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "quick brown fox"
    assert len(body["results"]) == 1
    assert "quick brown fox" in body["results"][0]["content"]


def test_debug_retrieve_excludes_other_users_private_document(
    client: TestClient, user_tokens: dict, admin_tokens: dict
) -> None:
    _upload(
        client,
        admin_tokens,
        title="Admin Private Doc",
        content=b"a secret private admin memo about quarterly finances",
    )

    response = client.post(
        "/api/v1/retrieval/debug",
        json={"query": "quarterly finances memo"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_debug_retrieve_includes_department_document_for_member(
    client: TestClient, user_tokens: dict, admin_tokens: dict
) -> None:
    department = _create_department(client, admin_tokens)
    _upload(
        client,
        admin_tokens,
        title="Handbook",
        visibility="department",
        department_ids=str(department["id"]),
        content=b"the department handbook covers onboarding and benefits",
    )

    me = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()
    client.put(
        f"/api/v1/users/{me['id']}/departments",
        json={"department_ids": [department["id"]]},
        headers=_auth_header(admin_tokens),
    )

    response = client.post(
        "/api/v1/retrieval/debug",
        json={"query": "onboarding benefits handbook"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


def test_debug_retrieve_validates_top_k_bounds(client: TestClient, user_tokens: dict) -> None:
    response = client.post(
        "/api/v1/retrieval/debug",
        json={"query": "anything", "top_k": 0},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 422
