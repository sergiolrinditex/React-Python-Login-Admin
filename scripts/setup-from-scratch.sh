#!/usr/bin/env bash
# Hilo People — stack-aware development setup.
#
# Slice:  P00-S01-T001 — Repo scaffold + scripts + env (added --check flag)
# Phase:  P00 Scaffold + Design System
# Purpose: Declarative project setup driven by STACK_PROFILE.yaml.
#          --check mode: validates scaffold artifact presence without mutating
#          anything (read-only, exit 1 on first missing artifact).
# Source:  STACK_PROFILE.yaml, 01-non-negotiables.md §API contract,
#          TECHNICAL_GUIDE §3 Comandos.
#
# Usage:
#   bash scripts/setup-from-scratch.sh           # declarative setup (default)
#   bash scripts/setup-from-scratch.sh --check   # read-only presence validation
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$ROOT_DIR}"
STACK="$ROOT_DIR/.claude/bin/stack_profile.py"

log()  { echo "==> $1"; }
warn() { echo "WARN: $1" >&2; }
fail() { echo "ERROR: $1" >&2; exit 1; }
ok()   { echo "  [OK]  $1"; }

get_profile() {
  python3 -B -S "$STACK" --root "$PROJECT_ROOT" --get "$1" --default "$2"
}

run_if_declared() {
  local label="$1"
  local cmd="$2"
  if [ -z "$cmd" ] || [ "$cmd" = "none" ]; then
    log "$label: no command declared, skip"
    return
  fi
  log "$label: $cmd"
  ( cd "$PROJECT_ROOT" && bash -lc "$cmd" )
}

# ── --check mode ─────────────────────────────────────────────────────────────
# Read-only static validation of scaffold artifact presence.
# Exit 0 only if ALL required scaffold artifacts exist and the health stub
# imports cleanly.  Exit 1 with an ERROR: message on the first missing item.
# Does NOT install deps, start servers or touch the DB.
#
# Required artifacts (from task pack P00-S01-T001 §3.1):
#   1. package.json at repo root
#   2. frontend/package.json (Vite+React+TS)
#   3. backend/pyproject.toml AND/OR backend/requirements.txt
#   4. backend/app/main.py with /health stub that imports cleanly
#   5. .env.example with required canonical keys

if [ "${1:-}" = "--check" ]; then
  log "Running scaffold --check (read-only validation)"
  echo ""
  PASS=0
  FAIL=0

  _check_file() {
    local label="$1"
    local path="$2"
    if [ -f "$PROJECT_ROOT/$path" ]; then
      ok "$label: $path"
      PASS=$((PASS + 1))
    else
      echo "  [FAIL] $label: $path NOT FOUND" >&2
      FAIL=$((FAIL + 1))
    fi
  }

  _check_dir() {
    local label="$1"
    local path="$2"
    if [ -d "$PROJECT_ROOT/$path" ]; then
      ok "$label: $path/"
      PASS=$((PASS + 1))
    else
      echo "  [FAIL] $label: $path/ NOT FOUND" >&2
      FAIL=$((FAIL + 1))
    fi
  }

  log "Artifact presence check:"
  _check_file "repo-root package.json"            "package.json"
  _check_file "frontend package.json"             "frontend/package.json"
  _check_dir  "backend app directory"             "backend/app"

  # pyproject.toml OR requirements.txt (either satisfies acceptance)
  if [ -f "$PROJECT_ROOT/backend/pyproject.toml" ] || [ -f "$PROJECT_ROOT/backend/requirements.txt" ]; then
    ok "backend Python manifest: found (pyproject.toml or requirements.txt)"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] backend Python manifest: neither pyproject.toml nor requirements.txt found" >&2
    FAIL=$((FAIL + 1))
  fi

  _check_file "backend main.py"                   "backend/app/main.py"
  _check_file ".env.example"                      ".env.example"

  # Verify .env.example has the required canonical env keys (TECHNICAL_GUIDE §11.1)
  log ""
  log "Env-key presence check (.env.example):"
  REQUIRED_ENV_KEYS="DATABASE_URL REDIS_URL JWT_PRIVATE_KEY JWT_PUBLIC_KEY ENCRYPTION_KEY LITELLM_BASE_URL DEFAULT_LANGUAGE ENABLE_VERBOSE_LOGGING"
  for key in $REQUIRED_ENV_KEYS; do
    if grep -qE "^${key}=" "$PROJECT_ROOT/.env.example" 2>/dev/null; then
      ok ".env.example has $key"
      PASS=$((PASS + 1))
    else
      echo "  [FAIL] .env.example missing key: $key" >&2
      FAIL=$((FAIL + 1))
    fi
  done

  # Verify health stub compiles (Python import test — no server boot required)
  log ""
  log "Health stub compile check:"
  if python3 -c "import sys; sys.path.insert(0,'$PROJECT_ROOT/backend'); from app.main import app; print('import ok')" 2>/dev/null; then
    ok "backend/app/main.py: imports cleanly (health stub compiles)"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] backend/app/main.py: failed to import" >&2
    FAIL=$((FAIL + 1))
  fi

  echo ""
  log "Result: $PASS checks passed, $FAIL checks failed."
  if [ "$FAIL" -gt 0 ]; then
    fail "$FAIL scaffold artifact(s) missing. See FAIL lines above."
  fi
  log "✓ All scaffold checks passed."
  exit 0
fi

# ── Default mode — declarative setup ─────────────────────────────────────────

FRONTEND_ROOT="$(get_profile frontend.module_root none)"
BACKEND_ROOT="$(get_profile backend.module_root none)"
FRONTEND_DEV_CMD="$(get_profile frontend.dev_cmd none)"
BACKEND_DEV_CMD="$(get_profile backend.dev_cmd none)"
DB_MIGRATE_CMD="$(get_profile db.migrate_cmd none)"
DB_SEED_CMD="$(get_profile db.seed_cmd none)"
HEALTH_URL="$(get_profile backend.health_url none)"

if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
else
  warn ".env no existe. Continúo porque el stack profile puede apuntar a servicios externos o comandos no locales."
fi

BACKEND_EXISTS=1
if [ "$BACKEND_ROOT" != "none" ] && [ ! -d "$PROJECT_ROOT/$BACKEND_ROOT" ]; then
  BACKEND_EXISTS=0
  warn "Backend root $BACKEND_ROOT no existe todavía; skip setup backend."
fi
if [ "$FRONTEND_ROOT" != "none" ] && [ ! -d "$PROJECT_ROOT/$FRONTEND_ROOT" ]; then
  warn "Frontend root $FRONTEND_ROOT no existe todavía; skip setup frontend."
fi

if [ "$BACKEND_EXISTS" -eq 0 ]; then
  log "DB migrations: backend root $BACKEND_ROOT no existe todavía, skip"
  log "DB seed: backend root $BACKEND_ROOT no existe todavía, skip"
else
  run_if_declared "DB migrations" "$DB_MIGRATE_CMD"
  run_if_declared "DB seed" "$DB_SEED_CMD"
fi

echo ""
log "✓ Setup declarativo completado."
echo ""
echo "Comandos declarados para arrancar dev:"
echo "  Backend:  $BACKEND_DEV_CMD"
echo "  Frontend: $FRONTEND_DEV_CMD"
if [ "$HEALTH_URL" != "none" ]; then
  echo "  Health:   curl $HEALTH_URL"
fi
echo ""
echo "Usa scripts/run-all-tests.sh para ejecutar los checks declarados por STACK_PROFILE.yaml."
