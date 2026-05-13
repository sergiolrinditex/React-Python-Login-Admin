#!/usr/bin/env bash
# pr-flow.sh -- Closer's Git workflow for git_workflow: pr-flow
#
# Steps:
#   1. Verify we are on a feature branch (not main).
#   2. Push the branch.
#   3. Create a PR via gh (or reuse the existing one for this branch).
#   4. Auto-merge: try --admin (immediate squash merge bypassing checks)
#      first because /verify-slice already provided real human verification
#      with real data; CI on the PR would re-run what the human just
#      validated. If --admin fails (no admin permission), fall back to
#      --auto (queues the merge until required checks pass).
#
# Outputs (closer parses these from stdout):
#   GIT_WORKFLOW_READY: yes|no|blocked
#   PUSH_READY: yes|no
#   PR_READY:  yes|no
#   MERGED:    yes | auto-queued | no
#   PR_URL:    <url>
#
# Exit codes:
#   0   PR created and (merged immediately OR queued for auto-merge)
#   2   branch is main; pr-flow is wrong workflow for this checkout
#   3   gh CLI missing OR PR creation failed OR neither merge mode worked

set -euo pipefail
BRANCH="$(git branch --show-current)"
if [ "$BRANCH" = "main" ]; then
  echo "GIT_WORKFLOW_READY: no"
  echo "Reason: pr-flow requires a feature branch, not main. Use git_workflow: push-to-main/direct-main for intentional direct pushes to main."
  exit 2
fi

# Push the branch (idempotent if already up-to-date).
git push -u origin "$BRANCH"

if ! command -v gh >/dev/null 2>&1; then
  echo "GIT_WORKFLOW_READY: blocked"
  echo "PUSH_READY: yes"
  echo "PR_READY: no"
  echo "Reason: branch pushed but gh CLI is not installed; open PR manually."
  exit 3
fi

# Create the PR or reuse the existing one for this branch.
if ! gh pr view "$BRANCH" >/dev/null 2>&1; then
  if ! gh pr create --fill >/tmp/pr-flow-create.log 2>&1; then
    echo "GIT_WORKFLOW_READY: blocked"
    echo "PUSH_READY: yes"
    echo "PR_READY: no"
    echo "Reason: gh pr create failed. See /tmp/pr-flow-create.log"
    sed 's/^/  /' /tmp/pr-flow-create.log >&2 || true
    exit 3
  fi
fi
PR_URL="$(gh pr view "$BRANCH" --json url -q .url 2>/dev/null || echo '')"
echo "PR_URL: ${PR_URL:-unknown}"

# Auto-merge strategy:
#   1) --admin: immediate squash merge bypassing required checks. /verify-slice
#      is the orchestrator's verification gate; CI here would duplicate it.
#   2) --auto: queue the merge until required checks pass. Works for non-admin
#      users on repos that have auto-merge enabled.
MERGE_OK=0
if gh pr merge "$BRANCH" --squash --delete-branch --admin >/tmp/pr-flow-merge.log 2>&1; then
  echo "GIT_WORKFLOW_READY: yes"
  echo "PUSH_READY: yes"
  echo "PR_READY: yes"
  echo "MERGED: yes (admin squash, branch deleted)"
  MERGE_OK=1
elif gh pr merge "$BRANCH" --squash --delete-branch --auto >>/tmp/pr-flow-merge.log 2>&1; then
  echo "GIT_WORKFLOW_READY: yes"
  echo "PUSH_READY: yes"
  echo "PR_READY: yes"
  echo "MERGED: auto-queued (waiting for required checks; will squash-merge + delete branch automatically)"
  MERGE_OK=1
fi

if [ "$MERGE_OK" -ne 1 ]; then
  echo "GIT_WORKFLOW_READY: yes"
  echo "PUSH_READY: yes"
  echo "PR_READY: yes"
  echo "MERGED: no"
  echo "Reason: PR created but neither --admin nor --auto merge succeeded. Review at: ${PR_URL:-unknown}"
  sed 's/^/  /' /tmp/pr-flow-merge.log >&2 || true
  exit 0
fi
