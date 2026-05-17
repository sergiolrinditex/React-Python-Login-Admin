#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Keep subagent operational memory small before computing a new frontier.
# This is safe runtime housekeeping: originals are archived byte-for-byte and
# the files live under gitignored orchestrator-state/agent-memory/. Disable with
# CLAUDE_AUTO_COMPACT_AGENT_MEMORY=0.
if [ "${CLAUDE_AUTO_COMPACT_AGENT_MEMORY:-1}" != "0" ] && [ -f "$ROOT/scripts/compact-agent-memory.py" ]; then
  threshold="${CLAUDE_AGENT_MEMORY_COMPACT_THRESHOLD_LINES:-250}"
  if ! python3 -B -S "$ROOT/scripts/compact-agent-memory.py" --all --apply --threshold-lines "$threshold" --quiet; then
    echo "WARN: agent memory auto-compaction incomplete; run: python3 -B -S scripts/compact-agent-memory.py --all --apply --threshold-lines $threshold" >&2
  fi
fi

# Hook-safe housekeeping: if a previous closer deferred deletion of its active
# worktree, remove it now from the canonical root before listing new work.
# This never changes DAG state; failures are warnings because dirty worktrees
# should not hide ready tasks.
if [ -f "$ROOT/scripts/cleanup-deferred-worktrees.sh" ]; then
  if ! bash "$ROOT/scripts/cleanup-deferred-worktrees.sh" --apply --quiet; then
    echo "WARN: deferred worktree cleanup incomplete; run: bash scripts/cleanup-deferred-worktrees.sh --apply" >&2
  fi
fi
# Replay committed close events before computing the next wave. This repairs
# local registry state after PR squash-merge/reset without committing runtime files.
if [ -f "$ROOT/scripts/sync-lifecycle-events.sh" ]; then
  bash "$ROOT/scripts/sync-lifecycle-events.sh" --apply >/dev/null 2>&1 || true
fi

# Safe branch/worktree housekeeping for tasks already proven closed. This is
# intentionally conservative: it only removes clean worktrees and local dev/* or
# feature/* task branches for TASK_IDs that are done via registry/lifecycle-events.
# Dirty or active checkouts are never discarded.
if [ -f "$ROOT/scripts/cleanup-closed-task-worktrees.sh" ]; then
  if ! bash "$ROOT/scripts/cleanup-closed-task-worktrees.sh" --apply --quiet; then
    echo "WARN: closed task worktree cleanup incomplete; run: bash scripts/cleanup-closed-task-worktrees.sh --apply --verbose" >&2
  fi
fi
python3 -B -S "$ROOT/.claude/bin/next_wave.py" "$@"
