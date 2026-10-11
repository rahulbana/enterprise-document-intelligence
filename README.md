<!--
Name: Rahul Singh Bana
Email: bana.saa@gmail.com
LinkedIn: https://www.linkedin.com/in/rahulsinghbana
-->

# Document Intelligence

Multi-user, RBAC-secured document chat platform with hybrid retrieval
(BM25 + vector via Weaviate), a pluggable re-ranker, and layered short-term /
long-term chat memory. LLM and embedding providers switch between OpenAI and
Ollama via `.env`.


## Stack

- **Backend**: FastAPI, SQLAlchemy 2.0, Alembic, SQLite (Postgres-ready),
  Celery + Redis (from Phase 3), Weaviate client (from Phase 4).
- **Frontend**: React + Vite + TypeScript + Tailwind CSS v4, React Router.
- **Infra**: Weaviate + Redis via Docker Compose.

## Prerequisites

- Python 3.12 on `PATH` as `python3.12`
- Node.js 20+ and npm
- Docker (optional for Phase 0; required from Phase 3+ for Redis/Weaviate)

## Quickstart

```bash
./setup.sh   # creates backend/.venv, installs deps, seeds .env files, runs migrations
./start.sh   # starts Weaviate+Redis (if Docker present), FastAPI on :8000, Vite on :5173
```

Then open http://localhost:5173 — the home page pings `GET /api/v1/health`
on the backend and shows the result.

## Manual setup (equivalent to setup.sh)

```bash
# Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
alembic upgrade head

# Frontend
cd ../frontend
npm install
cp .env.example .env.local
```

## Running tests / lint

```bash
# Backend
cd backend && source .venv/bin/activate
pytest
ruff check .
black --check .

# Frontend
cd frontend
npm run lint
npm run build   # tsc -b && vite build
```

## Pre-commit hooks (backend)

The `.pre-commit-config.yaml` lives at `document-intelligence/` but the git
repo root is one level up, so install/run it explicitly:

```bash
pip install pre-commit   # once, anywhere on PATH
pre-commit install -c document-intelligence/.pre-commit-config.yaml
```

## Switching to Postgres (Phase 8+)

SQLite is dev-only from Phase 8 on. To cut over:

```bash
# 1. Get a Postgres instance — docker-compose, a local install, or a managed
#    one. Via docker-compose (adds a "postgres" service on 5433, not 5432,
#    to avoid colliding with a Postgres already running natively):
docker compose up -d postgres

# 2. Point DATABASE_URL at it (backend/.env) — psycopg3 driver, already a
#    dependency:
DATABASE_URL=postgresql+psycopg://document_intelligence:document_intelligence@localhost:5433/document_intelligence

# 3. Run migrations against the new database — same command, no changes:
cd backend && source .venv/bin/activate && alembic upgrade head
```

Nothing else changes: the ORM layer, connection pooling (`DB_POOL_SIZE`/
`DB_MAX_OVERFLOW`/`DB_POOL_RECYCLE_SECONDS`, dormant under SQLite), and
every query are dialect-agnostic. Verified for real against a live
Postgres 16 instance (all 6 migrations, plus a full register → login →
upload → department → chat smoke test) — see `PLAN.md`'s Phase 8 entry.

**One thing to know before cutting a real environment over**: Weaviate
chunks are keyed by this app's own auto-increment integer IDs
(`owner_id`, `document_id`), not anything Postgres-specific — but if you
point at a *fresh* database (IDs restarting from 1) while re-using an
*existing* Weaviate instance that already has chunks from a previous
environment, old chunks can resurface as false-positive citations for
unrelated documents that happen to reuse the same IDs. Reindex Weaviate
(or start it fresh too) when cutting over to a new database, don't just
swap `DATABASE_URL`.

## Project layout

```
document-intelligence/
├── backend/    # FastAPI app (see backend/app for module layout)
├── frontend/   # React + Vite app
├── docker-compose.yml
├── setup.sh
├── start.sh
└── PLAN.md
```

Every source file carries a signature header and is scoped to a single
responsibility — see `PLAN.md` §3 for the intended module layout as later
phases fill it in.
