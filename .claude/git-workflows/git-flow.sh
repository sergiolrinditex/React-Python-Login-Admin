#!/usr/bin/env bash
# git-flow.sh -- Closer's Git workflow for git_workflow: git-flow
#
# Implements the Vincent Driessen Gitflow model adapted for DAG orchestration.
# /verify-slice is the human verification gate; this script is transport-only.
#
# Branch conventions (auto-detected from current branch name):
#   feature/<TASK_ID>-*  →  merge into 'develop', delete feature branch
#   release/<version>    →  merge into 'main' + 'develop', tag vX.Y.Z, delete release branch
#   hotfix/<version>     →  merge into 'main' + 'develop', tag vX.Y.Z-hotfix.N, delete hotfix branch
#   develop              →  push develop (manual / CI trigger, no merge)
#
# All merges use --no-ff to preserve branch topology in history.
# Fast-forward is intentionally disabled so the graph always shows parallel work.
#
# Outputs (closer parses these from stdout):
#   GIT_WORKFLOW_READY:  yes|no|blocked
#   PUSH_READY:          yes|no
#   BRANCH_TYPE:         feature|release|hotfix|develop|unknown
#   MERGED_TO_DEVELOP:   yes|no
#   MERGED_TO_MAIN:      yes|no
#   TAGGED:              <tag> | no
#   BRANCH_DELETED:      yes|no
#   REBASE_CONFLICT:     yes  (only when blocked)
#
# Exit codes:
#   0   success
#   2   wrong branch for this workflow / not a git repo
#   3   push / merge / tag failed
#   4   rebase conflict; manual resolution required

set -euo pipefail

# ── Helpers ───────────────────────────────────────────────────────────────────
log()    { echo "$*"; }
warn()   { echo "WARN: $*" >&2; }
abort()  { echo "GIT_WORKFLOW_READY: blocked"; echo "PUSH_READY: no"; echo "$*"; exit "${2:-3}"; }

# ── Config ────────────────────────────────────────────────────────────────────
BRANCH="$(git branch --show-current)"
DEVELOP_BRANCH="${GIT_FLOW_DEVELOP:-develop}"
MAIN_BRANCH="${GIT_FLOW_MAIN:-main}"

# Resolve remote: honour upstream tracking config, fall back to 'origin'.
REMOTE="$(git config "branch.${BRANCH}.remote" 2>/dev/null || echo origin)"
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  REMOTE="origin"
fi
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  abort "Reason: remote '$REMOTE' not found. Add it with: git remote add $REMOTE <url>"
fi

# ── Branch type detection ─────────────────────────────────────────────────────
detect_branch_type() {
  case "$BRANCH" in
    feature/*)  echo "feature"  ;;
    release/*)  echo "release"  ;;
    hotfix/*)   echo "hotfix"   ;;
    "$DEVELOP_BRANCH") echo "develop" ;;
    "$MAIN_BRANCH")    echo "main"    ;;
    *)          echo "unknown"  ;;
  esac
}

BRANCH_TYPE="$(detect_branch_type)"
log "BRANCH_TYPE: ${BRANCH_TYPE}"

if [ "$BRANCH_TYPE" = "unknown" ]; then
  echo "GIT_WORKFLOW_READY: no"
  echo "PUSH_READY: no"
  echo "Reason: branch '$BRANCH' does not match git-flow conventions."
  echo "  Expected: feature/<name>, release/<version>, hotfix/<version>, or '$DEVELOP_BRANCH'."
  echo "  Rename with: git branch -m <new-name>"
  exit 2
fi

if [ "$BRANCH_TYPE" = "main" ]; then
  echo "GIT_WORKFLOW_READY: no"
  echo "PUSH_READY: no"
  echo "Reason: direct push to '$MAIN_BRANCH' is not allowed in git-flow."
  echo "  Use a release/* or hotfix/* branch to reach $MAIN_BRANCH."
  exit 2
fi

# ── Fetch all refs we'll need ─────────────────────────────────────────────────
log "Fetching ${REMOTE}..."
if ! git fetch "$REMOTE" --tags >/tmp/git-flow-fetch.log 2>&1; then
  abort "Reason: git fetch $REMOTE failed. See /tmp/git-flow-fetch.log" 3
fi

# ── Ensure develop exists locally ─────────────────────────────────────────────
if ! git rev-parse --verify "$DEVELOP_BRANCH" >/dev/null 2>&1; then
  if git rev-parse --verify "${REMOTE}/${DEVELOP_BRANCH}" >/dev/null 2>&1; then
    git checkout -b "$DEVELOP_BRANCH" "${REMOTE}/${DEVELOP_BRANCH}" >/dev/null
    git checkout "$BRANCH" >/dev/null
  else
    abort "Reason: branch '$DEVELOP_BRANCH' not found locally or on '$REMOTE'." \
      "Create it with: git checkout -b $DEVELOP_BRANCH $MAIN_BRANCH && git push -u $REMOTE $DEVELOP_BRANCH"
  fi
fi

# ── Rebase feature branch onto latest develop (keeps history linear) ──────────
rebase_onto_develop() {
  local base
  base="$(git merge-base "${REMOTE}/${DEVELOP_BRANCH}" HEAD 2>/dev/null || echo)"
  local remote_sha
  remote_sha="$(git rev-parse "${REMOTE}/${DEVELOP_BRANCH}" 2>/dev/null || echo)"

  if [ -z "$base" ] || [ "$base" = "$remote_sha" ]; then
    log "REBASED_ON_DEVELOP: no (already up to date)"
    return 0
  fi

  if git rebase "${REMOTE}/${DEVELOP_BRANCH}" >/tmp/git-flow-rebase.log 2>&1; then
    log "REBASED_ON_DEVELOP: yes"
  else
    git rebase --abort 2>/dev/null || true
    echo "GIT_WORKFLOW_READY: blocked"
    echo "PUSH_READY: no"
    echo "REBASE_CONFLICT: yes"
    echo "Reason: rebase onto ${REMOTE}/${DEVELOP_BRANCH} had conflicts. Resolve manually:"
    echo "  git rebase ${REMOTE}/${DEVELOP_BRANCH}"
    echo "  # fix conflicts, git add <files>, git rebase --continue"
    echo "  ./scripts/git-workflow.sh   # retry"
    sed 's/^/  /' /tmp/git-flow-rebase.log >&2 || true
    exit 4
  fi
}

# ── Merge <branch> into <target> with --no-ff ─────────────────────────────────
merge_into() {
  local target="$1"
  local source_branch="$2"
  local current_sha
  current_sha="$(git rev-parse HEAD)"

  git checkout "$target" >/dev/null 2>&1
  # Fast-forward target to remote state first.
  git merge --ff-only "${REMOTE}/${target}" >/dev/null 2>&1 || true

  if ! git merge --no-ff "$source_branch" \
      -m "chore(git-flow): merge $source_branch into $target" \
      >/tmp/git-flow-merge-"${target}".log 2>&1; then
    git checkout "$source_branch" >/dev/null 2>&1 || true
    abort "Reason: merge of '$source_branch' into '$target' failed. See /tmp/git-flow-merge-${target}.log"
  fi

  git checkout "$source_branch" >/dev/null 2>&1
}

# ── Push a branch to remote ───────────────────────────────────────────────────
push_branch() {
  local b="$1"
  local flags="${2:---force-with-lease}"
  if ! git push $flags "$REMOTE" "$b" >/tmp/git-flow-push-"${b//\//-}".log 2>&1; then
    abort "Reason: push of '$b' to '$REMOTE' failed. See /tmp/git-flow-push-${b//\//-}.log"
  fi
}

# ── Create and push a version tag ────────────────────────────────────────────
create_tag() {
  local tag="$1"
  local message="$2"
  if git rev-parse --verify "refs/tags/${tag}" >/dev/null 2>&1; then
    warn "Tag '${tag}' already exists — skipping tag creation."
    log "TAGGED: ${tag} (pre-existing)"
    return 0
  fi
  git tag -a "$tag" -m "$message"
  if ! git push "$REMOTE" "$tag" >/tmp/git-flow-tag.log 2>&1; then
    abort "Reason: push of tag '$tag' failed. See /tmp/git-flow-tag.log"
  fi
  log "TAGGED: ${tag}"
}

# ── Delete branch locally and remotely ───────────────────────────────────────
delete_branch() {
  local b="$1"
  git branch -d "$b" 2>/dev/null || git branch -D "$b" 2>/dev/null || warn "Could not delete local branch '$b'."
  git push "$REMOTE" --delete "$b" >/dev/null 2>&1 || warn "Could not delete remote branch '$REMOTE/$b' (may not exist)."
  log "BRANCH_DELETED: yes"
}

# ═══════════════════════════════════════════════════════════════════════════════
# Feature flow:  feature/* → develop
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$BRANCH_TYPE" = "feature" ]; then
  rebase_onto_develop

  # Push rebased feature branch (--force-with-lease because rebase rewrites SHAs).
  push_branch "$BRANCH" "--force-with-lease -u"
  log "PUSH_READY: yes"

  merge_into "$DEVELOP_BRANCH" "$BRANCH"
  log "MERGED_TO_DEVELOP: yes"
  log "MERGED_TO_MAIN: no"

  push_branch "$DEVELOP_BRANCH"

  delete_branch "$BRANCH"

  log "GIT_WORKFLOW_READY: yes"
  log "TAGGED: no"
  exit 0
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Develop push (manual / no merge needed)
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$BRANCH_TYPE" = "develop" ]; then
  REMOTE_AHEAD="$(git rev-list --count "HEAD..${REMOTE}/${DEVELOP_BRANCH}" 2>/dev/null || echo 0)"
  if [ "$REMOTE_AHEAD" -gt 0 ]; then
    abort "Reason: ${REMOTE}/${DEVELOP_BRANCH} is ${REMOTE_AHEAD} commit(s) ahead of local. Rebase first:
  git fetch ${REMOTE} ${DEVELOP_BRANCH}
  git rebase ${REMOTE}/${DEVELOP_BRANCH}
  ./scripts/git-workflow.sh"
  fi

  push_branch "$DEVELOP_BRANCH"

  log "GIT_WORKFLOW_READY: yes"
  log "PUSH_READY: yes"
  log "MERGED_TO_DEVELOP: no"
  log "MERGED_TO_MAIN: no"
  log "TAGGED: no"
  log "BRANCH_DELETED: no"
  exit 0
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Release / Hotfix flow:  release/* or hotfix/* → main + develop, tag, delete
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$BRANCH_TYPE" = "release" ] || [ "$BRANCH_TYPE" = "hotfix" ]; then
  # Extract version from branch name (release/1.2.3 → 1.2.3).
  VERSION="${BRANCH#*/}"
  if [ "$BRANCH_TYPE" = "hotfix" ]; then
    TAG="v${VERSION}-hotfix"
  else
    TAG="v${VERSION}"
  fi

  # Push the release/hotfix branch to remote first.
  push_branch "$BRANCH" "--force-with-lease -u"
  log "PUSH_READY: yes"

  # Ensure main exists locally.
  if ! git rev-parse --verify "$MAIN_BRANCH" >/dev/null 2>&1; then
    git checkout -b "$MAIN_BRANCH" "${REMOTE}/${MAIN_BRANCH}" >/dev/null
    git checkout "$BRANCH" >/dev/null
  fi

  # Merge into main.
  merge_into "$MAIN_BRANCH" "$BRANCH"
  log "MERGED_TO_MAIN: yes"
  push_branch "$MAIN_BRANCH"

  # Tag on main.
  git checkout "$MAIN_BRANCH" >/dev/null 2>&1
  create_tag "$TAG" "Release ${TAG} — merged from ${BRANCH}"
  git checkout "$BRANCH" >/dev/null 2>&1

  # Merge into develop (carry release commits / fixes forward).
  merge_into "$DEVELOP_BRANCH" "$BRANCH"
  log "MERGED_TO_DEVELOP: yes"
  push_branch "$DEVELOP_BRANCH"

  delete_branch "$BRANCH"

  log "GIT_WORKFLOW_READY: yes"
  exit 0
fi
