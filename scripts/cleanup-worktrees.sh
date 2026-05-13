#!/usr/bin/env bash
set -euo pipefail

# Safely remove per-slice git worktrees after the closer has committed and
# pushed to main. Dry-run by default. Never touches main/current worktree and
# never removes dirty worktrees.

APPLY=0
TASK_ID=""
VERBOSE=0

usage() {
  cat <<'USAGE'
Usage: scripts/cleanup-worktrees.sh [--apply] [--task TASK_ID] [--verbose]

Default is dry-run. A worktree is a candidate when its path or branch name
contains TASK_ID. Without --task, candidates are paths/branches that look like
per-slice worktrees (contain Pxx-Sxx-Txxx or dev/...). Dirty worktrees are
reported and skipped.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      # Default mode anyway, but accept it as explicit flag so users who
      # type "--dry-run" don't get an error.
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

ROOT="$(git rev-parse --show-toplevel)"
CURRENT="$(cd "$ROOT" && pwd -P)"

MATCHED=0
WOULD_REMOVE=0
REMOVED=0
SKIPPED=0

records="$(git worktree list --porcelain)"
current_path=""
current_branch=""

process_record() {
  local wt_path="$1"
  local wt_branch="$2"
  [ -n "$wt_path" ] || return 0

  local wt_real
  wt_real="$(cd "$wt_path" 2>/dev/null && pwd -P || printf '%s' "$wt_path")"

  # Never touch the primary/current worktree.
  if [ "$wt_real" = "$CURRENT" ]; then
    [ "$VERBOSE" -eq 1 ] && echo "skip current: $wt_path"
    return 0
  fi

  # Never touch a worktree checked out on main/master.
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
    if printf '%s\n' "$haystack" | grep -Eq 'P[0-9]+-S[0-9]+-T[0-9]+|dev/'; then
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
    # Try git's clean remove first. It refuses if the worktree has
    # untracked files (caches, .ruff_cache, __pycache__, .DS_Store, dev logs).
    # The status check above already confirmed there are no MODIFIED tracked
    # files. So if git rejects with "Directory not empty", the remaining
    # content is only untracked cruft — safe to rm -rf the dir directly.
    if git worktree remove "$wt_path" 2>/dev/null; then
      REMOVED=$((REMOVED + 1))
      echo "removed: $wt_path ($wt_branch)"
    else
      # Fallback: forced removal (registers the worktree as gone in git)
      # plus filesystem rm of the physical directory. Safe because:
      #   * we already skipped current/main/master worktrees above
      #   * we already skipped dirty worktrees above (tracked changes)
      git worktree remove --force "$wt_path" 2>/dev/null || true
      if [ -d "$wt_path" ]; then
        rm -rf "$wt_path"
      fi
      REMOVED=$((REMOVED + 1))
      echo "removed (forced after git refused, untracked cruft only): $wt_path ($wt_branch)"
    fi
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

# Remove the empty <repo>-worktrees/ container directory when no
# slice worktrees remain inside it. This keeps the parent tidy after
# all slices in a wave have closed. Only removes if completely empty
# and only with --apply. ensure-task-worktree.sh re-creates it for
# the next TASK_ID, so no behaviour change for active slices.
CONTAINER="$(dirname "$ROOT")/$(basename "$ROOT")-worktrees"
if [ "$APPLY" -eq 1 ] && [ -d "$CONTAINER" ] && [ -z "$(ls -A "$CONTAINER" 2>/dev/null)" ]; then
  rmdir "$CONTAINER" 2>/dev/null && echo "removed empty container: $CONTAINER" || true
fi

echo "cleanup-worktrees: matched=$MATCHED would_remove=$WOULD_REMOVE removed=$REMOVED skipped=$SKIPPED mode=$([ "$APPLY" -eq 1 ] && echo apply || echo dry-run) task=${TASK_ID:-all}"
