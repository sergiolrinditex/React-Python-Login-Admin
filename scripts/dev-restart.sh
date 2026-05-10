#!/usr/bin/env bash
# scripts/dev-restart.sh
#
# Stack-agnostic dev environment manager. The contract (consumed by
# /next-slice and /verify-slice) is fixed regardless of stack:
#
#   --soft   (default) start only what is down; never restart what is healthy.
#            Auto-soft exit ≤1s when everything is up.
#   --check  report status only; never start/stop/migrate anything.
#            Exit 0 if everything is up, 1 otherwise.
#   --reset  hard reset: stop everything, drop DB to base + migrate + reseed,
#            restart back + front. Destructive — only when explicitly requested.
#
# How it works
# ------------
# This script is a generic dispatcher. The stack-specific commands (how to
# start the backend, how to start the frontend, how to probe health, how to
# reset the DB) live in `scripts/dev-restart.profile.sh`, which this script
# sources. The profile shipped in the orchestrator ZIP is neutral because no default app is bundled. A generated app must replace scripts/dev-restart.profile.sh with stack-specific commands derived from STACK_PROFILE.yaml; never edit this dispatcher for stack changes.
#
# Profile contract (each function returns 0 on success / non-zero on fail):
#   back_health        → quick health probe, exit 0 if up
#   back_start         → start backend (background), echo PID to BACK_PID_FILE
#   back_url           → human-readable URL for the status table
#   front_health       → quick health probe, exit 0 if up
#   front_start        → start frontend (background), echo PID to FRONT_PID_FILE
#   front_url          → human-readable URL for the status table
#   db_health          → 0 if DB reachable, 1 if down, 2 if unknown (back down)
#   db_reset           → migrate down + up + seed (only called by --reset)
#
# The profile may read .env (auto-sourced before the profile is loaded) and
# may use any helpers it wants; it MUST set BACK_PID_FILE / FRONT_PID_FILE
# (or accept the defaults below).
#
# Logs default to:
#   orchestrator-state/dev-logs/back.log    backend stdout+stderr
#   orchestrator-state/dev-logs/front.log   frontend stdout+stderr
#   orchestrator-state/dev-logs/back.pid    backend PID
#   orchestrator-state/dev-logs/front.pid   frontend PID

set -euo pipefail

# --- Paths and helpers ------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/orchestrator-state/dev-logs"
mkdir -p "${LOG_DIR}"

BACK_LOG="${LOG_DIR}/back.log"
FRONT_LOG="${LOG_DIR}/front.log"
BACK_PID_FILE="${LOG_DIR}/back.pid"
FRONT_PID_FILE="${LOG_DIR}/front.pid"

export ROOT_DIR LOG_DIR BACK_LOG FRONT_LOG BACK_PID_FILE FRONT_PID_FILE

log()   { printf '==> %s\n' "$1"; }
warn()  { printf 'WARN: %s\n' "$1" >&2; }
fail()  { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
info()  { printf '     %s\n' "$1"; }
export -f log warn fail info

# --- Args -------------------------------------------------------------------

MODE="--soft"
case "${1:-}" in
  --soft|--check|--reset) MODE="$1" ;;
  "" )                    MODE="--soft" ;;
  -h|--help)
    sed -n '1,55p' "$0"
    exit 0
    ;;
  *) fail "Unknown flag: $1 (expected --soft | --check | --reset)" ;;
esac

# --- Load .env --------------------------------------------------------------

if [ -f "${ROOT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

# --- Generic helpers (available to the profile) -----------------------------

pid_alive() {
  local pidfile="$1"
  [ -f "$pidfile" ] || return 1
  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}
export -f pid_alive

stop_pidfile() {
  local pidfile="$1" name="$2"
  if pid_alive "$pidfile"; then
    local pid
    pid="$(cat "$pidfile")"
    log "Stopping ${name} (pid ${pid})..."
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      warn "${name} did not exit; sending SIGKILL"
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$pidfile"
}
export -f stop_pidfile

stop_orphan_on_port() {
  local port="$1" name="$2"
  local pid
  pid="$(lsof -ti :"$port" 2>/dev/null | head -1 || true)"
  if [ -n "$pid" ]; then
    warn "Orphan process on :${port} (pid ${pid}) — killing for ${name} reset"
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  fi
}
export -f stop_orphan_on_port

wait_for() {
  # wait_for <probe-fn-name> <timeout-seconds> <human-name>
  # Returns 0 as soon as the probe succeeds; 1 on timeout.
  local fn="$1" timeout="$2" name="$3"
  # `_` makes the loop counter explicitly unused (silences SC2034).
  for _ in $(seq 1 "$timeout"); do
    if "$fn" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  warn "${name} did not respond within ${timeout}s"
  return 1
}
export -f wait_for

# --- Load the stack profile -------------------------------------------------
#
# Resolution order:
#   1. ${ROOT_DIR}/scripts/dev-restart.profile.sh — the per-project profile.
#      A feature-app overrides the stack here. The template ships a neutral profile; generated apps replace it with real stack commands.
#   2. (no fallback) — if the profile is missing, abort with a clear error
#      so the project is forced to declare its stack explicitly.

PROFILE="${ROOT_DIR}/scripts/dev-restart.profile.sh"
if [ ! -f "${PROFILE}" ]; then
  fail "Missing ${PROFILE}. Each project must declare its stack profile.
       The template ships scripts/dev-restart.profile.sh — restore it from
       git or copy from your TECHNICAL_GUIDE example."
fi
# shellcheck disable=SC1090
source "${PROFILE}"

# Verify the profile defined the contract.
for required_fn in back_health back_start back_url front_health front_start front_url db_health db_reset; do
  if ! declare -F "${required_fn}" >/dev/null 2>&1; then
    fail "Profile ${PROFILE} did not define required function: ${required_fn}"
  fi
done

# --- Status reporter --------------------------------------------------------

print_status() {
  local back_state front_state db_state
  if back_health  >/dev/null 2>&1; then back_state="UP";   else back_state="DOWN"; fi
  if front_health >/dev/null 2>&1; then front_state="UP";  else front_state="DOWN"; fi
  case "$(db_health >/dev/null 2>&1; echo $?)" in
    0) db_state="UP" ;;
    2) db_state="UNKNOWN" ;;
    *) db_state="DOWN" ;;
  esac

  printf '\n'
  printf '  Service   URL                        Status\n'
  printf '  --------- -------------------------- -------\n'
  printf '  backend   %-26s %s\n' "$(back_url)"  "${back_state}"
  printf '  frontend  %-26s %s\n' "$(front_url)" "${front_state}"
  printf '  database  %-26s %s\n' "(via /ready)" "${db_state}"
  printf '\n'
  printf '  Logs: %s  %s\n' "${BACK_LOG}" "${FRONT_LOG}"
  printf '\n'
}

# --- Mode dispatch ----------------------------------------------------------

case "${MODE}" in
  --check)
    print_status
    if back_health >/dev/null 2>&1 && front_health >/dev/null 2>&1 && db_health >/dev/null 2>&1; then
      log "All services UP."
      exit 0
    fi
    log "One or more services DOWN."
    exit 1
    ;;

  --soft)
    BACK_OK=0; FRONT_OK=0
    back_health  >/dev/null 2>&1 && BACK_OK=1
    front_health >/dev/null 2>&1 && FRONT_OK=1
    if [ "${BACK_OK}" = 1 ] && [ "${FRONT_OK}" = 1 ]; then
      log "Soft: everything healthy. Nothing to do."
      print_status
      exit 0
    fi
    [ "${BACK_OK}"  = 0 ] && back_start
    [ "${FRONT_OK}" = 0 ] && front_start
    print_status
    ;;

  --reset)
    log "Hard reset requested."
    stop_pidfile      "${FRONT_PID_FILE}" "frontend"
    stop_pidfile      "${BACK_PID_FILE}"  "backend"
    db_reset
    back_start
    front_start
    print_status
    log "Reset complete."
    ;;
esac
