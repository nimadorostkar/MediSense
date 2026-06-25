#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Run MediSense — backend (FastAPI) + frontend (Vite React) together.
#
#   ./run.sh           Local dev: uvicorn + SQLite (zero-setup) with hot reload
#   ./run.sh docker    Backend via Docker (Postgres + pgvector + Redis) + Vite
#
# Ctrl-C stops everything. Frontend → http://localhost:5173, Backend → :8787.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
MODE="${1:-local}"
BACKEND_PORT=8787
FRONTEND_PORT=5173

pids=()

cleanup() {
  echo
  echo "→ Stopping MediSense…"
  for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done
  if [ "$MODE" = "docker" ]; then (cd "$BACKEND" && docker compose down) || true; fi
  exit 0
}
trap cleanup INT TERM

port_busy() { lsof -ti:"$1" >/dev/null 2>&1; }

# ── Pre-flight: refuse to double-start on busy ports ─────────────────────────
if [ "$MODE" = "local" ] && port_busy "$BACKEND_PORT"; then
  echo "✗ Port $BACKEND_PORT is already in use (a backend is running)."
  echo "  Stop it first:  cd backend && docker compose down   (or kill the uvicorn process)"
  exit 1
fi
if port_busy "$FRONTEND_PORT"; then
  echo "✗ Port $FRONTEND_PORT is already in use (a frontend is running). Stop it and retry."
  exit 1
fi

# ── Backend ──────────────────────────────────────────────────────────────────
if [ "$MODE" = "docker" ]; then
  echo "▶ Backend: Docker (Postgres + pgvector + Redis)…"
  (cd "$BACKEND" && docker compose up -d --build)
else
  echo "▶ Backend: uvicorn + SQLite (hot reload)…"
  cd "$BACKEND"
  [ -d .venv ] || python3 -m venv .venv
  # shellcheck disable=SC1091
  . .venv/bin/activate
  python -c "import fastapi" 2>/dev/null || pip install -q -r requirements.txt
  uvicorn app.main:app --reload --port "$BACKEND_PORT" &
  pids+=($!)
fi

printf "  waiting for backend"
for _ in $(seq 1 40); do
  if curl -sf "http://localhost:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    echo " — ready"; break
  fi
  printf "."; sleep 1
done

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "▶ Frontend: Vite dev server…"
cd "$FRONTEND"
[ -d node_modules ] || npm install
npm run dev &
pids+=($!)

cat <<EOF

  ✓ MediSense is running
      Frontend   http://localhost:$FRONTEND_PORT
      Backend    http://localhost:$BACKEND_PORT   (API docs: /docs)
      Mode       $MODE

  Press Ctrl-C to stop.

EOF

wait
