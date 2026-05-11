#!/usr/bin/env bash
# scripts/setup-from-scratch.sh
#
# Hilo People — project structure validator and setup helper.
# Slice: P00-S01-T001 — Repo scaffold + scripts + env.
#
# Modes:
#   --check   Validate that all required files exist. Exit 0 if OK, 1 if any
#             are missing. Never installs, migrates or starts services.
#             Used by acceptance gates (CI, slice verification, pre-condition checks).
#   (default) Run full declarative setup: load .env, run DB migrations and seed.
#             Declares commands declared in STACK_PROFILE.yaml but does NOT
#             start dev servers (use scripts/dev-restart.sh for that).
#
# Usage:
#   bash scripts/setup-from-scratch.sh --check   # structure check only
#   bash scripts/setup-from-scratch.sh            # full setup (install skipped here; see T002/T003)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$ROOT_DIR}"
STACK="$ROOT_DIR/.claude/bin/stack_profile.py"

log()  { echo "==> $1"; }
warn() { echo "WARN: $1" >&2; }
fail() { echo "ERROR: $1" >&2; exit 1; }
ok()   { echo "  [OK] $1"; }
missing() { echo "  [MISSING] $1" >&2; MISSING_COUNT=$((MISSING_COUNT + 1)); }

get_profile() {
  python3 -B -S "$STACK" --root "$PROJECT_ROOT" --get "$1" --default "$2"
}

# ─────────────────────────────────────────────────────────────────────────────
# --check mode: validate required file structure, exit 0/1
# ─────────────────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--check" ]]; then
  log "Checking project file structure (--check mode)..."
  MISSING_COUNT=0

  # Required files as per P00-S01-T001 deliverables checklist.
  REQUIRED_FILES=(
    "package.json"
    "frontend/package.json"
    "backend/pyproject.toml"
    "backend/app/main.py"
    "backend/app/__init__.py"
    ".env.example"
    "scripts/dev-restart.profile.sh"
    "scripts/dev-restart.sh"
    "scripts/setup-from-scratch.sh"
  )

  # Accept either pyproject.toml OR requirements*.txt for backend deps.
  BACKEND_DEPS_OK=0
  if [ -f "$PROJECT_ROOT/backend/pyproject.toml" ]; then
    BACKEND_DEPS_OK=1
  fi
  if ls "$PROJECT_ROOT/backend/requirements"*.txt 2>/dev/null | grep -q .; then
    BACKEND_DEPS_OK=1
  fi

  for rel in "${REQUIRED_FILES[@]}"; do
    if [[ "$rel" == "backend/pyproject.toml" ]]; then
      # Handled separately above.
      continue
    fi
    full="$PROJECT_ROOT/$rel"
    if [ -f "$full" ]; then
      ok "$rel"
    else
      missing "$rel"
    fi
  done

  # Report backend deps status.
  if [ "$BACKEND_DEPS_OK" = "1" ]; then
    ok "backend/pyproject.toml (or requirements*.txt)"
  else
    missing "backend/pyproject.toml (or requirements*.txt) — at least one required"
    MISSING_COUNT=$((MISSING_COUNT + 1))
  fi

  # Check test files (smoke tests are part of P00-S01-T001 deliverables).
  TEST_FILES=(
    "backend/tests/__init__.py"
    "backend/tests/test_health.py"
  )
  for rel in "${TEST_FILES[@]}"; do
    full="$PROJECT_ROOT/$rel"
    if [ -f "$full" ]; then
      ok "$rel"
    else
      warn "$rel (optional smoke test — expected from P00-S01-T001)"
    fi
  done

  echo ""
  if [ "$MISSING_COUNT" -eq 0 ]; then
    log "All required files present. Structure check passed."
    exit 0
  else
    fail "$MISSING_COUNT required file(s) missing. See MISSING entries above."
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Default mode: full declarative setup
# ─────────────────────────────────────────────────────────────────────────────

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
  warn ".env not found. Continuing — stack profile may point to external services."
fi

BACKEND_EXISTS=1
if [ "$BACKEND_ROOT" != "none" ] && [ ! -d "$PROJECT_ROOT/$BACKEND_ROOT" ]; then
  BACKEND_EXISTS=0
  warn "Backend root $BACKEND_ROOT does not exist yet; skipping backend setup."
fi

if [ "$FRONTEND_ROOT" != "none" ] && [ ! -d "$PROJECT_ROOT/$FRONTEND_ROOT" ]; then
  warn "Frontend root $FRONTEND_ROOT does not exist yet; skipping frontend setup."
fi

if [ "$BACKEND_EXISTS" -eq 0 ]; then
  log "DB migrations: backend root $BACKEND_ROOT not found, skip"
  log "DB seed: backend root $BACKEND_ROOT not found, skip"
else
  run_if_declared "DB migrations" "$DB_MIGRATE_CMD"
  run_if_declared "DB seed" "$DB_SEED_CMD"
fi

echo ""
log "Declarative setup complete."
echo ""
echo "Commands declared for dev launch:"
echo "  Backend:  $BACKEND_DEV_CMD"
echo "  Frontend: $FRONTEND_DEV_CMD"
if [ "$HEALTH_URL" != "none" ]; then
  echo "  Health:   curl $HEALTH_URL"
fi
echo ""
echo "Run scripts/run-all-tests.sh to execute checks declared in STACK_PROFILE.yaml."
