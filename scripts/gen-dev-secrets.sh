#!/usr/bin/env bash
# Idempotent dev-only secrets provisioner for .env.
#
# Slice:  P01-S02-T009 — generate ≥32-byte JWT dev key + default
#         ENABLE_VERBOSE_LOGGING in dev .env
# Phase:  P01 Auth + Data Foundation
# Promoted from FU-20260512044309 (origin P01-S02-T002 verify-slice).
# Source: docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §11.1
#         docs/source-of-truth/01-non-negotiables.md §Logging §Security
#
# Single responsibility:
#   Ensure the developer-local .env file ships a RFC-7518-compliant JWT key
#   and verbose logging enabled BY DEFAULT, without ever overwriting a
#   real human-set value.
#
# Behaviors:
#   1. If .env does not exist, copy .env.example to .env first (idempotent).
#   2. JWT_PRIVATE_KEY:
#        a. Read current value.
#        b. If value matches placeholder pattern ('replace-with-dev-key',
#           empty, or len<32 bytes) → generate a new
#           secrets.token_urlsafe(48) key (~64 url-safe chars, ≥32 bytes)
#           and replace both JWT_PRIVATE_KEY and JWT_PUBLIC_KEY
#           (HS256 symmetric: same key for sign + verify).
#        c. Else → leave untouched (developer set a real key).
#   3. ENABLE_VERBOSE_LOGGING:
#        a. If line exists with value != 'true' → set value to 'true'.
#        b. If line missing → append.
#        c. If already 'true' → no-op.
#   4. Logging (to stderr, NEVER the secret value — only length):
#        BEFORE: '==> gen-dev-secrets.start path=...'
#        per op:  '==> gen-dev-secrets.jwt_private_key.rotated len=N reason=placeholder'
#                 '==> gen-dev-secrets.jwt_private_key.kept len=N reason=already_real'
#                 '==> gen-dev-secrets.enable_verbose_logging.set to=true was=...'
#                 '==> gen-dev-secrets.enable_verbose_logging.kept value=true'
#        AFTER:  '==> gen-dev-secrets.done changed=N'
#        ERROR:  '==> gen-dev-secrets.error context=...'
#        NEVER print the actual key value. Only its length.
#   5. Exit 0 on success (including no-op runs).
#
# Idempotency: running this script twice in a row produces CHANGED=0 on
# the second run — no key rotation, no flag flip.
#
# POSIX portability: no GNU-only flags (no 'sed -i'). Atomic in-place edit
# uses awk + temp file + mv. Compatible with macOS (BSD) and Linux (GNU).
#
# Security contract:
#   - 'set -x' is NOT used (it would print secret in xtrace output).
#   - The generated key is stored in $NEW_KEY only long enough to write
#     the temp file, then immediately unset.
#   - No pipe that carries the key ever touches stdout (stderr is used for
#     all log messages). The cat/awk pipeline writes only to a temp file.
#   - chmod 600 .env enforces file-level access restriction at the end.

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${CLAUDE_PROJECT_DIR:-$SCRIPT_DIR/..}" && pwd)"
ENV_PATH="${ROOT_DIR}/.env"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"

# ---------------------------------------------------------------------------
# Logging helpers (all to stderr; NEVER log secret values)
# ---------------------------------------------------------------------------
log() { printf '==> gen-dev-secrets.%s\n' "$1" >&2; }

# ---------------------------------------------------------------------------
# 1. Ensure .env exists (copy from .env.example if missing)
# ---------------------------------------------------------------------------
if [ ! -f "${ENV_PATH}" ]; then
  if [ ! -f "${ENV_EXAMPLE}" ]; then
    log "error context=missing_env_example path=${ENV_EXAMPLE}"
    exit 1
  fi
  log "env_create from=${ENV_EXAMPLE} to=${ENV_PATH}"
  cp "${ENV_EXAMPLE}" "${ENV_PATH}"
fi

log "start path=${ENV_PATH}"

CHANGED=0

# ---------------------------------------------------------------------------
# 2. Helper: read a variable value from .env (ignores comments + blank lines)
# ---------------------------------------------------------------------------
# Usage: current_value VAR
# Outputs the value (may be empty) or nothing if VAR not present.
current_value() {
  awk -v k="$1" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    /^[^=]+=/ {
      split($0, parts, /=/)
      if (parts[1] == k) {
        sub(/^[^=]*=/, "")
        print
        exit
      }
    }
  ' "${ENV_PATH}"
}

# ---------------------------------------------------------------------------
# 3. Helper: set or append a variable in .env (POSIX-portable, atomic)
# ---------------------------------------------------------------------------
# Usage: set_or_append VAR VALUE
# Writes VALUE to VAR in-place using awk + temp + mv.
# The actual secret value is passed via an awk variable — it never touches
# a shell expansion that would be visible in process listings (no export).
set_or_append() {
  local var="$1"
  local val="$2"
  local tmp
  tmp="$(mktemp "${ENV_PATH}.tmp.XXXXXX")"

  if grep -qE "^${var}=" "${ENV_PATH}"; then
    # Replace existing line (awk prints modified key=value, passes others through)
    awk -v k="${var}" -v v="${val}" '
      /^[^=]+=/ {
        split($0, parts, /=/)
        if (parts[1] == k) {
          print k "=" v
          next
        }
      }
      { print }
    ' "${ENV_PATH}" > "${tmp}"
  else
    # Append a new line at the end
    cat "${ENV_PATH}" > "${tmp}"
    printf '%s=%s\n' "${var}" "${val}" >> "${tmp}"
  fi

  mv "${tmp}" "${ENV_PATH}"
}

# ---------------------------------------------------------------------------
# 4. Helper: generate a new ≥32-byte URL-safe random key via Python stdlib
# ---------------------------------------------------------------------------
gen_jwt_key() {
  python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
}

# ---------------------------------------------------------------------------
# 5. Helper: detect placeholder key (needs rotation)
# ---------------------------------------------------------------------------
# Returns 0 (true) if the value should be rotated.
is_placeholder() {
  local v="$1"
  # Empty, literal placeholder, or shorter than 32 chars → rotate
  [ -z "${v}" ] && return 0
  [ "${v}" = "replace-with-dev-key" ] && return 0
  [ "${#v}" -lt 32 ] && return 0
  return 1
}

# ---------------------------------------------------------------------------
# 6. JWT_PRIVATE_KEY (and JWT_PUBLIC_KEY for HS256 symmetry)
# ---------------------------------------------------------------------------
JWT_CUR="$(current_value JWT_PRIVATE_KEY)"

if is_placeholder "${JWT_CUR}"; then
  # BEFORE: only log intent (no secret)
  log "jwt_private_key.rotate reason=placeholder len_was=${#JWT_CUR}"

  # Generate key; keep in local var only long enough to write temp file
  NEW_KEY="$(gen_jwt_key)"
  NEW_LEN="${#NEW_KEY}"

  set_or_append JWT_PRIVATE_KEY "${NEW_KEY}"
  set_or_append JWT_PUBLIC_KEY  "${NEW_KEY}"  # HS256: same value for sign + verify

  # AFTER: log only length, never the key value
  log "jwt_private_key.rotated len=${NEW_LEN} reason=placeholder"
  log "jwt_public_key.rotated  len=${NEW_LEN} reason=hs256_symmetric"

  # Drop the key from shell memory immediately
  unset NEW_KEY

  CHANGED=$((CHANGED + 2))
else
  log "jwt_private_key.kept len=${#JWT_CUR} reason=already_real"
fi

# ---------------------------------------------------------------------------
# 7. ENABLE_VERBOSE_LOGGING — dev default is 'true'
# ---------------------------------------------------------------------------
EVL_CUR="$(current_value ENABLE_VERBOSE_LOGGING)"

if [ "${EVL_CUR}" != "true" ]; then
  log "enable_verbose_logging.set to=true was=${EVL_CUR:-<missing>}"
  set_or_append ENABLE_VERBOSE_LOGGING "true"
  CHANGED=$((CHANGED + 1))
else
  log "enable_verbose_logging.kept value=true"
fi

# ---------------------------------------------------------------------------
# 8. Restrict file permissions (best-effort; non-fatal)
# ---------------------------------------------------------------------------
chmod 600 "${ENV_PATH}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 9. Done
# ---------------------------------------------------------------------------
log "done changed=${CHANGED}"
exit 0
