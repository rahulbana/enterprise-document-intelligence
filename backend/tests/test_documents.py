# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import io

import openpyxl
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from tests.conftest import register_and_login
from tests.fakes import FakeVectorRepository


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _upload(
    client: TestClient,
    tokens: dict,
    *,
    filename: str = "notes.txt",
    content: bytes = b"hello world",
    content_type: str = "text/plain",
    title: str | None = "My Notes",
    visibility: str | None = "private",
    department_ids: str = "",
    document_id: int | None = None,
):
    data = {"department_ids": department_ids}
    if title is not None:
        data["title"] = title
    if visibility is not None:
        data["visibility"] = visibility
    if document_id is not None:
        data["document_id"] = str(document_id)

    return client.post(
        "/api/v1/documents",
        headers=_auth_header(tokens),
        files={"file": (filename, content, content_type)},
        data=data,
    )


def _create_department(client: TestClient, admin_tokens: dict, name: str = "Engineering") -> dict:
    return client.post(
        "/api/v1/departments", json={"name": name}, headers=_auth_header(admin_tokens)
    ).json()


def test_upload_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("a.txt", b"hi", "text/plain")},
        data={"title": "A", "visibility": "private"},
    )

    assert response.status_code == 401


def test_user_can_upload_private_document(client: TestClient, user_tokens: dict) -> None:
    response = _upload(client, user_tokens)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "My Notes"
    assert body["visibility"] == "private"
    assert body["version_count"] == 1
    assert body["active_version"]["original_filename"] == "notes.txt"
    assert body["active_version"]["is_active"] is True


def test_upload_rejects_unsupported_extension(client: TestClient, user_tokens: dict) -> None:
    response = _upload(client, user_tokens, filename="malware.exe", content=b"x")

    assert response.status_code == 400


def test_upload_rejects_empty_file(client: TestClient, user_tokens: dict) -> None:
    response = _upload(client, user_tokens, content=b"")

    assert response.status_code == 400


def test_non_admin_cannot_upload_department_document(client: TestClient, user_tokens: dict) -> None:
    response = _upload(client, user_tokens, visibility="department", department_ids="1")

    assert response.status_code == 403


def test_department_visibility_requires_department_ids(
    client: TestClient, admin_tokens: dict
) -> None:
    response = _upload(client, admin_tokens, visibility="department", department_ids="")

    assert response.status_code == 400


def test_admin_can_upload_department_document(client: TestClient, admin_tokens: dict) -> None:
    department = _create_department(client, admin_tokens)

    response = _upload(
        client,
        admin_tokens,
        title="Handbook",
        visibility="department",
        department_ids=str(department["id"]),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["visibility"] == "department"
    assert body["department_ids"] == [department["id"]]


def test_department_member_can_see_department_document(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    department = _create_department(client, admin_tokens)
    doc = _upload(
        client,
        admin_tokens,
        title="Handbook",
        visibility="department",
        department_ids=str(department["id"]),
    ).json()

    me = client.get("/api/v1/auth/me", headers=_auth_header(user_tokens)).json()
    client.put(
        f"/api/v1/users/{me['id']}/departments",
        json={"department_ids": [department["id"]]},
        headers=_auth_header(admin_tokens),
    )

    response = client.get(f"/api/v1/documents/{doc['id']}", headers=_auth_header(user_tokens))

    assert response.status_code == 200


def test_non_member_cannot_see_department_document(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    department = _create_department(client, admin_tokens)
    doc = _upload(
        client,
        admin_tokens,
        title="Handbook",
        visibility="department",
        department_ids=str(department["id"]),
    ).json()

    response = client.get(f"/api/v1/documents/{doc['id']}", headers=_auth_header(user_tokens))

    assert response.status_code == 403


def test_user_cannot_see_another_users_private_document(client: TestClient, db_session) -> None:
    owner_tokens = register_and_login(
        client, db_session, email="owner@example.com", password="OwnerPass123", full_name="Owner"
    )
    other_tokens = register_and_login(
        client, db_session, email="other@example.com", password="OtherPass123", full_name="Other"
    )
    doc = _upload(client, owner_tokens).json()

    response = client.get(f"/api/v1/documents/{doc['id']}", headers=_auth_header(other_tokens))

    assert response.status_code == 403


def test_admin_cannot_see_another_users_private_document(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    doc = _upload(client, user_tokens).json()

    response = client.get(f"/api/v1/documents/{doc['id']}", headers=_auth_header(admin_tokens))

    assert response.status_code == 403


def test_list_documents_only_returns_accessible_ones(
    client: TestClient, admin_tokens: dict, user_tokens: dict
) -> None:
    _upload(client, user_tokens, title="Mine")

    response = client.get("/api/v1/documents", headers=_auth_header(admin_tokens))

    assert response.status_code == 200
    titles = {doc["title"] for doc in response.json()}
    assert "Mine" not in titles


def test_reupload_creates_new_version_and_deactivates_old(
    client: TestClient, user_tokens: dict
) -> None:
    first = _upload(client, user_tokens, content=b"version one").json()

    second_response = _upload(
        client,
        user_tokens,
        content=b"version two",
        document_id=first["id"],
        title=None,
        visibility=None,
    )

    assert second_response.status_code == 201
    body = second_response.json()
    assert body["id"] == first["id"]
    assert body["version_count"] == 2
    assert body["active_version"]["version_no"] == 2

    detail = client.get(
        f"/api/v1/documents/{first['id']}", headers=_auth_header(user_tokens)
    ).json()
    versions = {v["version_no"]: v["is_active"] for v in detail["versions"]}
    assert versions == {1: False, 2: True}


def test_other_user_cannot_add_version_to_private_document(client: TestClient, db_session) -> None:
    owner_tokens = register_and_login(
        client, db_session, email="owner2@example.com", password="OwnerPass123", full_name="Owner"
    )
    other_tokens = register_and_login(
        client, db_session, email="other2@example.com", password="OtherPass123", full_name="Other"
    )
    doc = _upload(client, owner_tokens).json()

    response = _upload(client, other_tokens, document_id=doc["id"], title=None, visibility=None)

    assert response.status_code == 403


def test_owner_can_rename_own_document(client: TestClient, user_tokens: dict) -> None:
    doc = _upload(client, user_tokens).json()

    response = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"title": "Renamed"},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"


def test_admin_can_change_department_document_departments(
    client: TestClient, admin_tokens: dict
) -> None:
    dept_a = _create_department(client, admin_tokens, "Sales")
    dept_b = _create_department(client, admin_tokens, "Support")
    doc = _upload(
        client,
        admin_tokens,
        title="Shared",
        visibility="department",
        department_ids=str(dept_a["id"]),
    ).json()

    response = client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"department_ids": [dept_b["id"]]},
        headers=_auth_header(admin_tokens),
    )

    assert response.status_code == 200
    assert response.json()["department_ids"] == [dept_b["id"]]


def test_delete_document_removes_it(client: TestClient, user_tokens: dict) -> None:
    doc = _upload(client, user_tokens).json()

    delete_response = client.delete(
        f"/api/v1/documents/{doc['id']}", headers=_auth_header(user_tokens)
    )
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/documents/{doc['id']}", headers=_auth_header(user_tokens))
    assert get_response.status_code == 404


def test_bulk_delete_removes_all_selected_documents(client: TestClient, user_tokens: dict) -> None:
    doc_a = _upload(client, user_tokens, title="Doc A").json()
    doc_b = _upload(client, user_tokens, title="Doc B").json()

    response = client.post(
        "/api/v1/documents/bulk-delete",
        json={"document_ids": [doc_a["id"], doc_b["id"]]},
        headers=_auth_header(user_tokens),
    )

    assert response.status_code == 204
    assert client.get(f"/api/v1/documents/{doc_a['id']}", headers=_auth_header(user_tokens)).status_code == 404
    assert client.get(f"/api/v1/documents/{doc_b['id']}", headers=_auth_header(user_tokens)).status_code == 404


def test_bulk_delete_with_unowned_document_deletes_nothing(
    client: TestClient, db_session
) -> None:
    owner_tokens = register_and_login(
        client, db_session, email="bulkowner@example.com", password="OwnerPass123", full_name="Owner"
    )
    other_tokens = register_and_login(
        client, db_session, email="bulkother@example.com", password="OtherPass123", full_name="Other"
    )
    own_doc = _upload(client, owner_tokens, title="Owned").json()
    other_doc = _upload(client, other_tokens, title="Not mine").json()

    response = client.post(
        "/api/v1/documents/bulk-delete",
        json={"document_ids": [own_doc["id"], other_doc["id"]]},
        headers=_auth_header(owner_tokens),
    )

    assert response.status_code == 403
    # All-or-nothing: the document the caller *does* own must survive a
    # batch that fails on another id.
    still_there = client.get(f"/api/v1/documents/{own_doc['id']}", headers=_auth_header(owner_tokens))
    assert still_there.status_code == 200


def test_preview_returns_chunks_in_order_for_ready_document(
    client: TestClient, user_tokens: dict
) -> None:
    doc = _upload(client, user_tokens, content=b"hello world " * 50).json()

    response = client.get(
        f"/api/v1/documents/{doc['id']}/preview", headers=_auth_header(user_tokens)
    )

    assert response.status_code == 200
    chunks = response.json()
    assert len(chunks) == doc["active_version"]["chunk_count"]
    assert [c["chunk_index"] for c in chunks] == sorted(c["chunk_index"] for c in chunks)
    assert all(c["content"] for c in chunks)


def test_preview_is_empty_for_a_failed_ingestion(client: TestClient, user_tokens: dict) -> None:
    doc = _upload(client, user_tokens, content=b"   ").json()
    assert doc["active_version"]["status"] == "failed"

    response = client.get(
        f"/api/v1/documents/{doc['id']}/preview", headers=_auth_header(user_tokens)
    )

    assert response.status_code == 200
    assert response.json() == []


def test_preview_denied_for_inaccessible_document(client: TestClient, db_session) -> None:
    owner_tokens = register_and_login(
        client, db_session, email="previewowner@example.com", password="OwnerPass123", full_name="O"
    )
    other_tokens = register_and_login(
        client, db_session, email="previewother@example.com", password="OtherPass123", full_name="P"
    )
    doc = _upload(client, owner_tokens).json()

    response = client.get(
        f"/api/v1/documents/{doc['id']}/preview", headers=_auth_header(other_tokens)
    )

    assert response.status_code == 403


def test_preview_requires_authentication(client: TestClient, user_tokens: dict) -> None:
    doc = _upload(client, user_tokens).json()

    response = client.get(f"/api/v1/documents/{doc['id']}/preview")

    assert response.status_code == 401


def test_download_returns_uploaded_content(client: TestClient, user_tokens: dict) -> None:
    doc = _upload(client, user_tokens, content=b"the actual file content").json()

    response = client.get(
        f"/api/v1/documents/{doc['id']}/download", headers=_auth_header(user_tokens)
    )

    assert response.status_code == 200
    assert response.content == b"the actual file content"
    assert "notes.txt" in response.headers["content-disposition"]


def test_download_denied_for_non_accessible_document(client: TestClient, db_session) -> None:
    owner_tokens = register_and_login(
        client, db_session, email="owner3@example.com", password="OwnerPass123", full_name="Owner"
    )
    other_tokens = register_and_login(
        client, db_session, email="other3@example.com", password="OtherPass123", full_name="Other"
    )
    doc = _upload(client, owner_tokens).json()

    response = client.get(
        f"/api/v1/documents/{doc['id']}/download", headers=_auth_header(other_tokens)
    )

    assert response.status_code == 403


def test_upload_triggers_ingestion_and_becomes_ready(
    client: TestClient, user_tokens: dict, fake_vector_repository: FakeVectorRepository
) -> None:
    doc = _upload(client, user_tokens, content=b"hello world " * 50).json()

    assert doc["active_version"]["status"] == "ready"
    assert doc["active_version"]["chunk_count"] > 0
    assert len(fake_vector_repository.replace_calls) == 1
    assert fake_vector_repository.replace_calls[0]["document_id"] == doc["id"]


def test_upload_with_empty_extractable_text_marks_version_failed(
    client: TestClient, user_tokens: dict
) -> None:
    doc = _upload(client, user_tokens, content=b"   ").json()

    assert doc["active_version"]["status"] == "failed"
    assert doc["active_version"]["status_message"]


def _real_pdf_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(300, 150))
    pdf.drawString(20, 100, text)
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def _real_xlsx_bytes(rows: list[list[str]]) -> bytes:
    workbook = openpyxl.Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def test_upload_pdf_is_accepted_and_ingested(
    client: TestClient, user_tokens: dict, fake_vector_repository: FakeVectorRepository
) -> None:
    content = _real_pdf_bytes("Real extractable PDF text for ingestion " * 5)

    doc = _upload(
        client, user_tokens, filename="report.pdf", content=content, content_type="application/pdf"
    ).json()

    assert doc["active_version"]["status"] == "ready"
    assert doc["active_version"]["chunk_count"] > 0


def test_upload_xlsx_is_accepted_and_ingested(
    client: TestClient, user_tokens: dict, fake_vector_repository: FakeVectorRepository
) -> None:
    content = _real_xlsx_bytes([["Item", "Quantity"], ["Widgets", "10"], ["Gadgets", "20"]])

    doc = _upload(
        client,
        user_tokens,
        filename="inventory.xlsx",
        content=content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ).json()

    assert doc["active_version"]["status"] == "ready"
    assert doc["active_version"]["chunk_count"] > 0


def test_reupload_ingests_new_version_and_deactivates_old_chunks(
    client: TestClient, user_tokens: dict, fake_vector_repository: FakeVectorRepository
) -> None:
    first = _upload(client, user_tokens, content=b"version one content here").json()

    second = _upload(
        client,
        user_tokens,
        content=b"version two content here, now longer",
        document_id=first["id"],
        title=None,
        visibility=None,
    ).json()

    assert second["active_version"]["status"] == "ready"
    assert len(fake_vector_repository.replace_calls) == 2
    assert (
        fake_vector_repository.replace_calls[1]["document_version_id"]
        == second["active_version"]["id"]
    )


def test_delete_document_removes_vector_chunks(
    client: TestClient, user_tokens: dict, fake_vector_repository: FakeVectorRepository
) -> None:
    doc = _upload(client, user_tokens).json()

    response = client.delete(f"/api/v1/documents/{doc['id']}", headers=_auth_header(user_tokens))

    assert response.status_code == 204
    assert fake_vector_repository.delete_calls == [doc["id"]]


def test_list_documents_reports_total_count_and_respects_limit(
    client: TestClient, user_tokens: dict
) -> None:
    for i in range(3):
        _upload(client, user_tokens, filename=f"doc{i}.txt", title=f"Doc {i}")

    response = client.get("/api/v1/documents?limit=2", headers=_auth_header(user_tokens))

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["X-Total-Count"] == "3"


def test_list_documents_filters_by_title_search(client: TestClient, user_tokens: dict) -> None:
    _upload(client, user_tokens, filename="a.txt", title="Vacation Policy")
    _upload(client, user_tokens, filename="b.txt", title="Expense Report")

    response = client.get("/api/v1/documents?q=vacation", headers=_auth_header(user_tokens))

    assert response.status_code == 200
    titles = [doc["title"] for doc in response.json()]
    assert titles == ["Vacation Policy"]
    assert response.headers["X-Total-Count"] == "1"


def test_list_documents_filters_by_department_id(client: TestClient, admin_tokens: dict) -> None:
    dept_a = client.post(
        "/api/v1/departments", json={"name": "Dept A"}, headers=_auth_header(admin_tokens)
    ).json()
    dept_b = client.post(
        "/api/v1/departments", json={"name": "Dept B"}, headers=_auth_header(admin_tokens)
    ).json()
    _upload(
        client,
        admin_tokens,
        filename="a.txt",
        title="Doc A",
        visibility="department",
        department_ids=str(dept_a["id"]),
    )
    _upload(
        client,
        admin_tokens,
        filename="b.txt",
        title="Doc B",
        visibility="department",
        department_ids=str(dept_b["id"]),
    )

    response = client.get(
        f"/api/v1/documents?department_id={dept_a['id']}", headers=_auth_header(admin_tokens)
    )

    assert response.status_code == 200
    titles = [doc["title"] for doc in response.json()]
    assert titles == ["Doc A"]


def test_list_documents_filters_by_status(client: TestClient, user_tokens: dict) -> None:
    _upload(client, user_tokens, filename="a.txt", title="Ready Doc")

    ready_response = client.get("/api/v1/documents?status=ready", headers=_auth_header(user_tokens))
    failed_response = client.get(
        "/api/v1/documents?status=failed", headers=_auth_header(user_tokens)
    )

    assert len(ready_response.json()) == 1
    assert len(failed_response.json()) == 0
