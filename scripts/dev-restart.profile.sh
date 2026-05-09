#!/usr/bin/env bash
# scripts/dev-restart.profile.sh
#
# Stack profile: React/Vite (TypeScript) + FastAPI (uvicorn) + Postgres (alembic).
# Aligned with docs/source-of-truth/STACK_PROFILE.yaml:
#   backend.module_root  = backend/app
#   backend.dev_cmd      = uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
#   backend.health_url   = http://localhost:8000/health
#   frontend.module_root = frontend/src
#   frontend.dev_cmd     = npm run dev -- --host 0.0.0.0
#   db.migrate_cmd       = alembic upgrade head
#   db.seed_cmd          = python -m app.seeds.bootstrap_verification_data ...
#
# Required functions (contract enforced by scripts/dev-restart.sh):
#   back_health   → exit 0 if backend healthy
#   back_start    → start backend in background, write PID to BACK_PID_FILE
#   back_url      → human-readable URL for the status table
#   front_health  → exit 0 if frontend healthy
#   front_start   → start frontend in background, write PID to FRONT_PID_FILE
#   front_url     → human-readable URL for the status table
#   db_health     → 0 = up, 1 = down, 2 = unknown (backend down or /ready missing)
#   db_reset      → migrate down + up + seed (only called by --reset)
#
# Reads from .env at the project root (auto-sourced by the dispatcher):
#   API_HOST                 (default: 127.0.0.1)
#   API_PORT                 (default: 8000)   # canonical per STACK_PROFILE.yaml
#   FRONT_PORT               (default: 5173)   # vite default
#   ENABLE_VERBOSE_LOGGING   (default: true while in dev)

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-5173}"
ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING:-true}"

# --- Backend venv resolution ------------------------------------------------
# Canonical venv is backend/.venv. During scaffold phase a slice may keep an
# isolated venv (backend/.venv-<slice>); we accept that as a fallback so the
# dev loop never breaks on intermediate states. Order:
#   1. backend/.venv                    (canonical)
#   2. backend/.venv-* (alphabetical)   (slice-isolated, scaffold phase only)
_resolve_backend_venv() {
  local canon="${ROOT_DIR}/backend/.venv"
  if [ -d "$canon" ]; then
    printf '%s' "$canon"
    return 0
  fi
  local match
  match="$(find "${ROOT_DIR}/backend" -maxdepth 1 -type d -name '.venv-*' 2>/dev/null | sort | head -1)"
  if [ -n "$match" ]; then
    printf '%s' "$match"
    return 0
  fi
  return 1
}

# --- Health probes ----------------------------------------------------------

back_health() {
  curl -sf -m 2 "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1
}

front_health() {
  # Liveness contract: the Vite dev server process is reachable on FRONT_PORT
  # and speaks HTTP. We accept ANY HTTP response (including 404 while
  # index.html has not been added yet, which is the case until T004 lands)
  # so the dev loop is usable during the scaffold phase. Slice-level UI
  # checks (200 on /showcase, /login, etc.) belong to the slice's own
  # verification, not to the dev environment liveness probe.
  # -I avoids dragging the bundle.
  curl -sI -m 2 "http://${API_HOST}:${FRONT_PORT}/" 2>/dev/null \
    | head -1 | grep -qE '^HTTP/[0-9.]+ [0-9]{3}'
}

db_health() {
  # Reachability proxy: does the backend's /ready report ok?
  # If backend is down we cannot tell — return 2 (unknown).
  # If /ready is not implemented yet (404), also return 2 — we don't want to
  # report DOWN while the slice that adds /ready hasn't landed.
  if ! back_health; then
    return 2
  fi
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 2 "http://${API_HOST}:${API_PORT}/ready" 2>/dev/null || echo 000)"
  case "${code}" in
    200) return 0 ;;
    404) return 2 ;;  # endpoint not built yet — don't lie as DOWN
    *)   return 1 ;;
  esac
}

# --- URLs (status table) ----------------------------------------------------

back_url()  { printf 'http://%s:%s' "${API_HOST}" "${API_PORT}"; }
front_url() { printf 'http://%s:%s' "${API_HOST}" "${FRONT_PORT}"; }

# --- Start helpers ----------------------------------------------------------

back_start() {
  [ -d "${ROOT_DIR}/backend" ] || fail "backend/ not found — run setup-from-scratch.sh first."
  local venv
  if ! venv="$(_resolve_backend_venv)"; then
    fail "No backend venv found (expected backend/.venv or backend/.venv-*). Run pip install -e \".[dev]\" inside backend/ first."
  fi
  [ -x "${venv}/bin/python" ] || fail "Resolved venv ${venv} has no bin/python."

  log "Starting backend on ${API_HOST}:${API_PORT} (venv: $(basename "${venv}"))..."
  (
    cd "${ROOT_DIR}/backend" || exit 1
    # shellcheck disable=SC1091
    source "${venv}/bin/activate"
    ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING}" \
      nohup uvicorn app.main:app --host "${API_HOST}" --port "${API_PORT}" --reload \
        >"${BACK_LOG}" 2>&1 &
    echo $! >"${BACK_PID_FILE}"
  )

  if wait_for back_health 30 "Backend"; then
    info "backend up at $(back_url)/health"
  else
    fail "Backend did not respond on /health within 30s. See ${BACK_LOG}"
  fi
}

front_start() {
  [ -d "${ROOT_DIR}/frontend" ] || fail "frontend/ not found — run setup-from-scratch.sh first."
  [ -d "${ROOT_DIR}/frontend/node_modules" ] || fail "frontend/node_modules not found — run npm install inside frontend/ first."

  log "Starting Vite dev server on ${API_HOST}:${FRONT_PORT}..."
  (
    cd "${ROOT_DIR}/frontend" || exit 1
    # vite reads VITE_* env vars; surface API_URL + verbose flag for the app.
    VITE_API_URL="http://${API_HOST}:${API_PORT}" \
    VITE_ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING}" \
      nohup npm run dev -- --host "${API_HOST}" --port "${FRONT_PORT}" --strictPort \
        >"${FRONT_LOG}" 2>&1 &
    echo $! >"${FRONT_PID_FILE}"
  )

  # Vite cold start can take 10–20s when node_modules is fresh. Wait up to 60s.
  if wait_for front_health 60 "Frontend"; then
    info "frontend up at $(front_url)/"
  else
    fail "Frontend did not respond within 60s. See ${FRONT_LOG}"
  fi
}

# --- DB reset (only --reset) ------------------------------------------------

db_reset() {
  [ -d "${ROOT_DIR}/backend" ] || fail "backend/ not found"
  local venv
  if ! venv="$(_resolve_backend_venv)"; then
    warn "No backend venv — skipping DB reset."
    return 0
  fi
  log "Resetting DB schema (alembic downgrade base + upgrade head)..."
  (
    cd "${ROOT_DIR}/backend" || exit 1
    # shellcheck disable=SC1091
    source "${venv}/bin/activate"
    if [ ! -f "alembic.ini" ]; then
      warn "backend/alembic.ini missing — skipping DB reset (first migration is P01-S01-T001)."
      return 0
    fi
    alembic downgrade base || warn "alembic downgrade base failed (non-blocking on first run)"
    alembic upgrade head
  )
  log "Reseeding DB (idempotent seeds)..."
  (
    cd "${ROOT_DIR}/backend" || exit 1
    # shellcheck disable=SC1091
    source "${venv}/bin/activate"
    # The seed module path comes from STACK_PROFILE.yaml; landing slice is P00-S02-T003.
    if python -c "import app.seeds.bootstrap_verification_data" 2>/dev/null; then
      info "python -m app.seeds.bootstrap_verification_data --source data/verification"
      python -m app.seeds.bootstrap_verification_data --source data/verification \
        || warn "bootstrap_verification_data failed (non-blocking)"
    else
      info "app.seeds.bootstrap_verification_data not present yet — skipping (lands in P00-S02-T003)."
    fi
  )

  # Orphan port reapers — only fire on reset; the soft path leaves them alone.
  stop_orphan_on_port "${FRONT_PORT}" "frontend"
  stop_orphan_on_port "${API_PORT}"   "backend"
}
