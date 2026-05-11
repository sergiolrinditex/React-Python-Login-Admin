#!/usr/bin/env bash
set -euo pipefail
BRANCH="$(git branch --show-current)"
if [ "$BRANCH" = "main" ]; then
  echo "GIT_WORKFLOW_READY: no"
  echo "Reason: pr-flow requires a feature branch, not main. Use git_workflow: push-to-main/direct-main for intentional direct pushes to main."
  exit 2
fi
git push -u origin "$BRANCH"
if command -v gh >/dev/null 2>&1; then
  gh pr create --fill
  echo "GIT_WORKFLOW_READY: yes"
  echo "PUSH_READY: yes"
  echo "PR_READY: yes"
else
  echo "GIT_WORKFLOW_READY: blocked"
  echo "PUSH_READY: yes"
  echo "PR_READY: no"
  echo "Reason: branch pushed but gh CLI is not installed; open PR manually."
  exit 3
fi
