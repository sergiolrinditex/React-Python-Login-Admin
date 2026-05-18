#!/usr/bin/env bash
set -euo pipefail
SCRIPT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || printf '%s\n' "$SCRIPT_ROOT")"
CONFIG_ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-}"
if [ -z "$CONFIG_ROOT" ] && [ -x "$SCRIPT_ROOT/scripts/ensure-task-worktree.sh" ]; then
  CONFIG_ROOT="$(bash "$SCRIPT_ROOT/scripts/ensure-task-worktree.sh" --print-root 2>/dev/null || printf '%s\n' "$SCRIPT_ROOT")"
fi
CONFIG_ROOT="${CONFIG_ROOT:-$SCRIPT_ROOT}"
cd "$WORKSPACE_ROOT"
WORKFLOW="$(python3 -B -S "$CONFIG_ROOT/.claude/bin/stack_profile.py" --root "$CONFIG_ROOT" --get git_workflow --default push-to-main)"
WORKFLOW="$(printf '%s' "$WORKFLOW" | tr -cd 'A-Za-z0-9_-')"
case "$WORKFLOW" in
  direct-main|direct-main-push|push-main)
    WORKFLOW="push-to-main"
    ;;
  gitflow)
    WORKFLOW="git-flow"
    ;;
esac
PLUGIN="$CONFIG_ROOT/.claude/git-workflows/${WORKFLOW}.sh"
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "GIT_WORKFLOW_READY: no"
  echo "Reason: not inside a git repository"
  exit 2
fi

if [ ! -x "$PLUGIN" ]; then
  echo "❌ Git workflow plugin not found/executable: .claude/git-workflows/${WORKFLOW}.sh" >&2
  exit 2
fi

if grep -Ev '^[[:space:]]*#' "$PLUGIN" | grep -Eq '(^|[;&|[:space:]])git[[:space:]]+stash([[:space:]]|$)'; then
  echo "GIT_WORKFLOW_READY: no"
  echo "Reason: git workflow plugin uses git stash, which is unsafe in production DAG mode. Stage/commit before this script instead."
  exit 2
fi

if [ -x "$CONFIG_ROOT/scripts/check-git-identity.sh" ]; then
  if ! bash "$CONFIG_ROOT/scripts/check-git-identity.sh" --strict; then
    echo "GIT_WORKFLOW_READY: no"
    echo "Reason: Git identity guard failed before transport; fix user.name/user.email and amend/reset-author before pushing."
    exit 3
  fi
fi

# Transport-only Git workflow. The closer must create the atomic slice commit
# before invoking this script. This script never stashes or pops. In production
# DAG mode Claude hooks can write late trace files after the closer's commit;
# amend only those known trace files, then refuse every other dirty path so
# product changes cannot be hidden behind push/PR automation.
amend_late_trace_files() {
  local found=0
  local path
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    if ! git diff --quiet -- "$path" 2>/dev/null || ! git diff --cached --quiet -- "$path" 2>/dev/null; then
      git add -- "$path" 2>/dev/null || true
      found=1
    fi
  done <<'EOF_LATE_TRACE_PATHS'
orchestrator-state/tasks/ledger.jsonl
orchestrator-state/tasks/bash-ledger.jsonl
orchestrator-state/tasks/runtime-state.json
EOF_LATE_TRACE_PATHS

  if [ "$found" -eq 0 ]; then
    return 0
  fi

  if git diff --cached --quiet; then
    return 0
  fi

  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    git commit --amend --no-edit --no-verify >/dev/null
    echo "GIT_WORKFLOW_TRACE_AMENDED: yes"
  else
    git commit --allow-empty -m "chore(orchestrator): sync late trace files" --no-verify >/dev/null
    echo "GIT_WORKFLOW_TRACE_COMMITTED: yes"
  fi
}

if [ "${GIT_WORKFLOW_ALLOW_DIRTY:-0}" != "1" ]; then
  amend_late_trace_files
  dirty="$(git status --porcelain=v1 --untracked-files=all)"
  if [ -n "$dirty" ]; then
    echo "GIT_WORKFLOW_READY: no"
    echo "Reason: working tree is dirty outside allowed late trace files; closer must stage and commit intended changes before git workflow. Do not use stash/pop here."
    echo "$dirty" | sed 's/^/DIRTY: /'
    exit 2
  fi
fi

exec "$PLUGIN" "$@"
