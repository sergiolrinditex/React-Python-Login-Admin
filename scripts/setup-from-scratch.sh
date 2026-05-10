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

# ---------------------------------------------------------------------------
# ensure_jwt_keypair — BEFORE sourcing .env so keypair is ready for any backend
# startup that calls get_settings() (e.g. seed, health, auth routes).
#
# What it does (idempotent — safe to call N times):
#   1. If .env does not exist → warns and returns (ensure_encryption_key already
#      tried to create it; if it still missing, nothing to do here).
#   2. Reads JWT_PRIVATE_KEY + JWT_PUBLIC_KEY current values from .env.
#   3. Placeholder/absent detection: treats "", "<change-me>", "dev-rsa-*-pem-placeholder"
#      and any value not starting with "-----BEGIN " as sentinel → needs_new=1.
#   4. If markers look valid: python3 deep-validates (parse RSA 2048+ + pyjwt RS256
#      sign+verify roundtrip). Failure → needs_new=1. Regenerates BOTH keys as a
#      pair (never mixes old private with new public or vice versa).
#   5. Generates fresh RSA 2048 keypair via cryptography lib (PKCS8 + SPKI PEM).
#   6. Injects both keys inline into .env (multi-line, double-quoted) via python3.
#   7. Logs masked SHA-256 thumbprint of PUBLIC key (last 4 chars). NEVER logs PEM.
#
# Security rules:
#   - PEM private key is NEVER echoed to stdout/stderr/logs. Only masked thumbprint.
#   - .env is gitignored; it will NEVER be committed by closer.
#   - python3 + cryptography (48.0.0) used for generation — no openssl CLI dependency.
#   - Concurrent double-invocation (R2) accepted as ~0 probability in dev local; no lock.
#
# Slice: P00-S02-T014 (data — dev .env RSA keypair hygiene)
# Ref: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.2 + §11.1
# Decision: D2 (PEM inline SecretStr), D3 (2048 bits), D4 (cryptography lib, no openssl)
# ---------------------------------------------------------------------------
ensure_jwt_keypair() {
  local env_file="$PROJECT_ROOT/.env"
  log "ensure_jwt_keypair: checking JWT_PRIVATE_KEY/JWT_PUBLIC_KEY in $env_file"

  # 1) Bail if .env still missing (ensure_encryption_key already tried to create it).
  if [ ! -f "$env_file" ]; then
    warn "ensure_jwt_keypair: .env not found — skipping (run setup-from-scratch.sh after creating .env)"
    return 0
  fi

  # 2) Read current values — only the first physical line of each key matters for
  #    the marker check; multi-line PEM values start with the BEGIN line.
  #    cut -d= -f2-: greedy (handles base64 '=' padding in existing PEM values).
  local current_priv current_pub
  current_priv="$(grep -E '^JWT_PRIVATE_KEY=' "$env_file" | head -1 | cut -d= -f2- || true)"
  current_pub="$(grep -E '^JWT_PUBLIC_KEY=' "$env_file" | head -1 | cut -d= -f2- || true)"
  # Strip Windows CR if present (R8 guard).
  current_priv="${current_priv%$'\r'}"
  current_pub="${current_pub%$'\r'}"
  # Strip surrounding double quotes (only the outer-most character on each side).
  current_priv="${current_priv#\"}"; current_priv="${current_priv%\"}"
  current_pub="${current_pub#\"}"; current_pub="${current_pub%\"}"

  # 3) Decide if regeneration is needed based on first-line sentinel check.
  local needs_new=0
  case "$current_priv" in
    ""|"<change-me>"|"dev-rsa-private-key-pem-placeholder") needs_new=1 ;;
    "-----BEGIN "*) ;;   # marker present — will deep-validate below
    *) needs_new=1 ;;
  esac
  case "$current_pub" in
    ""|"<change-me>"|"dev-rsa-public-key-pem-placeholder") needs_new=1 ;;
    "-----BEGIN "*) ;;
    *) needs_new=1 ;;
  esac

  # 4) Idempotent fast path: if first-line markers OK, deep-validate via python3
  #    (parse RSA 2048+ + pyjwt RS256 sign+verify roundtrip).
  if [ "$needs_new" -eq 0 ]; then
    if command -v python3 >/dev/null 2>&1; then
      local thumb
      # Pass env_file path; python reads and extracts multi-line PEM values.
      thumb="$(python3 - "$env_file" <<'PYVALIDATE' 2>/dev/null || true
import sys, hashlib
from pathlib import Path

env_file = Path(sys.argv[1])
text = env_file.read_text()

def extract_multiline_env(text: str, key: str) -> str:
    """Extract a (possibly multi-line double-quoted) env var value."""
    import re
    # Match KEY="...content..." spanning multiple lines until closing lone quote.
    # Pattern: KEY="<anything including newlines>"
    m = re.search(
        r'^' + re.escape(key) + r'="((?:[^"\\]|\\.)*)"\s*$',
        text, re.M | re.S
    )
    if m:
        return m.group(1)
    # Fallback: single-line unquoted value
    m = re.search(r'^' + re.escape(key) + r'=(.+)$', text, re.M)
    if m:
        return m.group(1).strip().strip('"')
    return ""

priv_pem = extract_multiline_env(text, "JWT_PRIVATE_KEY")
pub_pem  = extract_multiline_env(text, "JWT_PUBLIC_KEY")

if not priv_pem or not pub_pem:
    sys.exit(2)

try:
    from cryptography.hazmat.primitives import serialization
    pk = serialization.load_pem_private_key(priv_pem.encode(), password=None)
    if pk.key_size < 2048:
        sys.exit(3)
    import jwt as pyjwt
    token = pyjwt.encode({"t": 1}, priv_pem, algorithm="RS256")
    pyjwt.decode(token, pub_pem, algorithms=["RS256"])
    # Print last-4 chars of SHA-256 thumbprint of public key — NEVER the PEM itself.
    print(hashlib.sha256(pub_pem.encode()).hexdigest()[-4:])
except Exception:
    sys.exit(4)
PYVALIDATE
)"
      if [ -n "$thumb" ] && [ "$thumb" != "????" ]; then
        log "ensure_jwt_keypair: JWT keypair already valid (pub thumbprint: ****${thumb}) — no change"
        return 0
      fi
      # Parse or roundtrip failed → regenerate both as a pair.
      warn "ensure_jwt_keypair: existing keys failed deep validation — regenerating as a fresh pair"
      needs_new=1
    else
      # python3 not available — trust marker check; log and skip deep validation.
      log "ensure_jwt_keypair: PEM markers present and python3 unavailable for deep validation — assuming valid, no change"
      return 0
    fi
  fi

  # 5) Generate fresh RSA 2048 keypair via cryptography lib. Graceful warn if venv missing.
  if ! command -v python3 >/dev/null 2>&1; then
    warn "ensure_jwt_keypair: python3 not found — set JWT_PRIVATE_KEY/JWT_PUBLIC_KEY manually in .env."
    return 0
  fi

  # Use ASCII unit-separator (0x1f) as separator — never appears in base64 PEM bodies.
  local generated
  generated="$(python3 -c '
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
priv_pem = priv.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
pub_pem = priv.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()
# Unit-separator (0x1f) cannot appear in PEM base64 bodies — safe delimiter.
import sys
sys.stdout.write(priv_pem + "\x1f" + pub_pem)
' 2>/dev/null || true)"

  if [ -z "$generated" ]; then
    warn "ensure_jwt_keypair: cryptography package not available (backend venv not installed yet?). Run 'pip install -e \".[dev]\"' in backend/, then rerun this script."
    return 0
  fi

  # Split on the unit-separator character (bash parameter expansion).
  local priv_pem pub_pem
  priv_pem="${generated%%$'\x1f'*}"
  pub_pem="${generated##*$'\x1f'}"

  # 6) Inject both keys into .env (multi-line, double-quoted) via python3.
  #    Replaces existing JWT_PRIVATE_KEY / JWT_PUBLIC_KEY lines or appends if absent.
  python3 - "$env_file" "$priv_pem" "$pub_pem" <<'PYINJECT'
import pathlib, re, sys

path = pathlib.Path(sys.argv[1])
priv = sys.argv[2]
pub  = sys.argv[3]
text = path.read_text()

def upsert(text: str, key: str, pem: str) -> str:
    """Replace KEY=<anything> (single or multi-line quoted) or append if absent."""
    # Quoted multi-line: KEY="...\n..."\n
    quoted_val = '"' + pem.rstrip("\n") + '\n"'
    # Pattern covers:
    #   KEY="multi-line-value-ending-with-quote-on-own-line"
    #   KEY=single-line-value
    # We remove the old block and replace it with the new quoted multi-line form.
    pattern = (
        r'^' + re.escape(key) + r'='
        r'(?:"(?:[^"\\]|\\.)*?"'      # double-quoted (possibly multi-line)
        r'|[^\n]*)'                    # or single unquoted line
        r'\n?'
    )
    if re.search(pattern, text, re.M | re.S):
        text = re.sub(pattern, key + "=" + quoted_val + "\n", text, count=1, flags=re.M | re.S)
    else:
        text = text.rstrip() + f"\n{key}={quoted_val}\n"
    return text

text = upsert(text, "JWT_PRIVATE_KEY", priv)
text = upsert(text, "JWT_PUBLIC_KEY",  pub)
path.write_text(text)
PYINJECT

  # 7) Log masked thumbprint of PUBLIC key (last 4 chars of SHA-256). NEVER echo PEM.
  local thumb
  thumb="$(python3 -c "
import hashlib, sys
print(hashlib.sha256(sys.stdin.read().encode()).hexdigest()[-4:])
" <<<"$pub_pem" 2>/dev/null || echo "????")"

  log "ensure_jwt_keypair: generated fresh RSA 2048 keypair — PEM not echoed (pub thumbprint: ****${thumb})"
}

ensure_jwt_keypair

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
