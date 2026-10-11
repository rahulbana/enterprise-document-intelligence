# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Load-test scenario (Phase 7), sized toward the project's 1M-traffic
# target. Run against a real running backend (./start.sh), NOT the test
# suite's fakes — this exercises real Weaviate/Redis/DB/LLM-adjacent code
# paths, so cost and rate limits apply. See LOAD_TESTING.md for how to run
# it and read the results.
#
# Each simulated user registers once, then repeatedly does the read-heavy
# things a real user does far more often than anything else (list
# documents/departments, run a retrieval-debug query) and occasionally the
# expensive things (upload, chat) — weights below aim for that shape, not a
# uniform mix.

import uuid

from locust import HttpUser, between, task


class DocumentIntelligenceUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        email = f"loadtest_{uuid.uuid4().hex}@example.com"
        password = "LoadTest123!"
        self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Load Test"},
        )
        response = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        token = response.json().get("access_token", "")
        self.auth_headers = {"Authorization": f"Bearer {token}"}
        self.chat_session_id: int | None = None

    @task(10)
    def list_documents(self) -> None:
        self.client.get("/api/v1/documents", headers=self.auth_headers, name="/documents [list]")

    @task(8)
    def list_departments(self) -> None:
        self.client.get("/api/v1/departments", headers=self.auth_headers)

    @task(5)
    def me(self) -> None:
        self.client.get("/api/v1/auth/me", headers=self.auth_headers)

    @task(3)
    def retrieval_debug(self) -> None:
        self.client.post(
            "/api/v1/retrieval/debug",
            json={"query": "what does this document say about vacation policy"},
            headers=self.auth_headers,
        )

    @task(1)
    def upload_document(self) -> None:
        content = f"Load test document {uuid.uuid4().hex}".encode()
        self.client.post(
            "/api/v1/documents",
            headers=self.auth_headers,
            files={"file": ("loadtest.txt", content, "text/plain")},
            data={"title": "Load Test Doc", "visibility": "private"},
            name="/documents [upload]",
        )

    @task(1)
    def chat_round_trip(self) -> None:
        if self.chat_session_id is None:
            response = self.client.post(
                "/api/v1/chat/sessions", json={"title": "Load test chat"}, headers=self.auth_headers
            )
            self.chat_session_id = response.json().get("id")
            if self.chat_session_id is None:
                return

        # Streamed (SSE) — catch_response lets us judge success without
        # parsing the stream, since Locust's default success check is just
        # "did we get a 2xx".
        with self.client.post(
            f"/api/v1/chat/sessions/{self.chat_session_id}/messages",
            json={"content": "What can you tell me?"},
            headers=self.auth_headers,
            name="/chat/sessions/[id]/messages",
            catch_response=True,
            stream=True,
        ) as response:
            if response.status_code == 200:
                response.success()
