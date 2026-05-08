#!/usr/bin/env bash
# Stack-aware development setup. Commands and roots come from STACK_PROFILE.yaml.
#
# --check mode (P00-S01-T001 verify): validates that declared paths and roots exist
# without running migrations, seeds or dev servers. Exits 0 if structure is correct,
# non-zero and prints WARN lines for any missing root that STACK_PROFILE.yaml declares.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$ROOT_DIR}"
STACK="$ROOT_DIR/.claude/bin/stack_profile.py"

CHECK_MODE=0
for arg in "$@"; do
  if [ "$arg" = "--check" ]; then
    CHECK_MODE=1
  fi
done

log()  { echo "==> $1"; }
warn() { echo "WARN: $1" >&2; }
fail() { echo "ERROR: $1" >&2; exit 1; }

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
  if [ "$CHECK_MODE" -eq 1 ]; then
    log "$label: declared (skipped in --check mode): $cmd"
    return
  fi
  log "$label: $cmd"
  ( cd "$PROJECT_ROOT" && bash -lc "$cmd" )
}

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
FRONTEND_EXISTS=1
if [ "$BACKEND_ROOT" != "none" ] && [ ! -d "$PROJECT_ROOT/$BACKEND_ROOT" ]; then
  BACKEND_EXISTS=0
  warn "Backend root $BACKEND_ROOT no existe todavía; skip setup backend."
fi
if [ "$FRONTEND_ROOT" != "none" ] && [ ! -d "$PROJECT_ROOT/$FRONTEND_ROOT" ]; then
  FRONTEND_EXISTS=0
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
