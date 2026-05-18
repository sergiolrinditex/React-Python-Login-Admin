#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage:
  scripts/ensure-task-worktree.sh <TASK_ID>
  scripts/ensure-task-worktree.sh --check-current <TASK_ID>
  scripts/ensure-task-worktree.sh --print-root

Creates or locates the per-TASK_ID git worktree for branch-based workflows and
prints its path. For push-to-main/direct-main projects it prints the canonical
root because that workflow intentionally does not use feature branches.

Branch conventions:
  pr-flow   -> dev/<TASK_ID>, based on the default branch
  git-flow  -> feature/<TASK_ID>, based on develop

--print-root prints the canonical/main repository root, not the current linked
worktree. The script is safe in non-git checkouts: it prints the current dir.
EOF_USAGE
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

resolve_canonical_root() {
  local common_dir
  common_dir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
  if [ -n "$common_dir" ] && [ "$(basename "$common_dir")" = ".git" ] && [ -d "$(dirname "$common_dir")" ]; then
    (cd "$(dirname "$common_dir")" && pwd -P)
  else
    printf '%s\n' "$CURRENT_ROOT"
  fi
}
CANONICAL_ROOT="$(resolve_canonical_root)"
ROOT="$CANONICAL_ROOT"
# Drop stale metadata from previously removed Claude task worktrees before reuse,
# and flush any hook-safe deferred cleanup requests from older closed slices.
git -C "$ROOT" worktree prune >/dev/null 2>&1 || true
if [ -x "$ROOT/scripts/cleanup-deferred-worktrees.sh" ] && [ "${CLAUDE_SKIP_DEFERRED_CLEANUP:-0}" != "1" ]; then
  bash "$ROOT/scripts/cleanup-deferred-worktrees.sh" --apply --quiet >/dev/null 2>&1 || true
fi
if [ -x "$ROOT/scripts/sync-lifecycle-events.sh" ]; then
  bash "$ROOT/scripts/sync-lifecycle-events.sh" --apply >/dev/null 2>&1 || true
fi
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

WORKFLOW="$(python3 -S "$ROOT/.claude/bin/stack_profile.py" --root "$ROOT" --get git_workflow --default push-to-main 2>/dev/null || echo push-to-main)"
WORKFLOW="$(printf '%s' "$WORKFLOW" | tr -cd 'A-Za-z0-9_-')"
case "$WORKFLOW" in
  direct-main|direct-main-push|push-main) WORKFLOW="push-to-main" ;;
  gitflow) WORKFLOW="git-flow" ;;
esac

DEFAULT_BRANCH="${GIT_DEFAULT_BRANCH:-main}"
DEVELOP_BRANCH="${GIT_FLOW_DEVELOP:-develop}"
MAIN_REMOTE="$(git -C "$ROOT" config "branch.${DEFAULT_BRANCH}.remote" 2>/dev/null || echo origin)"
if ! git -C "$ROOT" remote get-url "$MAIN_REMOTE" >/dev/null 2>&1; then
  MAIN_REMOTE="origin"
fi
DEVELOP_REMOTE="$(git -C "$ROOT" config "branch.${DEVELOP_BRANCH}.remote" 2>/dev/null || echo "$MAIN_REMOTE")"
if ! git -C "$ROOT" remote get-url "$DEVELOP_REMOTE" >/dev/null 2>&1; then
  DEVELOP_REMOTE="$MAIN_REMOTE"
fi

if [ "$WORKFLOW" = "git-flow" ]; then
  BRANCH="feature/$TASK_ID"
else
  BRANCH="dev/$TASK_ID"
fi
CURRENT_BRANCH="$(git -C "$CURRENT_ROOT" branch --show-current 2>/dev/null || true)"

# Before creating/reusing a task worktree for branch-based PR flow, make sure
# the canonical main checkout is fast-forwarded to origin/main. This closes the
# class of drift where /next-slice is launched directly (without a prior
# /next-wave) and the new dev/<TASK_ID> branch is cut from stale local main.
# --check-current and --print-root remain read-only.
if [ "$MODE" = "ensure" ] && [ "$WORKFLOW" = "pr-flow" ] && [ "${CLAUDE_SKIP_MAIN_SYNC_BEFORE_WAVE:-0}" != "1" ] && [ "${CLAUDE_SKIP_MAIN_SYNC_BEFORE_WORKTREE:-0}" != "1" ] && [ -f "$ROOT/scripts/sync-main-before-wave.sh" ]; then
  if ! bash "$ROOT/scripts/sync-main-before-wave.sh" --apply --quiet --remote "$MAIN_REMOTE" --main "$DEFAULT_BRANCH"; then
    echo "TASK_WORKTREE_READY: no" >&2
    echo "Reason: canonical $DEFAULT_BRANCH could not fast-forward to $MAIN_REMOTE/$DEFAULT_BRANCH before creating task worktree." >&2
    echo "Run: cd '$ROOT' && bash scripts/sync-main-before-wave.sh --apply --remote '$MAIN_REMOTE' --main '$DEFAULT_BRANCH'" >&2
    exit 3
  fi
fi

if [ "$WORKFLOW" = "push-to-main" ]; then
  if [ "$MODE" = "check" ]; then
    if [ "$CURRENT_BRANCH" != "$DEFAULT_BRANCH" ]; then
      echo "TASK_WORKTREE_READY: no"
      echo "Reason: git_workflow=$WORKFLOW requires branch $DEFAULT_BRANCH, current=${CURRENT_BRANCH:-detached}"
      exit 2
    fi
    echo "TASK_WORKTREE_READY: yes"
  else
    printf '%s\n' "$ROOT"
  fi
  exit 0
fi

if [ "$MODE" = "check" ]; then
  if [ "$CURRENT_BRANCH" = "$DEFAULT_BRANCH" ] || [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ] || [ -z "$CURRENT_BRANCH" ]; then
    echo "TASK_WORKTREE_READY: no"
    echo "Reason: git_workflow=$WORKFLOW requires a task branch/worktree, current=${CURRENT_BRANCH:-detached}"
    exit 2
  fi
  if [ "$WORKFLOW" = "git-flow" ]; then
    case "$CURRENT_BRANCH" in
      "feature/$TASK_ID"|"feature/$TASK_ID"-*)
        echo "TASK_WORKTREE_READY: yes"
        echo "Branch: $CURRENT_BRANCH"
        echo "Worktree: $CURRENT_ROOT"
        exit 0
        ;;
      *)
        echo "TASK_WORKTREE_READY: no"
        echo "Reason: git_workflow=git-flow requires branch feature/$TASK_ID (or feature/$TASK_ID-*), current=$CURRENT_BRANCH"
        exit 2
        ;;
    esac
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

existing="$(git -C "$ROOT" worktree list --porcelain | awk -v branch="refs/heads/$BRANCH" '
  /^worktree / {wt=$0; sub(/^worktree /,"",wt)}
  /^branch / {br=$0; sub(/^branch /,"",br); if (br==branch) print wt}
' | head -1)"
if [ -n "$existing" ] && [ -d "$existing" ]; then
  printf '%s\n' "$existing"
  exit 0
fi

# Before cutting a NEW PR-flow task branch, bring the canonical main checkout up
# to origin/main when that is safe. This keeps terminal N+1 from starting on an
# old main after terminal N has merged. Existing/in-flight task branches are not
# rebased here.
if [ "$WORKFLOW" != "git-flow" ] && [ "${CLAUDE_SKIP_MAIN_SYNC_BEFORE_SLICE:-0}" != "1" ] && [ -x "$ROOT/scripts/sync-main-before-wave.sh" ]; then
  if ! bash "$ROOT/scripts/sync-main-before-wave.sh" --apply --quiet; then
    echo "TASK_WORKTREE_READY: no" >&2
    echo "Reason: canonical main could not sync with remote before creating $BRANCH. Run: bash scripts/sync-main-before-wave.sh --apply" >&2
    exit 3
  fi
fi

base_ref_for_workflow() {
  if [ "$WORKFLOW" = "git-flow" ]; then
    if git -C "$ROOT" show-ref --verify --quiet "refs/heads/$DEVELOP_BRANCH"; then
      printf '%s\n' "$DEVELOP_BRANCH"
      return 0
    fi
    if git -C "$ROOT" remote get-url "$DEVELOP_REMOTE" >/dev/null 2>&1; then
      git -C "$ROOT" fetch "$DEVELOP_REMOTE" "$DEVELOP_BRANCH" >/dev/null 2>&1 || true
    fi
    if git -C "$ROOT" show-ref --verify --quiet "refs/remotes/$DEVELOP_REMOTE/$DEVELOP_BRANCH"; then
      printf '%s\n' "$DEVELOP_REMOTE/$DEVELOP_BRANCH"
      return 0
    fi
    echo "TASK_WORKTREE_READY: no" >&2
    echo "Reason: git_workflow=git-flow requires branch '$DEVELOP_BRANCH' locally or on '$DEVELOP_REMOTE' before creating feature worktrees." >&2
    echo "Create it with: git checkout -b $DEVELOP_BRANCH ${GIT_FLOW_MAIN:-main} && git push -u $DEVELOP_REMOTE $DEVELOP_BRANCH" >&2
    return 2
  fi

  # PR-flow worktrees must start from the newest remote default branch, not
  # from a potentially stale local main. This is intentionally a fetch + branch
  # from origin/main instead of a planner-side rebase: new slices start fresh;
  # existing/in-flight task branches are never mutated here.
  if git -C "$ROOT" remote get-url "$MAIN_REMOTE" >/dev/null 2>&1; then
    git -C "$ROOT" fetch "$MAIN_REMOTE" --prune "+refs/heads/$DEFAULT_BRANCH:refs/remotes/$MAIN_REMOTE/$DEFAULT_BRANCH" >/dev/null 2>&1 || true
  fi
  if git -C "$ROOT" show-ref --verify --quiet "refs/remotes/$MAIN_REMOTE/$DEFAULT_BRANCH"; then
    printf '%s\n' "$MAIN_REMOTE/$DEFAULT_BRANCH"
  elif git -C "$ROOT" show-ref --verify --quiet "refs/heads/$DEFAULT_BRANCH"; then
    printf '%s\n' "$DEFAULT_BRANCH"
  else
    printf '%s\n' "HEAD"
  fi
}

BASE_REF="$(base_ref_for_workflow)"
if ! git -C "$ROOT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git -C "$ROOT" branch "$BRANCH" "$BASE_REF" >/dev/null 2>&1
fi

WT_PARENT="${CLAUDE_TASK_WORKTREES_DIR:-$(dirname "$ROOT")/$(basename "$ROOT")-worktrees}"
WT="$WT_PARENT/$TASK_ID"
mkdir -p "$WT_PARENT"
if [ -d "$WT/.git" ] || [ -f "$WT/.git" ]; then
  printf '%s\n' "$WT"
  exit 0
fi
if [ -e "$WT" ] && [ -n "$(ls -A "$WT" 2>/dev/null || true)" ]; then
  echo "TASK_WORKTREE_READY: no" >&2
  echo "Reason: target worktree path exists but is not an empty git worktree: $WT" >&2
  exit 3
fi

git -C "$ROOT" worktree add "$WT" "$BRANCH" >/dev/null 2>&1
printf '%s\n' "$WT"
