#!/usr/bin/env bash
# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# One-time (or repeatable) environment setup: creates the backend virtualenv
# with Python 3.12, installs backend + frontend dependencies, and seeds .env
# files from their .env.example templates if they don't exist yet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"

echo "==> Checking for $PYTHON_BIN"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON_BIN not found on PATH. Install Python 3.12 first." >&2
  exit 1
fi

echo "==> Creating backend virtualenv at $VENV_DIR"
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  echo "    (already exists, skipping)"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Installing backend dependencies"
pip install --upgrade pip -q
pip install -r "$BACKEND_DIR/requirements.txt" -r "$BACKEND_DIR/requirements-dev.txt" -q

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "==> Creating backend/.env from .env.example"
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
else
  echo "==> backend/.env already exists, leaving it untouched"
fi

deactivate

echo "==> Installing frontend dependencies"
(cd "$FRONTEND_DIR" && npm install)

if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
  echo "==> Creating frontend/.env.local from .env.example"
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
else
  echo "==> frontend/.env.local already exists, leaving it untouched"
fi

echo "==> Applying database migrations"
(cd "$BACKEND_DIR" && source .venv/bin/activate && alembic upgrade head && deactivate)

cat <<'EOF'

Setup complete.

Next steps:
  1. Review backend/.env and frontend/.env.local (API keys, model names).
  2. Start infra + app with: ./start.sh
EOF
