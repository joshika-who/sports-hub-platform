#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Starting Sports Hub Platform ==="

# 1. Backend
cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
  echo "[Backend] Creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

echo "[Backend] Starting FastAPI on http://localhost:8000 ..."
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 2. Frontend
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
  echo "[Frontend] Installing npm dependencies..."
  npm install
fi

echo "[Frontend] Starting Next.js on http://localhost:3000 ..."
npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT
wait

