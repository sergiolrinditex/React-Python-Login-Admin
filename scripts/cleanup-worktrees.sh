#!/usr/bin/env bash
set -euo pipefail

# Safely remove per-slice git worktrees after a closer has committed and run
# the configured Git workflow. Dry-run by default. The script is worktree-aware:
# when invoked from inside the task worktree, it first resolves and cd's to the
# canonical root so the task worktree itself can be removed safely.

APPLY=0
TASK_ID=""
VERBOSE=0

usage() {
  cat <<'USAGE'
Usage: scripts/cleanup-worktrees.sh [--apply] [--task TASK_ID] [--verbose]

Default is dry-run. A worktree is a candidate when its path or branch name
contains TASK_ID. Without --task, candidates are paths/branches that look like
per-slice worktrees (contain Pxx-Sxx-Txxx or dev/ or feature/). Dirty worktrees
are reported and skipped.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --task)
      TASK_ID="${2:-}"
      if [ -z "$TASK_ID" ]; then
        echo "ERROR: --task requires a TASK_ID" >&2
        exit 2
      fi
      shift 2
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "cleanup-worktrees: git_repository=no matched=0 would_remove=0 removed=0 skipped=0 mode=$([ "$APPLY" -eq 1 ] && echo apply || echo dry-run) task=${TASK_ID:-all}"
  exit 0
fi

ORIGINAL_ROOT="$(git rev-parse --show-toplevel)"
resolve_canonical_root() {
  local common_dir
  common_dir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
  if [ -n "$common_dir" ] && [ "$(basename "$common_dir")" = ".git" ] && [ -d "$(dirname "$common_dir")" ]; then
    (cd "$(dirname "$common_dir")" && pwd -P)
  else
    printf '%s\n' "$ORIGINAL_ROOT"
  fi
}
ROOT="$(resolve_canonical_root)"
ROOT_REAL="$(cd "$ROOT" && pwd -P)"
cd "$ROOT_REAL"

MATCHED=0
WOULD_REMOVE=0
REMOVED=0
SKIPPED=0
BRANCHES_DELETED=0
BRANCHES_SKIPPED=0

records="$(git worktree list --porcelain)"
current_path=""
current_branch=""

branch_short_name() {
  local branch="$1"
  case "$branch" in
    refs/heads/*) printf '%s\n' "${branch#refs/heads/}" ;;
    *) printf '%s\n' "$branch" ;;
  esac
}

maybe_delete_local_branch() {
  local wt_branch="$1"
  local short
  short="$(branch_short_name "$wt_branch")"
  case "$short" in
    ""|main|master|HEAD|detached) return 0 ;;
  esac
  if ! git show-ref --verify --quiet "refs/heads/$short"; then
    return 0
  fi

  local develop="${GIT_FLOW_DEVELOP:-develop}"
  local main="${GIT_FLOW_MAIN:-main}"
  local safe_to_delete=0
  # After pr-flow GitHub usually squash-merges the PR and deletes the remote
  # branch. A squash merge means the feature tip is not an ancestor of main,
  # so merge-base alone would keep stale local feature/Pxx-Sxx-Txxx branches
  # forever. When cleanup is scoped to a TASK_ID and the branch belongs to that
  # TASK_ID, the closer already proved integration before calling this script;
  # deleting the local task branch is safe.
  if [ -n "$TASK_ID" ]; then
    case "$short" in
      *"$TASK_ID"*) safe_to_delete=1 ;;
    esac
  fi
  if [ "$safe_to_delete" -ne 1 ] && git merge-base --is-ancestor "$short" HEAD >/dev/null 2>&1; then
    safe_to_delete=1
  elif [ "$safe_to_delete" -ne 1 ] && git show-ref --verify --quiet "refs/heads/$develop" && git merge-base --is-ancestor "$short" "$develop" >/dev/null 2>&1; then
    safe_to_delete=1
  elif [ "$safe_to_delete" -ne 1 ] && git show-ref --verify --quiet "refs/heads/$main" && git merge-base --is-ancestor "$short" "$main" >/dev/null 2>&1; then
    safe_to_delete=1
  fi

  if [ "$safe_to_delete" -eq 1 ]; then
    if git branch -d "$short" >/dev/null 2>&1 || git branch -D "$short" >/dev/null 2>&1; then
      BRANCHES_DELETED=$((BRANCHES_DELETED + 1))
      echo "deleted local branch: $short"
    else
      BRANCHES_SKIPPED=$((BRANCHES_SKIPPED + 1))
      echo "skip branch delete: $short"
    fi
  else
    BRANCHES_SKIPPED=$((BRANCHES_SKIPPED + 1))
    [ "$VERBOSE" -eq 1 ] && echo "skip branch delete not merged: $short"
  fi
}

process_record() {
  local wt_path="$1"
  local wt_branch="$2"
  [ -n "$wt_path" ] || return 0

  local wt_real
  wt_real="$(cd "$wt_path" 2>/dev/null && pwd -P || printf '%s' "$wt_path")"

  # Never touch the canonical root or main/master checkouts.
  if [ "$wt_real" = "$ROOT_REAL" ]; then
    [ "$VERBOSE" -eq 1 ] && echo "skip canonical root: $wt_path"
    return 0
  fi
  case "$wt_branch" in
    refs/heads/main|refs/heads/master|main|master)
      [ "$VERBOSE" -eq 1 ] && echo "skip main/master: $wt_path ($wt_branch)"
      return 0
      ;;
  esac

  local haystack="$wt_path $wt_branch"
  local candidate=0
  if [ -n "$TASK_ID" ]; then
    case "$haystack" in
      *"$TASK_ID"*) candidate=1 ;;
    esac
  else
    if printf '%s\n' "$haystack" | grep -Eq 'P[0-9]+-S[0-9]+-T[0-9]+|dev/|feature/'; then
      candidate=1
    fi
  fi

  if [ "$candidate" -ne 1 ]; then
    [ "$VERBOSE" -eq 1 ] && echo "skip non-candidate: $wt_path ($wt_branch)"
    return 0
  fi

  MATCHED=$((MATCHED + 1))

  if [ ! -d "$wt_path" ]; then
    SKIPPED=$((SKIPPED + 1))
    echo "skip missing path: $wt_path"
    return 0
  fi

  local status
  status="$(git -C "$wt_path" status --porcelain 2>/dev/null || true)"
  if [ -n "$status" ]; then
    SKIPPED=$((SKIPPED + 1))
    echo "skip dirty: $wt_path ($wt_branch)"
    return 0
  fi

  if [ "$APPLY" -eq 1 ]; then
    if git worktree remove "$wt_path" 2>/dev/null; then
      REMOVED=$((REMOVED + 1))
      echo "removed: $wt_path ($wt_branch)"
    else
      git worktree remove --force "$wt_path" 2>/dev/null || true
      if [ -d "$wt_path" ]; then
        rm -rf "$wt_path"
      fi
      REMOVED=$((REMOVED + 1))
      echo "removed (forced after git refused, untracked cruft only): $wt_path ($wt_branch)"
    fi
    maybe_delete_local_branch "$wt_branch"
  else
    WOULD_REMOVE=$((WOULD_REMOVE + 1))
    echo "would remove: $wt_path ($wt_branch)"
  fi
}

while IFS= read -r line; do
  if [ -z "$line" ]; then
    process_record "$current_path" "$current_branch"
    current_path=""
    current_branch=""
    continue
  fi
  case "$line" in
    worktree\ *) current_path="${line#worktree }" ;;
    branch\ *) current_branch="${line#branch }" ;;
  esac
done <<EOF2
$records
EOF2
process_record "$current_path" "$current_branch"

git worktree prune

CONTAINER="${CLAUDE_TASK_WORKTREES_DIR:-$(dirname "$ROOT_REAL")/$(basename "$ROOT_REAL")-worktrees}"
if [ "$APPLY" -eq 1 ] && [ -d "$CONTAINER" ] && [ -z "$(ls -A "$CONTAINER" 2>/dev/null)" ]; then
  rmdir "$CONTAINER" 2>/dev/null && echo "removed empty container: $CONTAINER" || true
fi

echo "cleanup-worktrees: matched=$MATCHED would_remove=$WOULD_REMOVE removed=$REMOVED skipped=$SKIPPED branches_deleted=$BRANCHES_DELETED branches_skipped=$BRANCHES_SKIPPED mode=$([ "$APPLY" -eq 1 ] && echo apply || echo dry-run) task=${TASK_ID:-all}"

if [ "$APPLY" -eq 1 ] && [ -n "$TASK_ID" ] && [ "$SKIPPED" -gt 0 ]; then
  echo "cleanup-worktrees: incomplete task cleanup; dirty/missing candidate(s) were skipped" >&2
  exit 3
fi
