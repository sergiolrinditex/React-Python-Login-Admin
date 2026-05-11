#!/usr/bin/env bash
# scripts/dev-restart.profile.sh
#
# Hilo People — stack-specific dev profile.
# Slice: P00-S01-T001 — Repo scaffold + scripts + env.
#
# This file is sourced by scripts/dev-restart.sh, which exports these
# variables before sourcing this profile:
#
#   ROOT_DIR          — absolute path to the repo root
#   BACK_LOG          — path for backend stdout/stderr log
#   FRONT_LOG         — path for frontend stdout/stderr log
#   BACK_PID_FILE     — path for backend PID file
#   FRONT_PID_FILE    — path for frontend PID file
#
# Required functions (contract enforced by scripts/dev-restart.sh):
#   back_health   → exit 0 if backend /health returns 200
#   back_start    → start uvicorn in background, write PID to BACK_PID_FILE
#   back_url      → echo human-readable backend URL
#   front_health  → exit 0 if Vite dev server responds to HTTP HEAD
#   front_start   → start Vite in background, write PID to FRONT_PID_FILE
#   front_url     → echo human-readable frontend URL
#   db_health     → 0=up, 1=down, 2=unknown (pg_isready)
#   db_reset      → migrate/seed; in P00 only warns (no Docker yet)

# Use env values if set (from .env or shell export), else defaults from STACK_PROFILE.
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# ---------------------------------------------------------------------------
# Health probes
# ---------------------------------------------------------------------------

back_health() {
  # Exit 0 if /health returns HTTP 200.
  curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null
}

front_health() {
  # Exit 0 if the Vite dev server is accepting connections.
  curl -sfI "http://localhost:${FRONTEND_PORT}/" >/dev/null
}

db_health() {
  # Exit 0 if PostgreSQL is accepting connections; 1 if down; 2 if unknown.
  if command -v pg_isready >/dev/null 2>&1; then
    pg_isready -h localhost -p 5432 >/dev/null 2>&1
    return $?
  fi
  # pg_isready not installed — report unknown.
  return 2
}

# ---------------------------------------------------------------------------
# URL labels (for status table in dev-restart.sh)
# ---------------------------------------------------------------------------

back_url() {
  printf 'http://localhost:%s' "${BACKEND_PORT}"
}

front_url() {
  printf 'http://localhost:%s' "${FRONTEND_PORT}"
}

# ---------------------------------------------------------------------------
# Startup functions
# ---------------------------------------------------------------------------

back_start() {
  # Kill any orphan process already occupying the backend port.
  stop_orphan_on_port "${BACKEND_PORT}" "backend"

  log "Starting uvicorn on :${BACKEND_PORT} ..."
  (
    cd "${ROOT_DIR}/backend" && \
    uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${BACKEND_PORT}" \
      --reload \
      > "${BACK_LOG}" 2>&1 &
    echo $! > "${BACK_PID_FILE}"
  )

  # Wait for /health to respond (timeout 20 s).
  if ! wait_for back_health 20 "backend"; then
    warn "Backend did not respond within 20s. Check ${BACK_LOG} for errors."
    return 1
  fi
  log "Backend up at $(back_url)"
}

front_start() {
  # Kill any orphan process already occupying the frontend port.
  stop_orphan_on_port "${FRONTEND_PORT}" "frontend"

  log "Starting Vite dev server on :${FRONTEND_PORT} ..."
  (
    cd "${ROOT_DIR}/frontend" && \
    npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}" \
      > "${FRONT_LOG}" 2>&1 &
    echo $! > "${FRONT_PID_FILE}"
  )

  # Wait for Vite to respond (timeout 30 s — npm cold-start can be slow).
  if ! wait_for front_health 30 "frontend"; then
    warn "Frontend did not respond within 30s. Check ${FRONT_LOG} for errors."
    return 1
  fi
  log "Frontend up at $(front_url)"
}

# ---------------------------------------------------------------------------
# DB reset — delegates to Docker Compose in P00-S02-T001+
# ---------------------------------------------------------------------------

db_reset() {
  warn "DB reset profile is pending Step 0.2 (docker-compose services — P00-S02-T001+)."
  warn "To reset manually: docker compose down -v && docker compose up -d postgres && alembic upgrade head"
  return 0
}
