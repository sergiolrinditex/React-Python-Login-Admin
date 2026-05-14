#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Hook-safe housekeeping: if a previous closer deferred deletion of its active
# worktree, remove it now from the canonical root before listing new work.
# This never changes DAG state; failures are warnings because dirty worktrees
# should not hide ready tasks.
if [ -x "$ROOT/scripts/cleanup-deferred-worktrees.sh" ]; then
  if ! bash "$ROOT/scripts/cleanup-deferred-worktrees.sh" --apply --quiet; then
    echo "WARN: deferred worktree cleanup incomplete; run: bash scripts/cleanup-deferred-worktrees.sh --apply" >&2
  fi
fi
python3 -B -S "$ROOT/.claude/bin/next_wave.py" "$@"
