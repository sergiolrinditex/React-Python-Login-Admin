#!/usr/bin/env bash
# Diagnose common Chrome DevTools MCP profile-lock problems without killing anything.
set -euo pipefail
PROFILE="${CHROME_DEVTOOLS_MCP_PROFILE:-$HOME/.cache/chrome-devtools-mcp/chrome-profile}"

print_kv() {
  printf '%s: %s\n' "$1" "$2"
}

print_kv "PROFILE" "$PROFILE"
if [ ! -d "$PROFILE" ]; then
  print_kv "PROFILE_EXISTS" "no"
  print_kv "LOCK_STATUS" "clean"
  exit 0
fi
print_kv "PROFILE_EXISTS" "yes"

found=0
active=0
unknown=0
for name in SingletonLock SingletonSocket SingletonCookie lockfile LOCK; do
  path="$PROFILE/$name"
  [ -e "$path" ] || [ -L "$path" ] || continue
  found=1
  print_kv "LOCK_FILE" "$path"
  target=""
  if [ -L "$path" ]; then
    target="$(readlink "$path" 2>/dev/null || true)"
    print_kv "LOCK_TARGET" "$target"
  fi
  candidate="$(printf '%s\n%s\n' "$target" "$path" | sed -n 's/.*[^0-9]\([0-9][0-9][0-9][0-9]*\).*/\1/p' | tail -1)"
  if [ -n "$candidate" ]; then
    if kill -0 "$candidate" 2>/dev/null; then
      active=1
      print_kv "LOCK_PID" "$candidate"
      ps -p "$candidate" -o pid= -o command= 2>/dev/null | sed 's/^/LOCK_PROCESS: /' || true
    else
      unknown=1
      print_kv "STALE_PID_CANDIDATE" "$candidate"
    fi
  else
    unknown=1
  fi
done

if [ "$found" -eq 0 ]; then
  print_kv "LOCK_STATUS" "clean"
  exit 0
fi
if [ "$active" -eq 1 ]; then
  print_kv "LOCK_STATUS" "active_process_holds_profile"
  print_kv "USER_ACTION" "close the Chrome process above or restart Chrome DevTools MCP, then rerun /verify-slice"
  exit 2
fi
if [ "$unknown" -eq 1 ]; then
  print_kv "LOCK_STATUS" "stale_or_unknown_lock_files"
  print_kv "USER_ACTION" "ensure no Chrome DevTools MCP browser is running, then remove stale Singleton* files or restart the MCP server"
  exit 1
fi
print_kv "LOCK_STATUS" "locked_unknown"
exit 1
