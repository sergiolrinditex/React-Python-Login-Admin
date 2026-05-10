#!/usr/bin/env bash
# scripts/dev-restart.profile.sh
#
# Stack profile: React (Vite) + FastAPI (uvicorn) + Postgres (native :5433).
# This file overrides the BaseflutterAppsEngineFeatures default so the dispatcher
# (scripts/dev-restart.sh) can manage this project's real stack. Keep the
# dispatcher untouched; only this profile is stack-specific.
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
#   FRONT_PORT               (default: 5173)
#   ENABLE_VERBOSE_LOGGING   (default: true while in dev)
#   ENCRYPTION_KEY           (Fernet key — required for admin_ai endpoints;
#                             auto-generated for the in-process backend if
#                             the env-supplied value is the dev placeholder)

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-5173}"
ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING:-true}"

BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
BACKEND_VENV="${BACKEND_DIR}/.venv-t003"
DB_URL_DEFAULT="postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
DATABASE_URL="${DATABASE_URL:-${DB_URL_DEFAULT}}"

# --- Health probes ----------------------------------------------------------

back_health() {
  curl -sf -m 2 "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1
}

front_health() {
  # Vite dev server returns 200 on /. -I avoids dragging the SPA bundle.
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
  [ -d "${BACKEND_DIR}" ] || fail "backend/ not found."
  [ -x "${BACKEND_VENV}/bin/uvicorn" ] || fail "backend venv missing. Expected ${BACKEND_VENV}/bin/uvicorn"

  # Auto-generate a real Fernet key when the env supplies the dev placeholder.
  # The legacy var name PROVIDER_ENCRYPTION_KEY (in .env) was renamed to
  # ENCRYPTION_KEY in P01-S01-T002 §11.1; this profile honours the new name.
  local enc_key="${ENCRYPTION_KEY:-${PROVIDER_ENCRYPTION_KEY:-}}"
  if [ -z "${enc_key}" ] || [ "${enc_key}" = "dev-encryption-key-placeholder" ]; then
    enc_key="$("${BACKEND_VENV}/bin/python" -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
    info "ENCRYPTION_KEY auto-generated for verify-slice (Fernet)"
  fi

  log "Starting backend on ${API_HOST}:${API_PORT}..."
  (
    cd "${BACKEND_DIR}" || exit 1
    ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING}" \
    ENCRYPTION_KEY="${enc_key}" \
    DATABASE_URL="${DATABASE_URL}" \
      nohup "${BACKEND_VENV}/bin/uvicorn" app.main:app \
        --host "${API_HOST}" --port "${API_PORT}" --reload \
        >"${BACK_LOG}" 2>&1 &
    echo $! >"${BACK_PID_FILE}"
  )

  # Persist the actual ENCRYPTION_KEY used for back, so db_reseed_admin_ai can
  # re-encrypt credentials with the same key the running backend will decrypt.
  printf '%s\n' "${enc_key}" >"${LOG_DIR}/encryption-key.runtime"
  chmod 600 "${LOG_DIR}/encryption-key.runtime" 2>/dev/null || true

  if wait_for back_health 30 "Backend"; then
    info "backend up at $(back_url)/health"
  else
    fail "Backend did not respond on /health within 30s. See ${BACK_LOG}"
  fi
}

front_start() {
  [ -d "${FRONTEND_DIR}" ] || fail "frontend/ not found."
  [ -d "${FRONTEND_DIR}/node_modules" ] || fail "frontend/node_modules missing — run npm ci."

  log "Starting Vite on ${API_HOST}:${FRONT_PORT}..."
  (
    cd "${FRONTEND_DIR}" || exit 1
    nohup npm run dev -- --host "${API_HOST}" --port "${FRONT_PORT}" --strictPort \
      >"${FRONT_LOG}" 2>&1 &
    echo $! >"${FRONT_PID_FILE}"
  )

  if wait_for front_health 30 "Frontend"; then
    info "frontend up at $(front_url)/"
  else
    fail "Frontend did not respond within 30s. See ${FRONT_LOG}"
  fi
}

# --- DB reset (only --reset) ------------------------------------------------

db_reset() {
  [ -d "${BACKEND_DIR}" ] || fail "backend/ not found"
  [ -x "${BACKEND_VENV}/bin/python" ] || fail "backend venv missing. Expected ${BACKEND_VENV}/bin/python"

  # Per Verification Data Contract §6.5 row J103: "delete ai_provider test rows".
  # We do not drop the whole schema for verify-slice — auth/users/conversations
  # state from prior journeys must survive. Only the admin_ai surface is reset.
  log "Resetting admin_ai surface (ai_models / ai_provider_credentials / ai_providers)..."
  "${BACKEND_VENV}/bin/python" - <<'PY' || warn "admin_ai truncate failed (non-blocking)"
import asyncio, os, asyncpg, re
url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev",
)
# asyncpg expects vanilla postgres:// not the SQLAlchemy variant
url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)

async def main():
    c = await asyncpg.connect(url)
    try:
        await c.execute("TRUNCATE ai_models, ai_provider_credentials, ai_providers RESTART IDENTITY CASCADE")
        print("   admin_ai tables truncated")
    finally:
        await c.close()
asyncio.run(main())
PY

  # Apply migrations (no-op if already at head).
  log "Applying alembic migrations to head..."
  (
    cd "${BACKEND_DIR}" || exit 1
    "${BACKEND_VENV}/bin/alembic" upgrade head >/dev/null
  ) || warn "alembic upgrade failed (non-blocking)"

  # Reseed only the admin_ai namespace per J103 row of the data contract.
  # The seed loader is table-tolerant: it inserts what it can and skips the rest.
  log "Reseeding admin_ai (verification bundle, P00-S02-T005)..."
  (
    cd "${BACKEND_DIR}" || exit 1
    DATABASE_URL="${DATABASE_URL}" \
    ENCRYPTION_KEY="${ENCRYPTION_KEY:-${PROVIDER_ENCRYPTION_KEY:-}}" \
      "${BACKEND_VENV}/bin/python" -m app.seeds.bootstrap_verification_data \
        --source ../data/verification --only admin_ai \
        2>&1 | tail -15
  ) || warn "admin_ai seed failed (non-blocking — verify-slice can fall back to SQL recipe)"

  # Orphan port reapers — only fire on reset; the soft path leaves them alone.
  stop_orphan_on_port "${FRONT_PORT}" "frontend"
  stop_orphan_on_port "${API_PORT}"   "backend"
}
