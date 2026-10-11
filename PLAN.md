<!--
Name: Rahul Singh Bana
Email: bana.saa@gmail.com
LinkedIn: https://www.linkedin.com/in/rahulsinghbana
-->

# Document Intelligence — Project Plan

A multi-user, RBAC-secured, department-aware document chat platform with hybrid
retrieval (BM25 + vector) over Weaviate, a cross-encoder re-ranker, and layered
short-term / long-term chat memory. LLM and embedding providers are swappable
between OpenAI and Ollama via `.env`.

This document is the single source of truth for scope and sequencing. Each
phase below ends in a working, demoable slice — nothing is "half-wired."

---

## 1. Decisions locked in (from requirements discussion)

| Area | Decision |
|---|---|
| Auth | Self-managed JWT (access + refresh), bcrypt/argon2 password hashing. SSO deferred, but auth layer is provider-agnostic. |
| Roles | `admin`, `user` only (department-manager role deferred). |
| Departments | Admin CRUD's departments dynamically. Users can belong to **multiple** departments (many-to-many). |
| Tenancy | Single organization. No `tenant_id` yet — added later if needed. |
| Document scope | A document can target one or many departments, or be private to the uploading user. |
| Duplicate admin uploads | Tracked as **versions** of the same logical document; only the latest version is "active" (searchable). Old versions are soft-retired, not deleted. |
| File types (Phase 1) | `.docx`, `.txt`, `.md`. PDF / PPTX / images(OCR) added in a later phase behind the same parser interface. |
| File storage | Local disk behind a `StorageBackend` interface now; S3/GCS backend added later without touching callers. |
| Task queue | Celery + Redis for ingestion (parse → chunk → embed → upsert), from Phase 1. Matches the 1M-traffic target. |
| Vector DB | Weaviate (hybrid search: BM25 + vector, native `alpha` blending). |
| Re-ranker | Pluggable `Reranker` interface. Concrete impl for now: local cross-encoder via `sentence-transformers` (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2` or `BAAI/bge-reranker-base`). Cohere/other rerankers can be added later as another implementation. |
| Embeddings | Pluggable `EmbeddingProvider` — **implemented in Phase 0.5** (pulled forward from Phase 3, self-contained). Three implementations, selected via `EMBEDDING_PROVIDER` in `.env`: Ollama `nomic-embed-text` (default; asymmetric, uses `search_query:`/`search_document:` prefixes), local `sentence-transformers` running `all-MiniLM-L6-v2` in-process (symmetric, no prefixes, no external service, no custom model code), and OpenAI `text-embedding-3-small` (symmetric). Prefixes and `trust_remote_code` are configured per-provider so swapping either provider's underlying model doesn't silently break the other's assumptions. |
| Chat LLM | Pluggable `LLMProvider`. Default: OpenAI `gpt-4o-mini`. Ollama (e.g. `llama3.1`) switchable via `.env`. |
| Chat UX | ChatGPT-style: multiple named conversations per user; every conversation can retrieve from all of that user's own docs + active docs from all departments they belong to. |
| Memory | Short-term: last-N-turns buffer in Redis per conversation. Long-term: LLM-generated rolling summaries of older turns, embedded and stored per-user in a dedicated Weaviate collection, retrieved alongside document chunks at answer time. |
| Streaming | SSE token streaming from FastAPI to React. |
| Frontend | React + Vite + TypeScript + Tailwind. |
| DB (Phase 1) | SQLite via SQLAlchemy + Alembic, with the ORM layer written so swapping to Postgres later is a connection-string + dialect change, not a rewrite. |
| Python | 3.12, virtualenv created by `setup.sh`. |
| File convention | Every source file starts with the signature comment block (name/email/linkedin) and does **one thing** — no god-files. |

---

## 2. High-level architecture

```
                         ┌──────────────────────┐
                         │   React (Vite/TS)     │
                         │  Admin UI · Chat UI    │
                         └──────────┬────────────┘
                                    │ REST + SSE (JWT bearer)
                         ┌──────────▼────────────┐
                         │      FastAPI API       │
                         │ routers → services →   │
                         │ repositories → models   │
                         └───┬───────────┬────────┘
                             │           │
                 enqueue     │           │ read/write
                 ingestion   │           │
                 job         │           ▼
                 ┌───────────▼───┐   ┌─────────────┐
                 │  Redis (broker │   │   SQLite    │
                 │  + short-term  │   │ (→Postgres) │
                 │  memory cache) │   │ users, RBAC,│
                 └───────┬────────┘   │ docs, chats │
                         │            └─────────────┘
                 ┌───────▼────────┐
                 │ Celery workers  │
                 │ parse→chunk→    │
                 │ embed→upsert    │
                 └───────┬────────┘
                         │
                 ┌───────▼────────┐
                 │    Weaviate     │
                 │ DocumentChunk   │
                 │ UserMemory      │
                 │ (hybrid search) │
                 └─────────────────┘

External providers (swappable via .env):
  LLMProvider        → OpenAI (gpt-4o-mini) | Ollama (llama3.1)
  EmbeddingProvider   → Ollama (nomic-embed-text) | OpenAI (text-embedding-3-small)
  Reranker            → local cross-encoder (sentence-transformers) | (future: Cohere)
```

**Retrieval flow per chat message:**
1. Load short-term memory (Redis buffer) for the conversation.
2. Embed the user query (`EmbeddingProvider`).
3. Hybrid search in Weaviate, scoped by an access filter (`owner_id == user` OR `department_id IN user's departments`) AND `is_active_version == true` — over both `DocumentChunk` and the user's `UserMemory` collection.
4. Re-rank the merged candidate set with the `Reranker`, take top-k.
5. Build the prompt: system instructions + long-term memory summary (if relevant) + short-term buffer + re-ranked chunks (with citations) + user question.
6. Stream the answer via `LLMProvider`, token-by-token over SSE.
7. Persist the turn; asynchronously (Celery) roll old turns into an updated long-term memory summary once the short-term buffer exceeds N turns.

---

## 3. Backend module layout (modular by responsibility, no god-files)

```
document-intelligence/
├── backend/
│   ├── app/
│   │   ├── main.py                        # FastAPI app factory + router mounting only
│   │   ├── core/
│   │   │   ├── config.py                  # Settings (pydantic-settings, reads .env)
│   │   │   ├── security.py                # password hashing
│   │   │   ├── jwt.py                     # token issue/verify
│   │   │   └── logging.py                 # structured logging setup
│   │   ├── db/
│   │   │   ├── session.py                 # engine/session factory
│   │   │   └── base.py                    # declarative base import hub
│   │   ├── models/                        # one SQLAlchemy model per file
│   │   │   ├── user.py
│   │   │   ├── department.py
│   │   │   ├── user_department.py
│   │   │   ├── document.py
│   │   │   ├── document_version.py
│   │   │   ├── document_access.py
│   │   │   ├── chat_session.py
│   │   │   └── chat_message.py
│   │   ├── schemas/                       # one Pydantic schema module per resource
│   │   │   ├── auth.py / user.py / department.py / document.py / chat.py
│   │   ├── repositories/                  # DB access only, no business logic
│   │   │   ├── user_repository.py / department_repository.py / document_repository.py / chat_repository.py
│   │   ├── services/                      # business logic, one concern per file
│   │   │   ├── auth_service.py
│   │   │   ├── rbac_service.py
│   │   │   ├── department_service.py
│   │   │   ├── document_service.py
│   │   │   ├── ingestion_service.py
│   │   │   ├── retrieval_service.py
│   │   │   ├── memory_service.py
│   │   │   └── chat_service.py
│   │   ├── api/v1/routers/                # thin controllers only
│   │   │   ├── auth_router.py / users_router.py / departments_router.py
│   │   │   ├── documents_router.py / chat_router.py
│   │   ├── providers/
│   │   │   ├── llm/
│   │   │   │   ├── base.py                # LLMProvider interface
│   │   │   │   ├── openai_provider.py
│   │   │   │   ├── ollama_provider.py
│   │   │   │   └── factory.py             # picks impl from settings
│   │   │   ├── embeddings/
│   │   │   │   ├── base.py / openai_embeddings.py / ollama_embeddings.py / factory.py
│   │   │   └── reranker/
│   │   │       ├── base.py / cross_encoder_reranker.py / factory.py
│   │   ├── storage/
│   │   │   ├── base.py                    # StorageBackend interface
│   │   │   └── local_storage.py           # (s3_storage.py added later)
│   │   ├── ingestion/
│   │   │   ├── parsers/
│   │   │   │   ├── base.py / docx_parser.py / txt_parser.py / markdown_parser.py
│   │   │   │   └── (pdf_parser.py / pptx_parser.py / ocr_parser.py — later phase)
│   │   │   ├── chunking.py                # chunk strategy, one file
│   │   │   └── pipeline.py                # orchestrates parse→chunk→embed→upsert
│   │   ├── vectorstore/
│   │   │   ├── client.py                  # Weaviate client/connection
│   │   │   ├── schema.py                  # collection definitions (DocumentChunk, UserMemory)
│   │   │   └── weaviate_repository.py     # hybrid search + upsert calls
│   │   ├── memory/
│   │   │   ├── short_term.py              # Redis buffer read/write
│   │   │   └── long_term.py               # summarization trigger + storage
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   ├── ingestion_tasks.py
│   │   │   └── memory_tasks.py
│   │   └── deps.py                        # FastAPI dependency wiring (get_db, get_current_user, require_role)
│   ├── alembic/                           # migrations
│   ├── tests/                             # pytest, mirrors app/ structure
│   ├── pyproject.toml / requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                           # one file per API resource (fetch clients)
│   │   ├── auth/                          # login, token storage, route guards
│   │   ├── features/
│   │   │   ├── admin/                     # departments, users, doc management screens
│   │   │   ├── documents/                 # my uploads, upload dialog
│   │   │   └── chat/                      # conversation list, message stream (SSE)
│   │   ├── components/                    # shared, generic UI pieces only
│   │   ├── routes/
│   │   └── main.tsx
│   ├── package.json / vite.config.ts / tailwind.config.ts
├── docker-compose.yml                     # weaviate, redis, (minio later)
├── setup.sh                               # creates venv (py3.12), installs backend+frontend deps
├── start.sh                               # starts api, celery worker, frontend (dev)
└── README.md
```

Every `.py` and `.tsx` file above gets the signature header and is scoped to one responsibility, per your instruction.

---

## 4. Core data model (SQLite → Postgres-ready)

- `users(id, email, hashed_password, full_name, role[admin|user], is_active, created_at)`
- `departments(id, name, description, created_at)`
- `user_departments(user_id, department_id)` — many-to-many
- `documents(id, title, owner_id, visibility[private|department], created_at)` — logical document, groups versions
- `document_versions(id, document_id, version_no, storage_path, file_type, checksum, is_active, uploaded_by, uploaded_at)`
- `document_department_links(document_id, department_id)` — many-to-many, only relevant when visibility=department
- `chat_sessions(id, user_id, title, created_at, updated_at)`
- `chat_messages(id, session_id, role[user|assistant], content, citations_json, created_at)`

Weaviate collections:
- `DocumentChunk` — properties: `content`, `document_id`, `document_version_id`, `owner_id`, `department_ids[]`, `chunk_index`, `is_active_version`, vector via configured embedding model.
- `UserMemory` — properties: `user_id`, `session_id`, `summary_text`, `covers_up_to_message_id`, `created_at`.

Access filter used on every retrieval call:
`is_active_version == true AND (owner_id == current_user OR department_ids INTERSECT current_user.departments)`.

---

## 5. Phases

**Phase 0 — Scaffolding & tooling** ✅ done
Repo skeleton above, `.env.example`, `setup.sh` (venv + pip/npm installs), `start.sh`, `docker-compose.yml` (Weaviate + Redis), base FastAPI app with health check, base React app with routing shell, pre-commit (ruff/black/eslint), Alembic initialized.

**Phase 1 — Auth, Users, RBAC, Departments** ✅ done
User/Department/user_departments models, bcrypt password hashing, access+refresh JWTs (`app/core/jwt.py`), `get_current_user`/`require_roles`/`require_admin` dependencies, register/login/refresh/me endpoints, department CRUD (admin-only writes, any-authenticated-user reads), user↔department assignment endpoint, `scripts/create_admin.py` to bootstrap the first admin (no public "become admin" endpoint by design). Frontend: `AuthContext`/`useAuth`, token storage + auto-refresh-on-401 fetch wrapper, `ProtectedRoute`/`AdminRoute` guards, login/register pages, admin Departments and Users screens. 47 backend tests, full live smoke test (register → login → RBAC-gated department create → assignment → refresh → 401s) all passing.

**Phase 2 — Document upload & storage** ✅ done
`StorageBackend` interface + local implementation (streams to disk, computes size/sha256 in one pass; storage keys are always UUID-generated, never derived from user input). `Document`/`DocumentVersion`/`document_departments` models. Upload endpoint: any user for private docs, admin-only for department-visibility docs targeting one or more departments; re-uploading onto an existing `document_id` adds a new version and deactivates the previous one. Access control is intentionally asymmetric so "private" stays private even from admins — read: owner, department member, or admin (department docs only); write: owner, or admin (department docs only). Download endpoint streams the active (or a specific) version with a sanitized `Content-Disposition` header (CRLF-stripped, RFC 5987 non-ASCII fallback). Frontend: `MyDocumentsPage` (upload private docs, list everything accessible, download/new-version/delete where permitted), admin `DepartmentDocumentsPage` (upload targeting departments, retarget/rename, version, delete). 71 backend tests total, full live smoke test (private upload → department upload → access denied before assignment → access granted after → re-version → download) all passing.

**Phase 3 — Ingestion pipeline** ✅ done
Celery app + `ingestion.process_document_version` task (Redis broker/backend). Parser interface + docx/txt/markdown parsers, word-based chunking with overlap (never splits a word). `VectorRepository` interface + `WeaviateChunkRepository` (schema auto-created, `replace_document_chunks` deletes-then-inserts so only the active version is ever searchable). Upload now enqueues ingestion via an injected `IngestionEnqueuer` (swappable in tests for a synchronous fake, exactly like storage/embeddings/vector-store); delete now also cleans up a document's vector chunks. `DocumentVersion` gained `status`/`status_message`/`chunk_count`, surfaced through the API and the frontend (a status badge + background polling on both document pages while anything is pending/processing). If the vector store or embedding provider is unreachable when the task runs, the version is marked `failed` with a clear message instead of the task crashing silently. `start.sh` now also launches a Celery worker.

Verified: 99 backend tests (chunking, parsers, the ingestion pipeline and Celery task in isolation via fakes, end-to-end through the API), ruff/black clean, frontend type-checks/builds/lints clean. Also ran a **real** Celery worker against a real Redis broker (no Docker needed for that — `redis-server` was available directly) in a separate process from the API: dispatch, pickup, and DB-visible status update all confirmed working across process boundaries, including the graceful-failure path when Weaviate was unreachable (Weaviate itself needs Docker, not available in this sandbox — the connection-refused error surfaced exactly as designed rather than crashing the worker).

**Phase 4 — Hybrid retrieval + re-ranker** ✅ done
`WeaviateChunkRepository.hybrid_search` (BM25+vector, `alpha` tunable) filtered to `is_active_version AND (owner_id == user OR department_ids overlaps user's departments)`. `Reranker` interface + `CrossEncoderReranker` (`sentence-transformers` CrossEncoder, model from `RERANKER_MODEL`). `retrieval_service.retrieve_chunks` composes embed-query → hybrid search (candidate set) → rerank → top-k, framework-agnostic so Phase 5's chat engine can reuse it directly. `POST /api/v1/retrieval/debug` (any authenticated user) runs the pipeline against their own RBAC scope and returns each chunk's content plus both its hybrid and rerank scores — no LLM call, just inspection.

Verified: 109 backend tests (10 new: retrieval_service unit tests with fakes covering owner/department/other-user scoping, top_k truncation, score plumbing; debug-endpoint integration tests including a 401 and a 422 on out-of-range `top_k`), ruff/black clean. Also ran the **real** pipeline end-to-end against Weaviate Cloud: uploaded two topically-distinct private documents (employee benefits vs. engineering/retrieval-infra), waited for real Celery + sentence-transformers ingestion, then queried `/retrieval/debug` twice — each query's own document came back first with a clearly separated positive cross-encoder score (e.g. 0.51 vs. −11.28), confirming the reranker actually discriminates rather than just passing through hybrid order. Confirmed RBAC for real too: a second, unrelated user querying the same terms got back `results: []`.

**Phase 5 — Chat engine + short-term memory** ✅ done
`LLMProvider` interface + `OpenAILLMProvider`/`OllamaLLMProvider` (streaming chat completions), `ChatSession`/`ChatMessage` models (owner-only, no department sharing). Short-term memory (`app/memory/short_term.py`) is a Redis list per session capped at `SHORT_TERM_MEMORY_TURNS`; Redis is an accelerator, not the source of truth — a miss/connection error transparently falls back to the last-N `chat_messages` rows and re-warms the cache, so chat still works with Redis off. `chat_service.stream_reply` persists the user message, calls Phase 4's `retrieve_chunks` for grounding (swallowing retrieval failures — you still get an answer, just ungrounded), assembles system-prompt + short-term buffer, streams the LLM token-by-token over SSE (`POST /api/v1/chat/sessions/{id}/messages`, `data: {"type": "token"|"done"|"error", ...}`), then persists the assistant reply with citations. Solves a real FastAPI gotcha: `Depends(get_db)` closes before an SSE generator finishes, so `stream_reply` takes a `session_factory` (`app/deps.py:get_session_factory`) and manages its own DB session for the stream's lifetime. Frontend: `ChatPage` — session sidebar (create/select/delete) + message thread with streaming bubble, citations shown per message, `parseSseStream` util for reading the event stream.

Verified: 125 backend tests (16 new: session CRUD/ownership, SSE streaming end-to-end with a fake LLM provider recording every prompt it was called with — used to confirm short-term memory actually reaches the second turn's messages — citations persisted and shaped correctly). Caught and fixed a real bug in review: `ChatMessageRead.citations` used `Field(alias=...)`, which made FastAPI serialize the *ORM column name* (`citations_json`) instead of the intended API field (`citations`) — the initial SSE-only test didn't catch it since the `done` event's citations are built directly in the service, not through this schema; added a persisted-history assertion and fixed with `validation_alias` (input-only) instead of `alias` (both directions). Ran the **real** pipeline end-to-end: real OpenAI streaming + real Weaviate Cloud retrieval through curl (grounded, cited answer), then drove the actual browser UI — uploaded a doc, asked about it, watched the reply stream in with its citation, asked a pronoun-referencing follow-up ("where is *that* party located?") and got the right answer back from short-term memory, then reloaded the page and confirmed full history (including citations) survives from the server, not just local state.

**Phase 6 — Long-term memory** ✅ done
`memory.summarize_session` Celery task (thin wrapper, mirrors `ingestion_tasks.py`) runs `memory_service.summarize_session_memory`: once a session has more messages than the short-term buffer keeps (`SHORT_TERM_MEMORY_TURNS`), folds whatever's newly fallen out of that window into one rolling, LLM-generated summary per session — tracked via `covers_up_to_message_id` so a steady-state conversation folds in ~1 new exchange per run, not the whole history each time. `retrieval_service.retrieve_context` (new, alongside the unchanged Phase 4 `retrieve_chunks` used by the debug endpoint) pulls the user's own memory summaries into the *same* candidate pool as document chunks before reranking, so a memory can genuinely outrank a document chunk or vice versa — the cross-encoder scores both against the query on equal footing, not as a bolted-on extra. Citations now carry a `source: "document" | "memory"` discriminator; the system prompt labels each numbered source "(from your chat history)" or "(from a document)" so the model's inline `[1]`/`[2]` citations line up.

`MemoryRepository` is a swappable interface (same pattern as `EmbeddingProvider`/`LLMProvider`), picked via `MEMORY_BACKEND`. Originally spec'd as a second Weaviate collection (`UserMemory`) — implemented and kept as the `"weaviate"` option — but your Weaviate Cloud sandbox is capped at **1 collection total** (`DocumentChunk` already uses it; creating a second gets `429 USAGE_LIMIT_EXCEEDED`). Per your call, default is now `"sqlite"`: a plain `chat_memories` table (`session_id, user_id, summary_text, vector_json, covers_up_to_message_id`), with `search_memories` doing brute-force cosine similarity in Python — entirely reasonable at this scale (one row per session per user) and swaps back to `"weaviate"` (or a real vector DB later) via one setting, no caller changes.

Verified: 140 backend tests (8 new dedicated to the real `SqliteMemoryRepository` — cosine-similarity ranking, owner scoping, upsert-replaces-existing, safe-delete-of-nothing — since every other test exercises `FakeMemoryRepository` instead; plus summarization-service and end-to-end router tests covering threshold-triggered summarization, idempotency when nothing new has fallen out, and memory citations appearing in a reply), ruff/black clean. Ran the **real** pipeline end-to-end with `SHORT_TERM_MEMORY_TURNS` temporarily lowered via env var (not `.env`): sent "my name is Rahul, favorite language is Python," then enough turns to push that exchange out of the short-term window, confirmed a real OpenAI call produced the rolling summary and a real sentence-transformers embedding landed in `chat_memories`, then — with that fact no longer in the short-term buffer — asked "what's my name and favorite language?" and got the correct answer back, sourced and cited as `{"source": "memory", "session_id": ...}`, purely from long-term memory. Confirmed session deletion removes its `chat_memories` row too.

**Phase 7 — Hardening for scale** ✅ done
- **DB indexing**: `Document.owner_id`, `ChatSession.user_id`, `ChatMessage.session_id` — all filtered-on-every-request FKs with no existing index (`DocumentVersion.document_id` already covered by its unique constraint's leftmost prefix).
- **Connection pooling**: `pool_pre_ping=True` always on; `pool_size`/`max_overflow`/`pool_recycle` apply only when `DATABASE_URL` isn't SQLite (SQLite's own pool doesn't accept those args — dormant until Phase 8's Postgres switch).
- **Pagination**: `limit`/`offset` (shared `PageParams`) + `X-Total-Count` header on documents, departments, users, chat sessions, chat messages — response body stays a plain list, so existing clients aren't broken; frontend updated to request `limit=200` explicitly everywhere until a real pager UI exists, so lists don't silently truncate.
- **Rate limiting**: `slowapi`, per-client-IP, `100/minute` default, `10/minute` on register/login (brute-force surface), `20/minute` on chat send-message (LLM-cost surface). `swallow_errors=True` (fails open if the storage backend's unreachable) and in-memory storage by default (`RATE_LIMIT_STORAGE_URI`, swap to `redis://` once running >1 worker).
- **Caching hot reads**: the department directory (read on nearly every admin/document screen, changes rarely) — one Redis key, full list cached, sliced in Python per page, invalidated on any write. Same graceful-degradation contract as short-term memory: Redis down → every read just re-hits the DB.
- **Background-task idempotency**: already true by construction (delete-then-insert chunk replacement, safe status re-transitions) — added a test that runs `process_document_version` twice for the same version and asserts identical end state, rather than bolting on Celery-level auto-retry (tried it first; `self.retry()` unconditionally re-raises outside a real worker/broker context, which broke every direct-call unit test in the existing suite — reverted rather than rewrite the test harness or accept real `time.sleep()`-based retries in tests).
- **Structured logging + metrics**: `LOG_FORMAT=text|json`, every line correlated by request ID (contextvar, `X-Request-ID` request/response header); Prometheus `/metrics` (`http_requests_total`, `http_request_duration_seconds`, labeled by method/path-template/status). Built as one raw ASGI middleware, deliberately not Starlette's `BaseHTTPMiddleware` — that class runs the downstream app in a separate task (breaks the request-ID contextvar's propagation into handlers) and buffers streaming responses (breaks the chat SSE endpoint).
- **Load-test plan**: `locustfile.py` + `LOAD_TESTING.md` — weighted toward the real usage shape (listing/retrieval far more common than upload/chat), with guidance on what each endpoint's latency profile should look like and how to size the user count toward the traffic target.

Verified: 159 backend tests (16 new — pagination headers/slicing on every paginated endpoint, cache-invalidation-on-write proven with a monkeypatched fake Redis client, the observability stack end-to-end including a real 429 after exceeding both the default and the stricter auth limit, and the ingestion-task idempotency test), ruff/black clean, frontend builds clean. Caught and fixed a real bug via testing, not inspection: `headers_enabled=True` on the rate limiter made `@limiter.limit()`'s decorator try to inject `X-RateLimit-*` headers directly onto route return values — which crashed instantly for every route returning a typed Pydantic model (register/login/send-message) instead of a raw `Response`, because the decorator's header-injection runs before FastAPI's own `response_model` serialization. Invisible in a code read; the moment tests exercised `user_tokens`/`admin_tokens` (i.e. almost every existing test), 55 of them failed. Fixed with `headers_enabled=False` (429 enforcement doesn't depend on it). Also added a autouse test fixture resetting slowapi's process-wide in-memory limiter storage between tests — without it, the ~160-test suite would eventually 429 unrelated later tests just from cumulative request count. Ran the **real** stack end-to-end: confirmed `X-Request-ID` on every response, real Prometheus counters correctly grouped by path template, real pagination (`X-Total-Count` header on a 3-document list), real Redis-backed department cache (watched the key actually appear/disappear/repopulate via `redis-cli` across create→invalidate→re-read), a real 429 on the login endpoint's stricter limit, and a real (brief, 3-user) Locust run against the live server with zero failures across register/login/departments/documents/upload.

**Phase 8 — Postgres migration path** ✅ done
`psycopg[binary]>=3.1,<4` added (SQLAlchemy 2.0's recommended modern driver). No ORM/query changes needed — `app/db/session.py`'s dialect branch (Phase 7) already routes pool config away from SQLite and toward Postgres based purely on `DATABASE_URL`'s scheme. `docker-compose.yml` gains a `postgres` service (port 5433, not 5432 — avoids colliding with a Postgres already running natively on a dev machine). Cutover steps documented in `README.md` ("Switching to Postgres").

Verified against a **real, live Postgres 16** instance (not just a read-through of the migration files): all 6 Alembic migrations applied cleanly in one shot, then a full app smoke test against it — register → login → document upload → admin department create → user↔department assignment (the many-to-many junction table) → paginated list (`X-Total-Count` header) → a real OpenAI-backed chat turn round-tripping the `chat_messages.citations_json` column (Postgres `json` type) and the `role` enum column correctly. Postgres's stricter timezone-aware timestamps showed up correctly in every response (`...899520Z` vs SQLite's bare datetimes) — a nice side-effect confirmation that `DateTime(timezone=True)` was the right call back in Phase 1.

**Real finding, not a Phase 8 bug**: reusing the same Weaviate Cloud instance across a fresh Postgres database (auto-increment IDs restarting from 1) surfaced stale citations from old SQLite-era documents that happened to share the same integer IDs — Weaviate chunks are keyed by this app's own `owner_id`/`document_id`, which aren't unique across separate SQL databases. Documented in `README.md`'s cutover section: reindex (or start fresh) Weaviate when cutting over to a genuinely new database, don't just swap `DATABASE_URL` and assume isolation.

**Phase 9 — Expansion (deferred scope)**

Parsers ✅ done — PDF, PPTX, XLSX, and OCR (scanned PDF pages + standalone images) added behind the existing `Parser` interface, zero changes to `ingestion_service`/callers.
- **PDF** (`pdf_parser.py`): `pypdf` direct text extraction per page; a page with under ~20 extracted characters is treated as scanned/image-only and falls back to OCR for that page only (`pdf2image` renders just that page, `pytesseract` reads it) — a mostly-text PDF with a few scanned pages doesn't pay to rasterize every page.
- **PPTX** (`pptx_parser.py`): `python-pptx`, text frames + table cells per slide.
- **XLSX** (`xlsx_parser.py`): `openpyxl`, each sheet a labeled block, each row a `|`-joined line.
- **Images** (`image_parser.py`): standalone PNG/JPG/JPEG straight through `pytesseract`.
- OCR needs two system binaries (`tesseract`, and poppler's `pdftoppm` for the PDF path) — same graceful-failure path as any other parser error if either's missing: `ingestion_service` already catches and marks the version `FAILED` with a message instead of crashing the worker, so no new error-handling was needed.

Verified: 168 backend tests (13 new parser unit tests — real files built in-memory via the same libraries used to parse them, `reportlab`/`python-pptx`/`openpyxl`/Pillow, including two real OCR round-trips guarded by `skipif` on the system binaries' availability; plus 2 new upload-to-`ready` integration tests proving the extensions are wired through the real API, not just the parser layer), ruff/black clean. Caught two stale test assumptions from before these extensions existed: one test used `"pdf"` as its example of an *unsupported* extension (now supported — updated to a still-genuinely-unknown one) in each of `test_parsers.py` and `test_ingestion_service.py`. Ran the **real** pipeline end-to-end for all four types against the live stack (real Celery, real sentence-transformers embeddings, real Weaviate Cloud): generated an actual PDF, PPTX, XLSX, and a scanned-style PNG (text rendered as an image, no text layer — a genuine OCR case, not a shortcut), uploaded all four, watched them reach `ready`, then queried `/retrieval/debug` for content specific to each and got back the exact right document with the exact right extracted text every time — including the OCR'd PNG's "Invoice Total: 4820 dollars" recognized correctly. Frontend upload `accept` attributes and labels updated to match.

Remaining deferred: S3/GCS `StorageBackend` implementation, optional Cohere reranker implementation, optional SSO provider, optional department-manager role.

---

**Phase 10 — Full format coverage + structured chunk metadata** ✅ done

Two things bundled together because the second makes the first worth doing properly: every format on the user's list, and — for presentations/spreadsheets specifically — preserving structure (slide/sheet/row/cell, tables, notes, hyperlinks) instead of collapsing everything to flat text like Phase 9's first pass did.

**Architecture change** (once, shared by every parser):
- `Parser.extract_text(file) -> str` becomes `Parser.extract_elements(file) -> list[ParsedElement]`, where `ParsedElement = {content: str, metadata: dict}`. A plain-text format (txt, csv, json, ...) yields one element with `metadata={}`; a structured format yields one element per structural unit (PDF page, PPTX slide/notes/table, XLSX sheet/table/row-group, email header vs. body, ...).
- `chunking.py` gains `chunk_elements()`: chunks each element's content independently (so a chunk never straddles a slide/sheet/page boundary) and carries that element's metadata onto every chunk derived from it, alongside the existing word-based `chunk_text()` used per-element.
- `DocumentChunk` (Weaviate schema) gains a `metadata_json` property. `VectorRepository.replace_document_chunks`/`RetrievedChunk`/`hybrid_search` all thread a `metadata: dict` through. `retrieval_service`'s `RankedChunk`/`ContextItem` and chat's citation dicts do the same — so "which slide/sheet/page did this answer come from" is finally answerable, not just "which document."

**Format matrix** (✅ shipping this phase / ❌ genuinely skipped, per your call — no LibreOffice install):

| Category | Format | Plan |
|---|---|---|
| Core docs | `.pdf` | ✅ already done (Phase 9), gains page metadata |
| | `.docx` | ✅ extend existing parser: tables + headers/footers, not just paragraphs |
| | `.doc` (legacy binary) | ❌ skipped — no reliable pure-Python path, LibreOffice declined |
| | `.rtf` | ✅ `striprtf` (pure Python) |
| | `.odt` | ✅ `odfpy` (pure Python) |
| | `.txt` | ✅ already done |
| | `.md`, `.markdown` | ✅ already done; `.markdown` extension alias added |
| | `.htm`/`.html`, `.xhtml` | ✅ `BeautifulSoup4`, text + preserved heading structure |
| | `.mhtml`/`.mht` | ✅ stdlib `email` (MIME-wrapped HTML) + the HTML parser |
| | `.xml` | ✅ stdlib `xml.etree`, element-path-aware |
| | `.epub` | ✅ `ebooklib` + BeautifulSoup for each chapter's HTML |
| | `.json`, `.jsonl` | ✅ stdlib `json` |
| | `.yaml`/`.yml` | ✅ `PyYAML` |
| Presentations | `.pptx` | ✅ rewritten for real structure: slide number, title, per-textbox content, tables (with cell grid preserved in metadata), speaker notes, hyperlink URLs, and a note per image/chart shape (alt text + position — not OCR'd in this pass) |
| | `.ppt` (legacy binary) | ❌ skipped, same reasoning as `.doc` |
| | `.odp` | ✅ `odfpy` |
| | `.ppsx`/`.pps` | ✅ `.ppsx` registered to the same OOXML-based PPTX parser (it's the same package format); `.pps` (legacy binary) skipped with `.ppt` |
| Spreadsheets | `.xlsx`, `.xlsm` | ✅ rewritten for real structure: one element per (sheet, contiguous table region), each row tagged with its 1-indexed row number and column letters, formulas preserved verbatim (`data_only=False`) alongside their calculated value where cached, table boundaries in metadata |
| | `.xls` (legacy binary) | ✅ `xlrd` (pure Python, still fully maintained for legacy `.xls` specifically) |
| | `.csv`, `.tsv` | ✅ stdlib `csv`, same row/column-aware element shape as XLSX |
| | `.ods` | ✅ `odfpy` |
| Images | `.png`, `.jpg`/`.jpeg` | ✅ already done |
| | `.tif`/`.tiff`, `.bmp`, `.webp`, `.gif` | ✅ Pillow already reads all of these natively — just registering the extensions |
| | `.heic` | ✅ `pillow-heif` plugin |
| Email | `.eml` | ✅ stdlib `email` |
| | `.msg` | ✅ `extract-msg` (pure Python) |
| | `.mbox` | ✅ stdlib `mailbox`, one element per message |
| | `.pst` | ✅ `libpst`'s `readpst` CLI (small, brew-installed) converts to `.mbox` first, then the mbox parser runs — same "shell out, then reuse an existing parser" pattern as nothing else in this codebase, but the only sane option for a container format this complex |
| Structured data | (all covered above: json/jsonl/yaml/csv/tsv/xml) | |
| Web | (all covered above: html/xhtml/mhtml/xml/md) | |

**Docling considered, rejected**: asked directly whether to switch to Docling for the harder cases (PDF tables, PPTX/XLSX structure). `pip install docling --dry-run` showed it forces `numpy` to 2.2.6 (via `pandas-3.0.6`, which requires `numpy>=2`), which breaks the Phase 9 `numpy<2`/`torch==2.2.2` pin `sentence-transformers` needs on this Intel Mac (PyPI's last macOS-x86_64 torch wheel is ABI-locked to NumPy 1.x). Went with hand-rolled parsers plus `pdfplumber` for PDF tables instead (lightweight, `pdfplumber --dry-run` confirmed no numpy/torch conflict) — satisfies the two priorities the user actually named (table fidelity, formula fidelity) without the dependency risk.

Verified: 190 backend tests (35 in `test_parsers.py` alone — one real-file round-trip per parser, built with the same library that parses it wherever a writer exists: `python-docx`, `python-pptx`, `openpyxl`, `xlwt`, `odfpy`, `ebooklib`, stdlib `email`/`mailbox`, etc.; `MsgParser` and the `PstParser` happy path are the only exceptions, since no writer library exists for `.msg`/`.pst` — `.msg` is covered by the factory registration test and `.pst`'s only unit-tested path is the readpst-missing error, its happy path verified live below), ruff/black clean.

Three real bugs caught during test-writing, not just fixture problems:
- `odt_parser.py`: `child.getAttribute("outline-level")` raised `ValueError` on every real heading — odfpy's `getAttribute` normalizes allowed-attribute names by stripping hyphens internally but does *not* strip them from the caller's argument, so it needs `"outlinelevel"`. Would have crashed on every `.odt` file with a heading.
- `pptx_parser.py`: `shape is title_shape` was always `False` — `slide.shapes.title` returns a fresh wrapper object on every access, not a cached instance, so identity comparison silently never matched and titles were always mis-tagged as plain textboxes. Fixed by comparing `shape.shape_id` instead.
- `image_parser.py`: pytesseract whitelists a fixed set of `Image.format` values and rejects anything else outright — a HEIC file decoded fine by Pillow still raised `TypeError: Unsupported image format/type` because its format tag was `"HEIF"`. Fixed with `.convert("RGB")` before OCR, which drops the source format tag; every real HEIC upload would otherwise have failed ingestion.

Live end-to-end pass against the real stack (real Celery worker, real sentence-transformers embeddings, real Weaviate Cloud, real LLM chat): built 19 representative files covering every category — pdf (with a table), docx (table + header), pptx (chart + speaker notes), xlsx (formula), xls, csv, tsv, json, jsonl, yaml, xml, html, rtf, odt, ods, odp, epub, eml, mbox — uploaded all 19 through the real API, all reached `ready` with nonzero chunk counts. Asked the chat endpoint a question spanning several of them and got back a correct streamed answer with citations carrying real structural metadata per source: `{"page": 1, "kind": "text"}` for the PDF, `{"slide": 1, "kind": "chart", ...}` for the PPTX, `{"kind": "table", "table_index": 0}` for the DOCX, `{"heading": "Details", "level": 2}` for the HTML, `{"key": "price"}` for the YAML — confirming the metadata thread works end-to-end from parser through Weaviate through retrieval through chat citations, not just at the unit level. Test documents and the test user were deleted afterward; no lasting state left in the shared Weaviate Cloud instance or local DB.

(Aside, unrelated to this phase's code: hit a `billiard`/prefork pool bug spawning the Celery worker on this macOS setup — `ValueError: not enough values to unpack` on every task. Worked around with `--pool=solo`, which is an environment/tooling quirk, not a regression from this work.)

Each phase = its own PR-sized chunk of work, reviewed and runnable end-to-end before moving on.

---

## 6. Open items I'll confirm again at the start of the relevant phase (not blocking now)
- Exact chunk size/overlap and cross-encoder model name (I'll propose defaults in Phase 3/4, you can override).
- Exact `.env` variable names (I'll propose a full `.env.example` in Phase 0 for your review).
- Whether admin document uploads targeting "no department" means org-wide-visible or admin-only until assigned — I'll default to **admin-only draft until at least one department is attached**, flag it explicitly when I get there.

---

Next step: I'll scaffold **Phase 0** (repo structure, `setup.sh`, `start.sh`, docker-compose, empty FastAPI/React apps, `.env.example`) so you have something runnable, then proceed phase by phase. Let me know if you want to adjust anything above before I start.
