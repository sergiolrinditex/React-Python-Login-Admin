#!/usr/bin/env bash
# Stack-aware development setup. Commands and roots come from STACK_PROFILE.yaml.
#
# --check mode (P00-S01-T001 verify): validates that declared paths and roots exist
# without running migrations, seeds or dev servers. Exits 0 if structure is correct,
# non-zero and prints WARN lines for any missing root that STACK_PROFILE.yaml declares.
#
# Updated: P00-S02-T011 — ensure_encryption_key() generates a valid Fernet ENCRYPTION_KEY
# in .env if missing, a placeholder, or carrying the legacy PROVIDER_ENCRYPTION_KEY name.
# Idempotent: a second run with a valid key already present does nothing.
# Security: the key value is NEVER echoed to stdout/stderr/logs — only masked last-4 chars.
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

# ---------------------------------------------------------------------------
# ensure_encryption_key — BEFORE sourcing .env so the key is ready for seed/
# migration steps that consume ENCRYPTION_KEY via os.environ.
#
# What it does (idempotent — safe to call N times):
#   1. If .env does not exist but .env.example does → copies it.
#   2. Drops legacy PROVIDER_ENCRYPTION_KEY line if present (deprecated by P01-S01-T002).
#   3. If ENCRYPTION_KEY is absent, a placeholder ("<change-me>"), or the old
#      deprecated placeholder value → generates a fresh Fernet key via python3.
#   4. If ENCRYPTION_KEY already has a non-placeholder value → leaves it untouched.
#
# Security rules:
#   - The generated key is NEVER echoed. Only masked last-4 chars are logged.
#   - .env is gitignored; it will NEVER be committed by closer.
#   - The in-place replacement uses python3 re.sub + pathlib to avoid the
#     portability issues of 'sed -i' between macOS and Linux.
#
# Slice: P00-S02-T011 (data — dev .env hygiene)
# Ref: HILO_PEOPLE_TECHNICAL_GUIDE.md §11.1
# ---------------------------------------------------------------------------
ensure_encryption_key() {
  local env_file="$PROJECT_ROOT/.env"
  local example_file="$PROJECT_ROOT/.env.example"

  log "ensure_encryption_key: checking ENCRYPTION_KEY in $env_file"

  # 1) Create .env from .env.example if it does not exist.
  if [ ! -f "$env_file" ] && [ -f "$example_file" ]; then
    log "ensure_encryption_key: .env not found — creating from .env.example"
    cp "$example_file" "$env_file"
  fi

  if [ ! -f "$env_file" ]; then
    warn "ensure_encryption_key: .env does not exist and no .env.example found — skipping"
    return 0
  fi

  # 2) Remove legacy PROVIDER_ENCRYPTION_KEY line if present (renamed in P01-S01-T002).
  if grep -q '^PROVIDER_ENCRYPTION_KEY=' "$env_file"; then
    log "ensure_encryption_key: removing deprecated PROVIDER_ENCRYPTION_KEY from .env (renamed to ENCRYPTION_KEY in P01-S01-T002)"
    python3 -c "
import pathlib, re
path = pathlib.Path('$env_file')
text = path.read_text()
text = re.sub(r'^PROVIDER_ENCRYPTION_KEY=.*\n?', '', text, flags=re.M)
path.write_text(text)
"
  fi

  # 3) Check whether ENCRYPTION_KEY needs to be generated.
  local current_key
  current_key="$(grep -E '^ENCRYPTION_KEY=' "$env_file" | head -1 | cut -d= -f2- || true)"
  current_key="${current_key%$'\r'}"  # strip Windows CR if present

  local needs_new=0
  if [ -z "$current_key" ] \
      || [ "$current_key" = "<change-me>" ] \
      || [ "$current_key" = "dev-encryption-key-placeholder" ]; then
    needs_new=1
  fi

  if [ "$needs_new" -eq 0 ]; then
    # Key already present and not a placeholder — idempotent, nothing to do.
    local masked
    masked="${current_key: -4}"
    log "ensure_encryption_key: ENCRYPTION_KEY already set (masked: ****${masked}) — no change"
    return 0
  fi

  # 4) Generate a fresh Fernet key.
  if ! command -v python3 >/dev/null 2>&1; then
    warn "ensure_encryption_key: python3 not found — cannot generate Fernet key. Set ENCRYPTION_KEY manually in .env before running seeds."
    return 0
  fi

  local generated_key
  generated_key="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null || true)"

  if [ -z "$generated_key" ]; then
    warn "ensure_encryption_key: cryptography package not available (backend venv not installed yet?). Run 'pip install -e \".[dev]\"' in backend/, then rerun this script."
    return 0
  fi

  # Inject key: replace existing ENCRYPTION_KEY line or append if absent.
  python3 - "$env_file" "$generated_key" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
text = path.read_text()
if re.search(r'^ENCRYPTION_KEY=', text, re.M):
    text = re.sub(r'^ENCRYPTION_KEY=.*$', 'ENCRYPTION_KEY=' + key, text, count=1, flags=re.M)
else:
    text += f'\nENCRYPTION_KEY={key}\n'
path.write_text(text)
PY

  local masked="${generated_key: -4}"
  log "ensure_encryption_key: generated fresh Fernet ENCRYPTION_KEY — value not echoed (masked: ****${masked})"
}

ensure_encryption_key

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
