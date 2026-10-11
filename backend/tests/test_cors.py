# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Regression test for a subtle CORS gap: browsers only auto-expose a small
# CORS-safelisted set of response headers to JS across origins (Content-Type,
# Content-Length, ...) — anything else, including X-Total-Count (pagination)
# and Content-Disposition (download filenames), is invisible to frontend
# fetch() code unless the backend explicitly lists it in expose_headers.
# TestClient calls without an Origin header bypass CORSMiddleware entirely
# (Starlette treats them as same-origin), which is exactly how this gap
# shipped unnoticed — every test below sends a real cross-origin Origin
# header, same as the frontend dev server does.

from fastapi.testclient import TestClient

from tests.test_documents import _auth_header, _upload

_ORIGIN = {"Origin": "http://localhost:5173"}


def test_paginated_endpoint_exposes_total_count_cross_origin(
    client: TestClient, user_tokens: dict
) -> None:
    response = client.get("/api/v1/documents", headers={**_auth_header(user_tokens), **_ORIGIN})

    assert response.status_code == 200
    exposed = response.headers.get("access-control-expose-headers", "")
    assert "X-Total-Count" in exposed


def test_download_exposes_content_disposition_cross_origin(
    client: TestClient, user_tokens: dict
) -> None:
    document = _upload(client, user_tokens, title="Doc", content=b"hello").json()

    response = client.get(
        f"/api/v1/documents/{document['id']}/download",
        headers={**_auth_header(user_tokens), **_ORIGIN},
    )

    assert response.status_code == 200
    exposed = response.headers.get("access-control-expose-headers", "")
    assert "Content-Disposition" in exposed
