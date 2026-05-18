#!/usr/bin/env bash
set -euo pipefail
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
resolve_canonical_root() {
  local common_dir
  if git -C "$SCRIPT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    common_dir="$(git -C "$SCRIPT_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
    if [ -n "$common_dir" ] && [ "$(basename "$common_dir")" = ".git" ] && [ -d "$(dirname "$common_dir")" ]; then
      (cd "$(dirname "$common_dir")" && pwd -P)
      return 0
    fi
  fi
  printf '%s\n' "$SCRIPT_ROOT"
}
ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-$(resolve_canonical_root)}"
cd "$ROOT"
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


# Keep canonical main aligned with origin/main before computing a new frontier.
# Product/source-of-truth dirty changes block the wave; local runtime files are
# backed up/restored by runtime-git-guard. Disable only for emergency inspection
# with CLAUDE_SKIP_MAIN_SYNC_BEFORE_WAVE=1.
if [ "${CLAUDE_SKIP_MAIN_SYNC_BEFORE_WAVE:-0}" != "1" ] && [ -f "$ROOT/scripts/sync-main-before-wave.sh" ]; then
  if ! bash "$ROOT/scripts/sync-main-before-wave.sh" --apply --quiet; then
    echo "ERROR: canonical main sync failed before next-wave; run: bash scripts/sync-main-before-wave.sh --apply" >&2
    exit 3
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



# Clean local task branches/worktrees that are patch-equivalent to main but were
# left behind after squash merges or obsolete worktree churn. This is stricter
# than closed-task cleanup: live registry statuses, dirty worktrees and branches
# with any unique patch are skipped.
if [ "${CLAUDE_DISABLE_ZOMBIE_WORKTREE_CLEANUP:-0}" != "1" ] && [ -f "$ROOT/scripts/cleanup-zombie-task-worktrees.sh" ]; then
  if ! bash "$ROOT/scripts/cleanup-zombie-task-worktrees.sh" --apply --quiet; then
    echo "WARN: zombie task worktree cleanup incomplete; run: bash scripts/cleanup-zombie-task-worktrees.sh --apply --verbose" >&2
  fi
fi

# Safe remote branch housekeeping for already-merged PRs. This only deletes
# same-repo remote task branches when GitHub reports the PR as MERGED and the
# remote branch SHA still equals that PR head SHA. Open, moved, forked, or
# ambiguous branches are left untouched. Missing gh/auth is a quiet no-op.
# Disable with CLAUDE_CLEAN_MERGED_PR_BRANCHES=0 or
# CLAUDE_DISABLE_REMOTE_BRANCH_CLEANUP=1.
if [ "${CLAUDE_CLEAN_MERGED_PR_BRANCHES:-1}" != "0" ] && [ "${CLAUDE_DISABLE_REMOTE_BRANCH_CLEANUP:-0}" != "1" ] && [ "${CLAUDE_DISABLE_REMOTE_PR_BRANCH_CLEANUP:-0}" != "1" ] && [ -f "$ROOT/scripts/cleanup-merged-pr-branches.sh" ]; then
  if ! bash "$ROOT/scripts/cleanup-merged-pr-branches.sh" --apply --quiet; then
    echo "WARN: merged PR remote branch cleanup incomplete; run: bash scripts/cleanup-merged-pr-branches.sh --apply --verbose" >&2
  fi
fi

python3 -B -S "$ROOT/.claude/bin/next_wave.py" "$@"
