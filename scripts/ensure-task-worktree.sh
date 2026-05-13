#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/ensure-task-worktree.sh <TASK_ID>
  scripts/ensure-task-worktree.sh --check-current <TASK_ID>
  scripts/ensure-task-worktree.sh --print-root

Creates or locates the per-TASK_ID git worktree for pr-flow projects and prints
its path. For push-to-main/direct-main projects it prints the canonical/main repo
path because that workflow intentionally does not use feature branches.

--print-root prints the canonical/main worktree root. This is intentionally
separate from `git rev-parse --show-toplevel`, which returns the current task
worktree when invoked from a worker terminal.

The script is safe in non-git checkouts: it prints the current directory.
EOF
}

MODE="ensure"
if [ "${1:-}" = "--print-root" ]; then
  MODE="print-root"
  shift
elif [ "${1:-}" = "--check-current" ]; then
  MODE="check"
  shift
fi
TASK_ID="${1:-}"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  pwd -P
  exit 0
fi

CURRENT_ROOT="$(git rev-parse --show-toplevel)"
CANONICAL_ROOT="$(git worktree list --porcelain 2>/dev/null | awk '
  BEGIN { first=""; main="" }
  /^worktree / { wt=substr($0, 10); if (first=="") first=wt }
  /^branch refs\/heads\/main$/ { main=wt }
  END { if (main!="") print main; else print first }
')"
ROOT="${CANONICAL_ROOT:-$CURRENT_ROOT}"

if [ "$MODE" = "print-root" ]; then
  printf '%s\n' "$ROOT"
  exit 0
fi

if [ -z "$TASK_ID" ] || [ "$TASK_ID" = "-h" ] || [ "$TASK_ID" = "--help" ]; then
  usage >&2
  [ -n "$TASK_ID" ] && [ "$TASK_ID" != "-h" ] && [ "$TASK_ID" != "--help" ] && exit 2 || exit 0
fi
if ! printf '%s' "$TASK_ID" | grep -Eq '^P[0-9]+-S[0-9]+-T[0-9]+$'; then
  echo "ERROR: invalid TASK_ID: $TASK_ID" >&2
  exit 2
fi

WORKFLOW="$(python3 "$ROOT/.claude/bin/stack_profile.py" --root "$ROOT" --get git_workflow --default push-to-main 2>/dev/null || echo push-to-main)"
WORKFLOW="${WORKFLOW//[^A-Za-z0-9_-]/}"
case "$WORKFLOW" in
  direct-main|direct-main-push|push-main) WORKFLOW="push-to-main" ;;
esac

BRANCH="dev/$TASK_ID"
CURRENT_BRANCH="$(git -C "$CURRENT_ROOT" branch --show-current 2>/dev/null || true)"

if [ "$WORKFLOW" = "push-to-main" ]; then
  if [ "$MODE" = "check" ]; then
    if [ "$CURRENT_BRANCH" != "main" ]; then
      echo "TASK_WORKTREE_READY: no"
      echo "Reason: git_workflow=$WORKFLOW requires branch main, current=${CURRENT_BRANCH:-detached}"
      exit 2
    fi
    echo "TASK_WORKTREE_READY: yes"
  else
    printf '%s\n' "$ROOT"
  fi
  exit 0
fi

if [ "$MODE" = "check" ]; then
  if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ] || [ -z "$CURRENT_BRANCH" ]; then
    echo "TASK_WORKTREE_READY: no"
    echo "Reason: git_workflow=$WORKFLOW requires a task branch/worktree, current=${CURRENT_BRANCH:-detached}"
    exit 2
  fi
  case "$CURRENT_BRANCH" in
    *"$TASK_ID"*)
      echo "TASK_WORKTREE_READY: yes"
      echo "Branch: $CURRENT_BRANCH"
      echo "Worktree: $CURRENT_ROOT"
      exit 0
      ;;
    *)
      echo "TASK_WORKTREE_READY: no"
      echo "Reason: current branch $CURRENT_BRANCH does not contain TASK_ID $TASK_ID"
      exit 2
      ;;
  esac
fi

# If this branch is already checked out in a worktree, reuse that path.
existing="$(git -C "$ROOT" worktree list --porcelain | awk -v branch="refs/heads/$BRANCH" '
  /^worktree / {wt=$0; sub(/^worktree /,"",wt)}
  /^branch / {br=$0; sub(/^branch /,"",br); if (br==branch) print wt}
' | head -1)"
if [ -n "$existing" ] && [ -d "$existing" ]; then
  printf '%s\n' "$existing"
  exit 0
fi

if ! git -C "$ROOT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git -C "$ROOT" branch "$BRANCH"
fi

WT_PARENT="${CLAUDE_TASK_WORKTREES_DIR:-$(dirname "$ROOT")/$(basename "$ROOT")-worktrees}"
WT="$WT_PARENT/$TASK_ID"
mkdir -p "$WT_PARENT"
if [ -d "$WT/.git" ] || [ -f "$WT/.git" ]; then
  printf '%s\n' "$WT"
  exit 0
fi

git -C "$ROOT" worktree add "$WT" "$BRANCH" >/dev/null
printf '%s\n' "$WT"
