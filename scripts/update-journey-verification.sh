#!/usr/bin/env bash
set -euo pipefail
ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
if [ -x "$ROOT/scripts/ensure-task-worktree.sh" ]; then
  ROOT="$(bash "$ROOT/scripts/ensure-task-worktree.sh" --print-root)"
fi
exec python3 -B -S "$ROOT/.claude/bin/update_journey_verification.py" "$@"
