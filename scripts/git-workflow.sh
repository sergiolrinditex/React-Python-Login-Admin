#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKFLOW="$(python3 "$ROOT_DIR/.claude/bin/stack_profile.py" --root "$ROOT_DIR" --get git_workflow --default push-to-main)"
WORKFLOW="${WORKFLOW//[^A-Za-z0-9_-]/}"
case "$WORKFLOW" in
  direct-main|direct-main-push|push-main)
    WORKFLOW="push-to-main"
    ;;
esac
PLUGIN="$ROOT_DIR/.claude/git-workflows/${WORKFLOW}.sh"
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

# Transport-only Git workflow. The closer must create the atomic slice commit
# before invoking this script. This script never stashes or pops. In production
# DAG mode Claude hooks can write late trace files after the closer's commit;
# amend only those known trace files, then refuse every other dirty path so
# product changes cannot be hidden behind push/PR automation.
amend_late_trace_files() {
  local late_paths=()
  for path in     orchestrator-state/tasks/ledger.jsonl     orchestrator-state/tasks/bash-ledger.jsonl     orchestrator-state/tasks/runtime-state.json
  do
    if ! git diff --quiet -- "$path" 2>/dev/null || ! git diff --cached --quiet -- "$path" 2>/dev/null; then
      late_paths+=("$path")
    fi
  done

  if [ "${#late_paths[@]}" -eq 0 ]; then
    return 0
  fi

  git add -- "${late_paths[@]}"
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
