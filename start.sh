#!/usr/bin/env bash
# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Dev entrypoint: brings up Redis (docker compose if Docker's available,
# otherwise the native redis-server binary directly — no Docker required)
# when backend/.env has CELERY_ENABLED=true, then runs the FastAPI backend,
# a Celery worker (ingestion tasks), and the React frontend dev server in
# the foreground. Ctrl+C stops everything.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "ERROR: backend virtualenv not found. Run ./setup.sh first." >&2
  exit 1
fi

# CELERY_ENABLED gates both Redis (docker compose) and the Celery worker
# below — read straight from backend/.env so this script doesn't need its
# own copy of the flag.
CELERY_ENABLED="$(grep -E '^CELERY_ENABLED=' "$BACKEND_DIR/.env" 2>/dev/null | cut -d= -f2- | tr '[:upper:]' '[:lower:]')"
CELERY_ENABLED="${CELERY_ENABLED:-true}"

pids=()

if [ "$CELERY_ENABLED" = "true" ]; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "==> Starting Weaviate + Redis (docker compose)"
    if ! (cd "$SCRIPT_DIR" && docker compose up -d); then
      echo "==> docker compose failed; continuing without Weaviate/Redis." >&2
    fi
  elif redis-cli -h localhost -p 6379 ping >/dev/null 2>&1; then
    echo "==> Redis already running on localhost:6379, using it"
  elif command -v redis-server >/dev/null 2>&1; then
    echo "==> Docker not available; starting Redis directly (native binary, no Docker needed)"
    redis-server --port 6379 --daemonize no --save "" --appendonly no &
    pids+=("$!")
    for _ in $(seq 1 20); do
      redis-cli -h localhost -p 6379 ping >/dev/null 2>&1 && break
      sleep 0.5
    done
  else
    echo "==> Neither Docker nor a local redis-server binary found; skipping Redis startup." >&2
    echo "    Ingestion won't work until Redis is reachable some other way (or set CELERY_ENABLED=false)." >&2
  fi
else
  echo "==> CELERY_ENABLED=false in backend/.env; skipping Redis + Celery worker."
fi

cleanup() {
  echo
  echo "==> Shutting down..."
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "==> Starting backend (FastAPI) on http://localhost:8000"
(
  cd "$BACKEND_DIR"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  exec uvicorn app.main:app --port 8000
) &
pids+=("$!")

if [ "$CELERY_ENABLED" = "true" ]; then
  echo "==> Starting Celery worker (ingestion tasks)"
  (
    cd "$BACKEND_DIR"
    # shellcheck disable=SC1091
    source .venv/bin/activate
    # --pool=solo: celery's default prefork pool crashes on this macOS/Python
    # 3.12/billiard combo ("ValueError: not enough values to unpack" in
    # fast_trace_task) as soon as a task is dispatched. solo runs tasks
    # sequentially in the main process — fine for dev, not for concurrency.
    exec celery -A app.workers.celery_app worker --loglevel=info --pool=solo
  ) &
  pids+=("$!")
fi

echo "==> Starting frontend (Vite) on http://localhost:5173"
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --port 5173
) &
pids+=("$!")

wait
