#!/usr/bin/env bash
# Hilo People — Idempotent dev secrets provisioner.
#
# Slice:  P02-S03-T004 — Rotate ENCRYPTION_KEY in dev .env + seed active AI provider
# Phase:  P02 Core Features
# Purpose: Rotates ENCRYPTION_KEY (and optionally MFA_ENCRYPTION_KEY, JWT_PRIVATE_KEY,
#          JWT_PUBLIC_KEY) in the dev .env file when values are placeholders.
#          IDEMPOTENT: a second run produces changed=0 when keys are already real.
#          NEVER prints secret values — only key lengths and status codes.
#
# Usage: bash scripts/gen-dev-secrets.sh [--env <path>]
#        (default: .env in repo root, resolved relative to this script)
#
# Exit codes:
#   0 — success (keys rotated or already valid)
#   1 — .env file not found
#
# Logging to stderr:
#   gen-dev-secrets.<key>.<status> len=N reason=...
#   All status messages are machine-readable key=value pairs.
#   NO secret values are ever printed.
#
# POSIX-portable: BSD awk (macOS) + GNU awk (Linux). No sed -i.
# SECURITY: set +x to prevent xtrace from leaking key expansions to stderr.
#
# Source refs:
#   - 01-non-negotiables.md §Security, §Logging ("never log tokens/passwords/PII")
#   - D-T004-A1: Fernet.generate_key() pattern
#   - D-T004-A2: placeholder-only rotation
#   - D-T004-A3: never print secret values
#   - D-T004-A7: Fernet constructor-only validity smoke test
#   - instrucciones.md §9 Logging
set +x  # SECURITY: never xtrace secrets
set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve root and .env path
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_PATH="$ROOT_DIR/.env"

# Allow override via --env flag
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_PATH="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Guard: .env must exist
# ---------------------------------------------------------------------------
if [ ! -f "$ENV_PATH" ]; then
  echo "gen-dev-secrets.error event=env_file_not_found path=$ENV_PATH" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Logging helpers — STDERR only; never print key values
# ---------------------------------------------------------------------------
_log() {
  echo "$@" >&2
}

# ---------------------------------------------------------------------------
# Generate a fresh Fernet key using Python (44-char url-safe base64 + =).
# Returns: prints key on stdout for capture.
# Never echoes the key to stderr.
# ---------------------------------------------------------------------------
_generate_fernet_key() {
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

# ---------------------------------------------------------------------------
# Validate that a string is a usable Fernet key (constructor smoke test).
# Returns 0 if valid, non-zero if not.
# No output — validation only.
# ---------------------------------------------------------------------------
_validate_fernet_key() {
  local key="$1"
  python3 -c "
from cryptography.fernet import Fernet
import sys
try:
    Fernet(sys.argv[1].encode())
    sys.exit(0)
except Exception:
    sys.exit(1)
" "$key" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Generate a JWT/secrets key (url-safe 64 chars, ≥48 bytes entropy).
# Returns: prints key on stdout.
# ---------------------------------------------------------------------------
_generate_jwt_key() {
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
}

# ---------------------------------------------------------------------------
# Check if a value looks like a placeholder (not a real key).
# Placeholders: 'replace-with-dev-key', 'replace-with-fernet-key-from-generate_key',
# or values shorter than 32 chars.
# Returns: 0 if placeholder, 1 if already a real key.
# ---------------------------------------------------------------------------
_is_placeholder() {
  local val="$1"
  local min_len="${2:-32}"
  if [ -z "$val" ] || \
     [ "$val" = "replace-with-dev-key" ] || \
     [ "$val" = "replace-with-fernet-key-from-generate_key" ] || \
     [ "${#val}" -lt "$min_len" ]; then
    return 0  # is placeholder
  fi
  return 1  # not placeholder
}

# ---------------------------------------------------------------------------
# Replace a single KEY=value line in .env using awk + tmpfile (POSIX portable).
# Arguments: env_path key new_value
# ---------------------------------------------------------------------------
_replace_env_line() {
  local env_path="$1"
  local key="$2"
  local new_val="$3"
  local tmp
  tmp="$(mktemp "${env_path}.tmp.XXXXXX")"

  awk -v K="$key" -v V="$new_val" '
    BEGIN { FS="="; OFS="=" }
    /^[[:space:]]*#/ { print; next }
    NF >= 2 && $1 == K {
      # Replace only the first occurrence
      if (!replaced) {
        print K "=" V
        replaced = 1
      } else {
        print
      }
      next
    }
    { print }
  ' "$env_path" > "$tmp"

  mv "$tmp" "$env_path"
  chmod 600 "$env_path"
}

# ---------------------------------------------------------------------------
# Read a key's current value from .env.
# Returns: prints the value (may be empty).
# ---------------------------------------------------------------------------
_read_env_value() {
  local env_path="$1"
  local key="$2"
  awk -v K="$key" '
    /^[[:space:]]*#/ { next }
    NF >= 1 && index($0, "=") > 0 {
      split($0, a, "=")
      if (a[1] == K) {
        # Join remaining parts (value may contain =)
        val = ""
        for (i=2; i<=length(a); i++) {
          if (i > 2) val = val "="
          val = val a[i]
        }
        print val
        exit
      }
    }
  ' "$env_path"
}

# ---------------------------------------------------------------------------
# Rotate ENCRYPTION_KEY (Fernet key)
# ---------------------------------------------------------------------------
_CHANGED=0

_rotate_fernet_key() {
  local key_name="$1"
  local current
  current="$(_read_env_value "$ENV_PATH" "$key_name")"

  if _is_placeholder "$current" 44; then
    _log "gen-dev-secrets.${key_name}.before event=placeholder_detected key_len=${#current}"
    local new_key
    new_key="$(_generate_fernet_key)"
    # Validate the generated key (constructor smoke test — D-T004-A7)
    if ! _validate_fernet_key "$new_key"; then
      _log "gen-dev-secrets.${key_name}.error event=generated_key_invalid"
      exit 1
    fi
    _replace_env_line "$ENV_PATH" "$key_name" "$new_key"
    local after_len="${#new_key}"
    _log "gen-dev-secrets.${key_name}.rotated event=key_rotated key_len=${after_len} placeholder_detected=true"
    _CHANGED=$(( _CHANGED + 1 ))
  else
    _log "gen-dev-secrets.${key_name}.kept event=key_valid_already key_len=${#current} reason=non_placeholder"
  fi
}

# ---------------------------------------------------------------------------
# Rotate JWT_PRIVATE_KEY + JWT_PUBLIC_KEY (symmetric HS256 key)
# ---------------------------------------------------------------------------
_rotate_jwt_key() {
  local key_name="$1"
  local current
  current="$(_read_env_value "$ENV_PATH" "$key_name")"

  if _is_placeholder "$current" 32; then
    _log "gen-dev-secrets.${key_name}.before event=placeholder_detected key_len=${#current}"
    local new_key
    new_key="$(_generate_jwt_key)"
    _replace_env_line "$ENV_PATH" "$key_name" "$new_key"
    local after_len="${#new_key}"
    _log "gen-dev-secrets.${key_name}.rotated event=key_rotated key_len=${after_len} placeholder_detected=true"
    _CHANGED=$(( _CHANGED + 1 ))
  else
    _log "gen-dev-secrets.${key_name}.kept event=key_valid_already key_len=${#current} reason=non_placeholder"
  fi
}

# ---------------------------------------------------------------------------
# Ensure ENABLE_VERBOSE_LOGGING=true in dev .env
# ---------------------------------------------------------------------------
_ensure_verbose_logging() {
  local current
  current="$(_read_env_value "$ENV_PATH" "ENABLE_VERBOSE_LOGGING")"
  if [ "$current" != "true" ]; then
    _replace_env_line "$ENV_PATH" "ENABLE_VERBOSE_LOGGING" "true"
    _log "gen-dev-secrets.ENABLE_VERBOSE_LOGGING.set event=set_true"
    _CHANGED=$(( _CHANGED + 1 ))
  else
    _log "gen-dev-secrets.ENABLE_VERBOSE_LOGGING.kept event=already_true"
  fi
}

# ---------------------------------------------------------------------------
# Main rotation sequence
# ---------------------------------------------------------------------------
_log "gen-dev-secrets.start event=provisioner_start env=$ENV_PATH"

# 1. Rotate ENCRYPTION_KEY (Fernet — required for ai_provider_credentials)
_rotate_fernet_key "ENCRYPTION_KEY"

# 2. Rotate JWT_PRIVATE_KEY and JWT_PUBLIC_KEY
_rotate_jwt_key "JWT_PRIVATE_KEY"
_rotate_jwt_key "JWT_PUBLIC_KEY"

# 3. Ensure ENABLE_VERBOSE_LOGGING=true for dev
_ensure_verbose_logging

_log "gen-dev-secrets.done event=provisioner_done changed=${_CHANGED}"

# Machine-readable summary line (one per run, on stdout for scripting)
echo "gen-dev-secrets.summary changed=${_CHANGED}"
exit 0
