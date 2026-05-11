#!/usr/bin/env bash
set -euo pipefail
BRANCH="$(git branch --show-current)"
if [ "$BRANCH" != "main" ]; then
  echo "GIT_WORKFLOW_READY: no"
  echo "Reason: push-to-main/direct-main requires branch main, current=$BRANCH"
  exit 2
fi
git push origin main
echo "GIT_WORKFLOW_READY: yes"
echo "PUSH_READY: yes"
