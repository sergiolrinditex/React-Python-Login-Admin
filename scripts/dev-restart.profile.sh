#!/usr/bin/env bash
# scripts/dev-restart.profile.sh
#
# Real stack profile for Hilo People.
# Slice: P02-S03-T003 — restore stack-specific dev-restart.profile.sh broken
#        by framework refactor c4c91ae (FU-20260513094006).
#
# File size: ~378 LOC justified by four documented edge-case helpers
# (compose/python/alembic resolution + host-TCP probe) and inline rationale
# comments. No business logic.
#
# Derived from:
#   - docs/source-of-truth/STACK_PROFILE.yaml
#       backend.dev_cmd        → uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
#       backend.health_url     → http://localhost:8000/health
#       backend.module_root    → backend/app
#       frontend.dev_cmd       → npm run dev -- --host 0.0.0.0
#       frontend.module_root   → frontend/src
#       db.migrate_cmd         → alembic upgrade head
#       db.seed_cmd            → python -m app.verification_data.bootstrap --source data/verification
#   - docker-compose.yml
#       services: postgres (5432) · redis (6379) · litellm (4000) · minio (9000/9001)
#       backend depends_on postgres+redis+litellm healthy; in host-mode we
#       launch uvicorn outside compose, so only postgres+redis are strictly
#       required for backend boot.
#   - .env.example
#       POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB (postgres init)
#       DATABASE_URL → postgresql+asyncpg://hilo:hilo@localhost:5432/hilo_dev
#
# Prior fixes preserved:
#   P01-S02-T008: absolute --source path for python -m app.verification_data.bootstrap
#   P01-S02-T012: host-TCP probe (_host_pg_ready) to close Rancher Desktop race;
#                 _ensure_infra_essential timeout raised 30→60s.
#
# Contract (enforced by scripts/dev-restart.sh):
#   back_health   exit 0 if backend up
#   back_start    boot backend (nohup, PID → $BACK_PID_FILE, logs → $BACK_LOG)
#   back_url      URL string for status table
#   front_health  exit 0 if frontend up
#   front_start   boot frontend (nohup, PID → $FRONT_PID_FILE, logs → $FRONT_LOG)
#   front_url     URL string for status table
#   db_health     0 = up, 1 = down, 2 = unknown (no CLI / no compose)
#   db_reset      destroy DB volume → infra up → migrate → seed (hard-fail on
#                 seed failure: data/verification/ must exist and be loadable;
#                 any bootstrap error aborts --reset with non-zero exit).
#
# Helpers exported by scripts/dev-restart.sh (available here):
#   log, warn, fail, info, pid_alive, stop_pidfile, stop_orphan_on_port, wait_for
# Vars exported by scripts/dev-restart.sh:
#   ROOT_DIR, LOG_DIR, BACK_LOG, FRONT_LOG, BACK_PID_FILE, FRONT_PID_FILE
#
# Notes:
#   - Rancher Desktop: if `docker`/`nerdctl` are not on PATH, we auto-prepend
#     $HOME/.rd/bin (default Rancher install location on macOS) before
#     resolving the compose command.
#   - Compose CLI resolution prefers `docker compose` (moby backend, fully
#     supports healthchecks + depends_on), then `docker-compose`, then
#     `nerdctl compose` (containerd backend — degraded; see compose file note).
#   - Python interpreter: prefers .venv/bin/python (root) → backend/.venv/bin/python
#     → system python3. We sanity-check `import uvicorn, fastapi` before boot
#     and fail with an actionable message if deps are missing.
#   - This profile MUST stay agnostic of the dispatcher internals — it only
#     uses the helpers exported by scripts/dev-restart.sh: log, warn, fail,
#     info, pid_alive, stop_pidfile, stop_orphan_on_port, wait_for; and the
#     vars ROOT_DIR, LOG_DIR, BACK_LOG, FRONT_LOG, BACK_PID_FILE, FRONT_PID_FILE.

# --- Config (derived from source-of-truth) ----------------------------------

HILO_BACKEND_PORT="${BACKEND_PORT:-8000}"
HILO_FRONTEND_PORT="${FRONTEND_PORT:-5173}"
HILO_POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
HILO_POSTGRES_PORT="${POSTGRES_PORT:-5432}"
HILO_POSTGRES_USER="${POSTGRES_USER:-hilo}"
HILO_POSTGRES_DB="${POSTGRES_DB:-hilo_dev}"
HILO_BACKEND_DIR="${ROOT_DIR}/backend"
HILO_FRONTEND_DIR="${ROOT_DIR}/frontend"
HILO_COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"
HILO_INFRA_ESSENTIAL=(postgres redis)
HILO_INFRA_FULL=(postgres redis litellm minio)

# --- Rancher Desktop PATH injection -----------------------------------------
# Rancher Desktop on macOS installs CLI shims into ~/.rd/bin. Subshells (e.g.
# launched by Claude Code) often don't inherit that PATH entry, so add it
# eagerly if the shims exist and `docker` is not yet visible.
if [ -d "${HOME}/.rd/bin" ] && ! command -v docker >/dev/null 2>&1; then
  export PATH="${HOME}/.rd/bin:${PATH}"
fi

# --- Internal helpers (private; prefix _) -----------------------------------

_resolve_compose() {
  # Echoes the compose command tokens; returns 1 if none found.
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    printf 'docker compose'
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    printf 'docker-compose'
    return 0
  fi
  if command -v nerdctl >/dev/null 2>&1 && nerdctl compose version >/dev/null 2>&1; then
    printf 'nerdctl compose'
    return 0
  fi
  return 1
}

_resolve_python() {
  # Echoes the python interpreter path; returns 1 if none found.
  if [ -x "${ROOT_DIR}/.venv/bin/python" ]; then
    printf '%s' "${ROOT_DIR}/.venv/bin/python"
    return 0
  fi
  if [ -x "${HILO_BACKEND_DIR}/.venv/bin/python" ]; then
    printf '%s' "${HILO_BACKEND_DIR}/.venv/bin/python"
    return 0
  fi
  local found
  found="$(command -v python3 || command -v python || true)"
  [ -n "${found}" ] && { printf '%s' "${found}"; return 0; }
  return 1
}

_resolve_alembic() {
  # Echoes the alembic CLI binary path; returns 1 if none found.
  #
  # We MUST use the CLI binary (not `python -m alembic` and not
  # `python -c "from alembic.config import main"`) because backend/alembic/
  # exists as a real package (the migrations directory). When `python` is
  # invoked from `backend/`, cwd is added to sys.path[0] and shadows the
  # installed `alembic` package — `from alembic.config import main` then
  # fails with ModuleNotFoundError. The CLI script's sys.path[0] is its
  # own bin directory, so it imports the installed package cleanly.
  if [ -x "${ROOT_DIR}/.venv/bin/alembic" ]; then
    printf '%s' "${ROOT_DIR}/.venv/bin/alembic"
    return 0
  fi
  if [ -x "${HILO_BACKEND_DIR}/.venv/bin/alembic" ]; then
    printf '%s' "${HILO_BACKEND_DIR}/.venv/bin/alembic"
    return 0
  fi
  # Probe user-site bin directories for Python 3.x installed via `pip --user`.
  local user_bin
  for v in 3.13 3.12 3.11 3.10; do
    user_bin="${HOME}/Library/Python/${v}/bin/alembic"
    if [ -x "${user_bin}" ]; then
      printf '%s' "${user_bin}"
      return 0
    fi
    user_bin="${HOME}/.local/bin/alembic"
    if [ -x "${user_bin}" ]; then
      printf '%s' "${user_bin}"
      return 0
    fi
  done
  local found
  found="$(command -v alembic || true)"
  [ -n "${found}" ] && { printf '%s' "${found}"; return 0; }
  return 1
}

_tcp_probe() {
  # Plain TCP probe via Bash /dev/tcp. Returns 0 if connect succeeds.
  # Uses a subshell so the FD is isolated; stderr suppressed to silence
  # "Connection refused" noise when postgres is not yet reachable.
  local host="$1" port="$2"
  (exec 3<>/dev/tcp/"${host}"/"${port}") 2>/dev/null && exec 3<&- 3>&-
}

_host_pg_ready() {
  # Probe host-side TCP port-forward to postgres. Returns 0 if reachable.
  # Distinct from _compose_pg_ready (container-internal pg_isready) because
  # Rancher Desktop / Docker Desktop can take 0.5-3s after container reports
  # ready before the host port-forward is usable by alembic. (P01-S02-T012)
  _tcp_probe "${HILO_POSTGRES_HOST}" "${HILO_POSTGRES_PORT}" 2>/dev/null
}

_compose_pg_ready() {
  # Run pg_isready inside the compose postgres container. Returns 0 if ready.
  local compose
  compose="$(_resolve_compose)" || return 1
  ${compose} -f "${HILO_COMPOSE_FILE}" exec -T postgres \
    pg_isready -U "${HILO_POSTGRES_USER}" -d "${HILO_POSTGRES_DB}" \
    >/dev/null 2>&1
}

_ensure_infra_essential() {
  # Boot postgres + redis if not already up. Idempotent — `compose up -d` is
  # a no-op when services are already healthy.
  local compose
  if ! compose="$(_resolve_compose)"; then
    warn "No container CLI available (need 'docker compose' or 'nerdctl compose')."
    warn "If Rancher Desktop is installed, ensure it is running and ~/.rd/bin is in PATH."
    return 1
  fi
  log "Ensuring infra up: ${HILO_INFRA_ESSENTIAL[*]}"
  if ! ${compose} -f "${HILO_COMPOSE_FILE}" up -d "${HILO_INFRA_ESSENTIAL[@]}" \
        >>"${BACK_LOG}" 2>&1; then
    warn "compose up failed — see ${BACK_LOG}"
    return 1
  fi
  if ! wait_for db_health 60 "Postgres"; then  # raised 30→60s: host TCP probe (P01-S02-T012)
    return 1
  fi
}

# --- Contract: backend ------------------------------------------------------

back_health() {
  curl -sf "http://localhost:${HILO_BACKEND_PORT}/health" >/dev/null 2>&1
}

back_url() {
  printf 'http://localhost:%s' "${HILO_BACKEND_PORT}"
}

back_start() {
  local py
  if ! py="$(_resolve_python)"; then
    fail "No Python interpreter found (need python3 in PATH or .venv/bin/python)."
  fi
  if ! "${py}" -c 'import uvicorn, fastapi' >/dev/null 2>&1; then
    fail "Python ${py} cannot import uvicorn/fastapi.
       Install backend deps first, e.g.:
         python3 -m venv .venv && source .venv/bin/activate && pip install -e backend
       Or with pip directly:
         pip install -r backend/requirements.txt"
  fi

  if ! _ensure_infra_essential; then
    fail "Cannot start backend: infra services (postgres/redis) are not ready.
       Bring up Rancher Desktop / Docker Desktop and retry, or run:
         docker compose -f docker-compose.yml up -d postgres redis"
  fi

  stop_orphan_on_port "${HILO_BACKEND_PORT}" "backend"
  log "Starting backend (uvicorn) on :${HILO_BACKEND_PORT}..."

  # Launch uvicorn from backend/ so `app.main:app` resolves correctly.
  cd "${HILO_BACKEND_DIR}"
  nohup "${py}" -m uvicorn app.main:app \
        --host 0.0.0.0 --port "${HILO_BACKEND_PORT}" --reload \
        >>"${BACK_LOG}" 2>&1 &
  echo $! > "${BACK_PID_FILE}"
  cd "${ROOT_DIR}"

  if ! wait_for back_health 30 "backend"; then
    warn "Backend did not become healthy in 30s. See ${BACK_LOG} for details."
    return 1
  fi
  info "backend ready at $(back_url) (pid $(cat "${BACK_PID_FILE}"))"
}

# --- Contract: frontend -----------------------------------------------------

front_health() {
  # Vite responds 200 to "/" once the dev server is ready. We accept 200/304.
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' \
          "http://localhost:${HILO_FRONTEND_PORT}/" 2>/dev/null)" || return 1
  case "${code}" in
    200|304) return 0 ;;
    *)       return 1 ;;
  esac
}

front_url() {
  printf 'http://localhost:%s' "${HILO_FRONTEND_PORT}"
}

front_start() {
  if ! command -v npm >/dev/null 2>&1; then
    fail "npm not found in PATH. Install Node.js (matching frontend/package.json
       engines) or add it to PATH."
  fi
  if [ ! -d "${HILO_FRONTEND_DIR}/node_modules" ]; then
    log "frontend/node_modules missing — running npm install..."
    cd "${HILO_FRONTEND_DIR}"
    if ! npm install >>"${FRONT_LOG}" 2>&1; then
      cd "${ROOT_DIR}"
      fail "npm install failed; see ${FRONT_LOG}"
    fi
    cd "${ROOT_DIR}"
  fi

  stop_orphan_on_port "${HILO_FRONTEND_PORT}" "frontend"
  log "Starting frontend (vite) on :${HILO_FRONTEND_PORT}..."

  cd "${HILO_FRONTEND_DIR}"
  # package.json "dev" script already binds --host 0.0.0.0; we pass --port so
  # the port is explicit and matches BACKEND_PORT / FRONTEND_PORT env vars.
  nohup npm run dev -- --port "${HILO_FRONTEND_PORT}" \
        >>"${FRONT_LOG}" 2>&1 &
  echo $! > "${FRONT_PID_FILE}"
  cd "${ROOT_DIR}"

  if ! wait_for front_health 60 "frontend"; then
    warn "Frontend did not respond in 60s. See ${FRONT_LOG} for details."
    return 1
  fi
  info "frontend ready at $(front_url) (pid $(cat "${FRONT_PID_FILE}"))"
}

# --- Contract: database -----------------------------------------------------

db_health() {
  # Returns:
  #   0 = postgres reachable: BOTH container-internal pg_isready AND host TCP pass
  #   1 = postgres is supposed to be up but not responding (one or both probes fail)
  #   2 = unknown (no compose CLI and no host TCP; UI surfaces UNKNOWN)
  #
  # P01-S02-T012: the two-probe AND is the core race fix. Rancher Desktop /
  # Docker Desktop can take 0.5-3s after pg_isready-internal returns OK before
  # the host port-forward is open. alembic upgrade head runs from the host, so
  # we must verify host TCP reachability before declaring postgres UP.
  log "[db_health] probing postgres: container-internal pg_isready AND host TCP ${HILO_POSTGRES_HOST}:${HILO_POSTGRES_PORT}"

  # Fast path: both probes must pass (container-internal AND host-side TCP).
  if _resolve_compose >/dev/null 2>&1 && _compose_pg_ready && _host_pg_ready; then
    log "[db_health] postgres UP (container ready + host TCP open)"
    return 0
  fi

  # No-compose path: if no compose CLI is available (postgres native on host),
  # a successful host TCP probe alone is sufficient and we surface UNKNOWN→UP.
  if ! _resolve_compose >/dev/null 2>&1; then
    if _host_pg_ready; then
      log "[db_health] postgres UP (no compose CLI; host TCP open — native postgres)"
      return 0
    fi
    log "[db_health] postgres UNKNOWN (no compose CLI, host TCP closed)"
    return 2
  fi

  log "[db_health] postgres DOWN (at least one probe failed)"
  return 1
}

db_reset() {
  local compose py alembic_cli
  if ! compose="$(_resolve_compose)"; then
    fail "Cannot reset DB: no container CLI found (need docker compose / nerdctl compose)."
  fi
  if ! py="$(_resolve_python)"; then
    fail "Cannot reset DB: no python interpreter found."
  fi
  if ! alembic_cli="$(_resolve_alembic)"; then
    fail "Cannot reset DB: alembic CLI not found.
       Install backend deps so the alembic script lands in a known bin dir:
         pip install --user alembic   # → ~/Library/Python/X.Y/bin/alembic
       Or use a venv:
         python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt"
  fi
  if ! "${py}" -c 'import app.verification_data.bootstrap' >/dev/null 2>&1 \
       && ! ( cd "${HILO_BACKEND_DIR}" && "${py}" -c 'import app.verification_data.bootstrap' >/dev/null 2>&1 ); then
    warn "Python ${py} cannot import app.verification_data.bootstrap.
       Seed step will be skipped. Check backend deps."
  fi

  log "Hard reset: destroying compose volumes (pg_data, minio_data)..."
  ${compose} -f "${HILO_COMPOSE_FILE}" down -v --remove-orphans \
    >>"${BACK_LOG}" 2>&1 || true

  log "Booting full infra: ${HILO_INFRA_FULL[*]}"
  if ! ${compose} -f "${HILO_COMPOSE_FILE}" up -d "${HILO_INFRA_FULL[@]}" \
        >>"${BACK_LOG}" 2>&1; then
    fail "compose up failed; see ${BACK_LOG}"
  fi
  if ! wait_for db_health 60 "Postgres"; then
    fail "Postgres did not become ready within 60s."
  fi

  log "Applying alembic migrations (alembic upgrade head)..."
  cd "${HILO_BACKEND_DIR}"
  if ! "${alembic_cli}" upgrade head >>"${BACK_LOG}" 2>&1; then
    cd "${ROOT_DIR}"
    fail "alembic upgrade head failed; see ${BACK_LOG}"
  fi
  cd "${ROOT_DIR}"

  log "Loading verification_data (real/provided fixtures)..."
  cd "${HILO_BACKEND_DIR}"
  # `python -m app.verification_data.bootstrap` is safe here: `app` is a real
  # package at backend/app/, and there is no top-level module that shadows it.
  # --source uses an absolute path derived from ROOT_DIR so that cwd=backend/
  # does not cause the relative path data/verification to resolve to
  # backend/data/verification (which does not exist). P01-S02-T008 fix.
  if ! "${py}" -m app.verification_data.bootstrap \
        --source "${ROOT_DIR}/data/verification" >>"${BACK_LOG}" 2>&1; then
    cd "${ROOT_DIR}"
    fail "verification_data bootstrap failed; see ${BACK_LOG}."
  fi
  log "verification_data bootstrap complete."
  cd "${ROOT_DIR}"
}
