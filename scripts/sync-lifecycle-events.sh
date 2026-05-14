#!/usr/bin/env bash
set -euo pipefail
ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-}"
if [ -z "$ROOT" ]; then
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
fi
exec python3 -B -S "$ROOT/.claude/bin/sync_lifecycle_events.py" "$@"
