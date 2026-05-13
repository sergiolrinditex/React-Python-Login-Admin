#!/usr/bin/env bash
# pr-flow.sh -- Closer's Git workflow for git_workflow: pr-flow
#
# Steps:
#   1. Verify we are on a feature branch (not main).
#   2. Fetch + rebase onto the latest main BEFORE the push. This avoids
#      the most common cause of "PR mergeable: CONFLICTING": other slices
#      that closed while this one was alive already moved generated state
#      (PROGRESS.md, MEMORY.md, task-dag.json, etc.) forward on main.
#      If the rebase is conflict-free, the PR will fast-forward cleanly.
#      If real conflicts exist, abort rebase and surface to the human
#      (closer will not try to push or merge — better fail loudly than
#       force-push something half-resolved).
#   3. Push the branch (--force-with-lease because rebase rewrites SHAs).
#   4. Create a PR via gh (or reuse the existing one for this branch).
#   5. Auto-merge: try --admin (immediate squash merge bypassing checks)
#      first because /verify-slice already provided real human verification
#      with real data; CI on the PR would re-run what the human just
#      validated. If --admin fails (no admin permission), fall back to
#      --auto (queues the merge until required checks pass).
#
# Outputs (closer parses these from stdout):
#   GIT_WORKFLOW_READY: yes|no|blocked
#   PUSH_READY:        yes|no
#   PR_READY:          yes|no
#   MERGED:            yes | auto-queued | no
#   PR_URL:            <url>
#   REBASED_ON_MAIN:   yes | no
#   REBASE_CONFLICT:   yes (only when blocked by rebase)
#
# Exit codes:
#   0   PR created and (merged immediately OR queued for auto-merge)
#   2   branch is main; pr-flow is wrong workflow for this checkout
#   3   gh CLI missing OR PR creation failed OR neither merge mode worked
#   4   rebase against upstream main hit real conflicts; manual resolution required

set -euo pipefail
BRANCH="$(git branch --show-current)"
if [ "$BRANCH" = "main" ]; then
  echo "GIT_WORKFLOW_READY: no"
  echo "Reason: pr-flow requires a feature branch, not main. Use git_workflow: push-to-main/direct-main for intentional direct pushes to main."
  exit 2
fi

# Resolve which remote owns main (origin by default, but pr-flow projects
# may have custom remote names like 'inditex'). git config branch.main.remote
# tells us the configured upstream; fallback to 'origin'.
TARGET_REMOTE="$(git config branch.main.remote 2>/dev/null || echo origin)"
if ! git ls-remote --exit-code "$TARGET_REMOTE" >/dev/null 2>&1; then
  TARGET_REMOTE="origin"
fi

# --- Rebase pre-push ---
# Pull the latest main from the upstream that hosts it. If the fetch itself
# fails (network, auth), abort cleanly without leaving the branch in a
# half-rebased state.
if ! git fetch "$TARGET_REMOTE" main >/tmp/pr-flow-fetch.log 2>&1; then
  echo "GIT_WORKFLOW_READY: blocked"
  echo "PUSH_READY: no"
  echo "Reason: git fetch $TARGET_REMOTE main failed; see /tmp/pr-flow-fetch.log"
  sed 's/^/  /' /tmp/pr-flow-fetch.log >&2 || true
  exit 3
fi

# Detect whether main moved at all since the branch base. If not, no rebase
# needed and we keep the SHA stable (no --force-with-lease later).
BRANCH_BASE="$(git merge-base "$TARGET_REMOTE/main" HEAD 2>/dev/null || echo)"
TARGET_MAIN_SHA="$(git rev-parse "$TARGET_REMOTE/main" 2>/dev/null || echo)"
REBASED=0
if [ -n "$BRANCH_BASE" ] && [ -n "$TARGET_MAIN_SHA" ] && [ "$BRANCH_BASE" != "$TARGET_MAIN_SHA" ]; then
  if git rebase "$TARGET_REMOTE/main" >/tmp/pr-flow-rebase.log 2>&1; then
    REBASED=1
    echo "REBASED_ON_MAIN: yes (rebased onto $TARGET_REMOTE/main)"
  else
    # Real conflict. Abort cleanly so the worktree returns to a sane state,
    # then surface to the human. Closer treats exit 4 as 'blocked: needs
    # manual resolution', does NOT push.
    git rebase --abort 2>/dev/null || true
    echo "GIT_WORKFLOW_READY: blocked"
    echo "PUSH_READY: no"
    echo "PR_READY: no"
    echo "REBASE_CONFLICT: yes"
    echo "Reason: rebase onto $TARGET_REMOTE/main had conflicts. Resolve manually:"
    echo "  cd \$(pwd)"
    echo "  git rebase $TARGET_REMOTE/main"
    echo "  # fix conflicts, git add <files>, git rebase --continue"
    echo "  git push --force-with-lease $TARGET_REMOTE $BRANCH"
    echo "Conflict log: /tmp/pr-flow-rebase.log"
    sed 's/^/  /' /tmp/pr-flow-rebase.log >&2 || true
    exit 4
  fi
else
  echo "REBASED_ON_MAIN: no (branch already up to date with $TARGET_REMOTE/main)"
fi

# --- Push ---
# When rebased, SHA rewriting requires --force-with-lease. We ALSO use it
# when no rebase happened because it is a no-op in that case (the lease
# matches the remote SHA) and it remains safe against concurrent pushes
# from another terminal.
if [ "$REBASED" -eq 1 ]; then
  PUSH_FLAGS="--force-with-lease -u"
else
  PUSH_FLAGS="-u"
fi
if ! git push $PUSH_FLAGS "$TARGET_REMOTE" "$BRANCH" >/tmp/pr-flow-push.log 2>&1; then
  echo "GIT_WORKFLOW_READY: blocked"
  echo "PUSH_READY: no"
  echo "Reason: git push failed; see /tmp/pr-flow-push.log"
  sed 's/^/  /' /tmp/pr-flow-push.log >&2 || true
  exit 3
fi

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
