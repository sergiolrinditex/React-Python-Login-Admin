#!/usr/bin/env bash
# scripts/dev-restart.profile.sh
#
# Slice:  P00-S02-T003 — Verification data loader and reset
# Phase:  P00 Scaffold + Design System
# Purpose: Stack-specific profile for Hilo People. Implements the function
#          contract required by scripts/dev-restart.sh. Previously a neutral
#          stub that returned fail/warn; this slice connects it to real services.
#
# Stack:
#   - Backend: FastAPI/Uvicorn on port 8000
#   - Frontend: Vite dev server on port 5173
#   - DB: Postgres via Docker Compose (hilo:hilo@localhost:5432/hilo_dev)
#   - Migrations: Alembic (cd backend && alembic upgrade head)
#   - Seed: python -m app.verification_data.bootstrap --source data/verification
#
# Required functions (contract enforced by scripts/dev-restart.sh):
#   back_health   -> exit 0 if backend healthy, else non-zero
#   back_start    -> start backend in background, write PID to $BACK_PID_FILE
#   back_url      -> print human-readable backend URL
#   front_health  -> exit 0 if frontend healthy, else non-zero
#   front_start   -> start frontend in background, write PID to $FRONT_PID_FILE
#   front_url     -> print human-readable frontend URL
#   db_health     -> 0 = up, 1 = down, 2 = unknown
#   db_reset      -> drop + recreate schema + seed verification data
#
# Source refs:
#   - docs/source-of-truth/STACK_PROFILE.yaml db.migrate_cmd, db.seed_cmd
#   - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §6.5 (seed cmd)
#   - 01-non-negotiables.md §Logging (BEFORE/AFTER, never PII)
#   - P00-S02-T003 §F.2 extensions (write_set extension justified by
#     scripts/dev-restart.sh:159,219 which call db_reset() from this profile)

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
back_health() {
  # BEFORE: check if backend health endpoint responds 200.
  curl -fsS http://localhost:8000/health > /dev/null 2>&1
}

back_start() {
  # BEFORE: launch uvicorn in background, capture PID.
  # Uses the worktree-relative backend directory.
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_root
  repo_root="$(cd "${script_dir}/.." && pwd)"
  (
    cd "${repo_root}/backend" || exit 1
    ENABLE_VERBOSE_LOGGING="${ENABLE_VERBOSE_LOGGING:-false}" \
      python3 -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        >> "${repo_root}/.dev-logs/backend.log" 2>&1 &
    echo $! > "${BACK_PID_FILE:-/tmp/hilo-backend.pid}"
  )
}

back_url() {
  printf 'http://localhost:8000'
}

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
front_health() {
  # BEFORE: check if Vite dev server is reachable.
  curl -fsS http://localhost:5173/ > /dev/null 2>&1
}

front_start() {
  # BEFORE: start Vite dev server in background, capture PID.
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_root
  repo_root="$(cd "${script_dir}/.." && pwd)"
  (
    cd "${repo_root}/frontend" || exit 1
    npm run dev -- --host 0.0.0.0 \
      >> "${repo_root}/.dev-logs/frontend.log" 2>&1 &
    echo $! > "${FRONT_PID_FILE:-/tmp/hilo-frontend.pid}"
  )
}

front_url() {
  printf 'http://localhost:5173'
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db_health() {
  # 0 = healthy, 1 = down, 2 = unknown.
  # Check via docker compose ps or direct psql.
  if command -v docker > /dev/null 2>&1; then
    local status
    status=$(docker compose ps --format json postgres 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for s in data:
            if s.get('Health') == 'healthy' or s.get('State') == 'running':
                print('healthy'); sys.exit(0)
    elif isinstance(data, dict):
        if data.get('Health') == 'healthy' or data.get('State') == 'running':
            print('healthy'); sys.exit(0)
except Exception:
    pass
print('down'); sys.exit(1)
" 2>/dev/null)
    if [ "$status" = "healthy" ]; then
      return 0
    fi
  fi
  # Fallback: try direct TCP connection.
  if python3 -c "
import socket, sys
try:
    s = socket.create_connection(('localhost', 5432), timeout=2)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    return 0
  fi
  return 1
}

db_reset() {
  # BEFORE: full DB reset — downgrade all migrations, re-run, seed.
  # Per §G capa 5 plan and AC7 acceptance criterion.
  # Working directory: caller is typically the repo root from dev-restart.sh.
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_root
  repo_root="$(cd "${script_dir}/.." && pwd)"

  echo "[db_reset] BEFORE: running alembic downgrade base"
  (
    cd "${repo_root}/backend" || return 1
    DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev}" \
      /Users/sergiolr/Library/Python/3.11/bin/alembic downgrade base 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then
      echo "[db_reset] ERROR: alembic downgrade base failed (exit $rc)" >&2
      return $rc
    fi

    echo "[db_reset] BEFORE: running alembic upgrade head"
    DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev}" \
      /Users/sergiolr/Library/Python/3.11/bin/alembic upgrade head 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then
      echo "[db_reset] ERROR: alembic upgrade head failed (exit $rc)" >&2
      return $rc
    fi

    echo "[db_reset] BEFORE: running bootstrap seed"
    DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev}" \
      python3 -m app.verification_data.bootstrap \
        --source "${repo_root}/data/verification" 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then
      echo "[db_reset] ERROR: bootstrap seed failed (exit $rc)" >&2
      return $rc
    fi
  )
  echo "[db_reset] AFTER: db_reset completed successfully"
  return 0
}
