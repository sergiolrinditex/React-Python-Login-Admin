#!/usr/bin/env bash
# scripts/dev-restart.profile.sh
#
# Stack profile: Flutter + FastAPI + Supabase (the BaseflutterAppsEngineFeatures
# default). This is the file feature-apps override when their stack diverges:
# replace this profile, keep scripts/dev-restart.sh untouched.
#
# Required functions (contract enforced by scripts/dev-restart.sh):
#   back_health   → exit 0 if backend healthy
#   back_start    → start backend in background, write PID to BACK_PID_FILE
#   back_url      → human-readable URL for the status table
#   front_health  → exit 0 if frontend healthy
#   front_start   → start frontend in background, write PID to FRONT_PID_FILE
#   front_url     → human-readable URL for the status table
#   db_health     → 0 = up, 1 = down, 2 = unknown (backend down)
#   db_reset      → migrate down + up + seed (only called by --reset)
#
# Reads from .env at the project root (auto-sourced by the dispatcher):
#   API_HOST                 (default: 127.0.0.1)
#   API_PORT                 (default: 8000)
#   FRONT_PORT               (default: 5000)
#   ENABLE_VERBOSE_LOGGING   (default: true while in dev)

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-5000}"
ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING:-true}"

# --- Health probes ----------------------------------------------------------

back_health() {
  curl -sf -m 2 "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1
}

front_health() {
  # Flutter web-server returns 200 on /. -I avoids dragging the bundle.
  curl -sI -m 2 "http://${API_HOST}:${FRONT_PORT}/" 2>/dev/null \
    | head -1 | grep -qE 'HTTP/[0-9.]+ (200|304)'
}

db_health() {
  # Reachability proxy: does the backend's /ready report ok?
  # If backend is down we cannot tell — return 2 (unknown) so the dispatcher
  # surfaces UNKNOWN instead of falsely reporting DOWN.
  if back_health; then
    curl -sf -m 2 "http://${API_HOST}:${API_PORT}/ready" >/dev/null 2>&1
  else
    return 2
  fi
}

# --- URLs (status table) ----------------------------------------------------

back_url()  { printf 'http://%s:%s' "${API_HOST}" "${API_PORT}"; }
front_url() { printf 'http://%s:%s' "${API_HOST}" "${FRONT_PORT}"; }

# --- Start helpers ----------------------------------------------------------

back_start() {
  [ -d "${ROOT_DIR}/api" ] || fail "api/ not found — run setup-from-scratch.sh first."
  [ -d "${ROOT_DIR}/api/.venv" ] || fail "api/.venv not found — run setup-from-scratch.sh first."

  log "Starting backend on ${API_HOST}:${API_PORT}..."
  (
    cd "${ROOT_DIR}/api" || exit 1
    # shellcheck disable=SC1091
    source .venv/bin/activate
    ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING}" \
      nohup uvicorn src.main:app --host "${API_HOST}" --port "${API_PORT}" --reload \
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
  [ -d "${ROOT_DIR}/app" ] || fail "app/ not found — run setup-from-scratch.sh first."

  log "Starting Flutter web on ${API_HOST}:${FRONT_PORT}..."
  (
    cd "${ROOT_DIR}/app" || exit 1
    nohup flutter run \
      -d web-server \
      --web-hostname "${API_HOST}" \
      --web-port "${FRONT_PORT}" \
      --dart-define=API_URL="http://${API_HOST}:${API_PORT}" \
      --dart-define=ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING}" \
      >"${FRONT_LOG}" 2>&1 &
    echo $! >"${FRONT_PID_FILE}"
  )

  # Flutter web-server takes longer (initial compile). Wait up to 90s.
  if wait_for front_health 90 "Frontend"; then
    info "frontend up at $(front_url)/"
  else
    fail "Frontend did not respond within 90s. See ${FRONT_LOG}"
  fi
}

# --- DB reset (only --reset) ------------------------------------------------

db_reset() {
  [ -d "${ROOT_DIR}/api" ] || fail "api/ not found"
  log "Resetting DB schema (alembic downgrade base + upgrade head)..."
  (
    cd "${ROOT_DIR}/api" || exit 1
    # shellcheck disable=SC1091
    source .venv/bin/activate
    if [ ! -f "alembic.ini" ]; then
      warn "api/alembic.ini missing — skipping DB reset."
      return 0
    fi
    alembic downgrade base
    alembic upgrade head
  )
  log "Reseeding DB (idempotent seeds)..."
  (
    cd "${ROOT_DIR}/api" || exit 1
    # shellcheck disable=SC1091
    source .venv/bin/activate
    for seed in bootstrap_users bootstrap_ai_providers bootstrap_rag_documents; do
      if python -c "import seeds.${seed}" 2>/dev/null; then
        info "python -m seeds.${seed}"
        python -m "seeds.${seed}" || warn "seeds.${seed} failed (non-blocking)"
      fi
    done
  )

  # Orphan port reapers — only fire on reset; the soft path leaves them alone.
  stop_orphan_on_port "${FRONT_PORT}" "frontend"
  stop_orphan_on_port "${API_PORT}"   "backend"
}
