#!/usr/bin/env bash
set -euo pipefail

# One-time best-effort helper for repository-wide PR branch cleanup.
# Requires gh authentication and repository admin permission.

if ! command -v gh >/dev/null 2>&1; then
  echo "GITHUB_PR_CLEANUP_CONFIGURED: no"
  echo "Reason: gh CLI not found"
  exit 3
fi

if gh repo edit --delete-branch-on-merge >/dev/null 2>&1; then
  echo "GITHUB_PR_CLEANUP_CONFIGURED: yes"
  echo "DELETE_BRANCH_ON_MERGE: enabled"
  exit 0
fi

echo "GITHUB_PR_CLEANUP_CONFIGURED: no"
echo "Reason: could not enable delete-branch-on-merge. You need admin permission or repository rules may block it."
echo "Manual equivalent: gh repo edit --delete-branch-on-merge"
exit 3
