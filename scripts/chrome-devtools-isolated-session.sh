#!/usr/bin/env bash
# Print/start a per-TASK_ID Chrome profile for Chrome DevTools MCP isolation.
# This does not configure Claude Code by itself; it gives the safe browser-url
# and profile path to use when the chrome-devtools MCP is configured in
# --browser-url mode. For normal no-auth runs, prefer configuring the MCP with
# chrome-devtools-mcp --isolated.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/chrome-devtools-isolated-session.sh --task <TASK_ID> [--url <URL>] [--start]

Prints a per-task Chrome profile, remote-debugging port and browser-url for
Chrome DevTools MCP isolation. With --start it launches Chrome with that profile.

Recommended policy:
  - use Chrome DevTools MCP first for /verify-slice.
  - no login/MFA: configure chrome-devtools MCP with --isolated, or use this
    script with --browser-url mode for per-TASK_ID parallel runs.
  - login/MFA/2FA/CAPTCHA: still try Chrome DevTools first with this visible
    per-TASK_ID Chrome session; the user can complete the human step there.
  - if Chrome DevTools cannot be used, fall back to claude-in-chrome, then to
    Agent360 Browser MCP (browser-mcp).
EOF
}

TASK_ID="${CLAUDE_ACTIVE_TASK_ID:-}"
URL="about:blank"
START=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --task)
      [ "$#" -ge 2 ] || { echo "ERROR: --task requires TASK_ID" >&2; exit 2; }
      TASK_ID="$2"
      shift 2
      ;;
    --url)
      [ "$#" -ge 2 ] || { echo "ERROR: --url requires URL" >&2; exit 2; }
      URL="$2"
      shift 2
      ;;
    --start)
      START=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$TASK_ID" ]; then
  echo "ERROR: TASK_ID required via --task or CLAUDE_ACTIVE_TASK_ID" >&2
  exit 2
fi

if ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  ROOT="$(pwd)"
fi

safe_task="$(printf '%s' "$TASK_ID" | sed 's/[^A-Za-z0-9_.-]/-/g')"
repo_key="$(printf '%s' "$ROOT" | cksum | awk '{print $1}')"
base="${CLAUDE_BROWSER_MCP_CACHE:-$HOME/.cache/orquestador/browser-mcp}"
profile="$base/chrome-devtools/$repo_key/$safe_task"
port="$(printf '%s' "$ROOT:$TASK_ID" | cksum | awk '{print 9300 + ($1 % 500)}')"
browser_url="http://127.0.0.1:$port"

printf 'TASK_ID: %s\n' "$TASK_ID"
printf 'CHROME_DEVTOOLS_PROFILE: %s\n' "$profile"
printf 'CHROME_DEVTOOLS_REMOTE_DEBUGGING_PORT: %s\n' "$port"
printf 'CHROME_DEVTOOLS_BROWSER_URL: %s\n' "$browser_url"
printf 'MCP_CONFIG_HINT: chrome-devtools-mcp --browser-url=%s\n' "$browser_url"
printf 'START_URL: %s\n' "$URL"

if [ "$START" -ne 1 ]; then
  printf 'START_COMMAND: bash scripts/chrome-devtools-isolated-session.sh --task %s --url %s --start\n' "$TASK_ID" "$URL"
  exit 0
fi

mkdir -p "$profile"

if [ -n "${CHROME_BINARY:-}" ]; then
  "$CHROME_BINARY" --remote-debugging-port="$port" --user-data-dir="$profile" --no-first-run --new-window "$URL" >/dev/null 2>&1 &
elif command -v google-chrome >/dev/null 2>&1; then
  google-chrome --remote-debugging-port="$port" --user-data-dir="$profile" --no-first-run --new-window "$URL" >/dev/null 2>&1 &
elif command -v chromium >/dev/null 2>&1; then
  chromium --remote-debugging-port="$port" --user-data-dir="$profile" --no-first-run --new-window "$URL" >/dev/null 2>&1 &
elif command -v chromium-browser >/dev/null 2>&1; then
  chromium-browser --remote-debugging-port="$port" --user-data-dir="$profile" --no-first-run --new-window "$URL" >/dev/null 2>&1 &
elif [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
  open -na "Google Chrome" --args --remote-debugging-port="$port" --user-data-dir="$profile" --no-first-run --new-window "$URL"
else
  echo "ERROR: could not find Chrome/Chromium. Set CHROME_BINARY=/path/to/chrome" >&2
  exit 1
fi

printf 'STARTED: yes\n'
printf 'NEXT: configure/use Chrome DevTools MCP with --browser-url=%s, then rerun /verify-slice %s\n' "$browser_url" "$TASK_ID"
