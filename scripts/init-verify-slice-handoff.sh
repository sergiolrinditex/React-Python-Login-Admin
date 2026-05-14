#!/usr/bin/env bash
set -euo pipefail

if [ -n "${CLAUDE_ORCHESTRATOR_ROOT:-}" ]; then
  ROOT="$CLAUDE_ORCHESTRATOR_ROOT"
elif [ -x "scripts/ensure-task-worktree.sh" ]; then
  ROOT="$(bash scripts/ensure-task-worktree.sh --print-root 2>/dev/null || pwd)"
else
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

exec python3 -B -S "$ROOT/.claude/bin/init_verify_slice_handoff.py" "$@"
