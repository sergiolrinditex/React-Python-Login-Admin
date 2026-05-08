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
exec "$PLUGIN" "$@"
