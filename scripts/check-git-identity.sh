#!/usr/bin/env bash
set -euo pipefail

STRICT=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/check-git-identity.sh [--strict]

Prints the effective Git author/committer identity and optional expectations.
No personal account is hardcoded in the orchestrator template.

Expectation sources, highest priority first:
  env: CLAUDE_GIT_EXPECTED_NAME / CLAUDE_EXPECTED_GIT_USER
       CLAUDE_GIT_EXPECTED_EMAIL / CLAUDE_EXPECTED_GIT_EMAIL
       CLAUDE_GIT_EXPECTED_LOGIN / CLAUDE_EXPECTED_GH_LOGIN
  git config: claude.expectedUserName / claude.expectedUserEmail / claude.expectedGithubLogin
              claude.requiredUserName / claude.requiredUserEmail / claude.requiredGithubLogin
  STACK_PROFILE.yaml: git_identity.user_name / user_email / github_login

In --strict mode, configured expectations are enforced. Missing user.name or
user.email is always an error because git commit would fail or use an unintended
fallback.
USAGE
      exit 0
      ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "GIT_IDENTITY_READY: skipped"
  echo "Reason: not inside a git repository"
  exit 0
fi

WORKSPACE_ROOT="$(git rev-parse --show-toplevel)"
CONFIG_ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-}"
if [ -z "$CONFIG_ROOT" ] && [ -x "$WORKSPACE_ROOT/scripts/ensure-task-worktree.sh" ]; then
  CONFIG_ROOT="$(bash "$WORKSPACE_ROOT/scripts/ensure-task-worktree.sh" --print-root 2>/dev/null || true)"
fi
CONFIG_ROOT="${CONFIG_ROOT:-$WORKSPACE_ROOT}"

profile_get() {
  local key="$1"
  if [ -x "$CONFIG_ROOT/.claude/bin/stack_profile.py" ]; then
    python3 -B -S "$CONFIG_ROOT/.claude/bin/stack_profile.py" --root "$CONFIG_ROOT" --get "$key" --default "" 2>/dev/null || true
  fi
}

first_nonempty() {
  local value
  for value in "$@"; do
    if [ -n "$value" ]; then
      printf '%s\n' "$value"
      return 0
    fi
  done
  return 0
}

actual_name="$(git config --get user.name 2>/dev/null || true)"
actual_email="$(git config --get user.email 2>/dev/null || true)"
author_ident="$(git var GIT_AUTHOR_IDENT 2>/dev/null || true)"
committer_ident="$(git var GIT_COMMITTER_IDENT 2>/dev/null || true)"
signing_key="$(git config --get user.signingkey 2>/dev/null || true)"
gpgsign="$(git config --get commit.gpgsign 2>/dev/null || true)"
signing_format="$(git config --get gpg.format 2>/dev/null || true)"

expected_name="$(first_nonempty \
  "${CLAUDE_GIT_EXPECTED_NAME:-}" \
  "${CLAUDE_EXPECTED_GIT_USER:-}" \
  "$(git config --get claude.expectedUserName 2>/dev/null || true)" \
  "$(git config --get claude.requiredUserName 2>/dev/null || true)" \
  "$(git config --get orchestrator.requiredUserName 2>/dev/null || true)" \
  "$(profile_get git_identity.user_name)" \
)"
expected_email="$(first_nonempty \
  "${CLAUDE_GIT_EXPECTED_EMAIL:-}" \
  "${CLAUDE_EXPECTED_GIT_EMAIL:-}" \
  "$(git config --get claude.expectedUserEmail 2>/dev/null || true)" \
  "$(git config --get claude.requiredUserEmail 2>/dev/null || true)" \
  "$(git config --get orchestrator.requiredUserEmail 2>/dev/null || true)" \
  "$(profile_get git_identity.user_email)" \
)"
expected_login="$(first_nonempty \
  "${CLAUDE_GIT_EXPECTED_LOGIN:-}" \
  "${CLAUDE_EXPECTED_GH_LOGIN:-}" \
  "$(git config --get claude.expectedGithubLogin 2>/dev/null || true)" \
  "$(git config --get claude.requiredGithubLogin 2>/dev/null || true)" \
  "$(git config --get orchestrator.requiredGithubLogin 2>/dev/null || true)" \
  "$(profile_get git_identity.github_login)" \
)"

printf 'GIT_IDENTITY_USER_NAME: %s\n' "${actual_name:-unset}"
printf 'GIT_IDENTITY_USER_EMAIL: %s\n' "${actual_email:-unset}"
printf 'GIT_AUTHOR_IDENT: %s\n' "${author_ident:-unavailable}"
printf 'GIT_COMMITTER_IDENT: %s\n' "${committer_ident:-unavailable}"
printf 'GIT_SIGNING_KEY: %s\n' "${signing_key:-unset}"
printf 'GIT_COMMIT_GPGSIGN: %s\n' "${gpgsign:-unset}"
printf 'GIT_SIGNING_FORMAT: %s\n' "${signing_format:-unset}"

if [ -n "${GIT_AUTHOR_NAME:-}" ] || [ -n "${GIT_AUTHOR_EMAIL:-}" ] || [ -n "${GIT_COMMITTER_NAME:-}" ] || [ -n "${GIT_COMMITTER_EMAIL:-}" ]; then
  echo "GIT_IDENTITY_ENV_OVERRIDE: yes"
else
  echo "GIT_IDENTITY_ENV_OVERRIDE: no"
fi

actual_login=""
if [ -n "$expected_login" ] || [ "${CLAUDE_GIT_CHECK_GH:-0}" = "1" ]; then
  if command -v gh >/dev/null 2>&1; then
    if command -v timeout >/dev/null 2>&1; then
      actual_login="$(GH_PROMPT_DISABLED=1 timeout 5 gh api user --jq .login 2>/dev/null || true)"
    else
      actual_login="$(GH_PROMPT_DISABLED=1 gh api user --jq .login 2>/dev/null || true)"
    fi
    printf 'GH_AUTH_USER: %s
' "${actual_login:-unavailable}"
  else
    echo "GH_AUTH_USER: gh_not_installed"
  fi
else
  echo "GH_AUTH_USER: not_checked"
fi

errors=0
if [ -z "$actual_name" ] || [ -z "$actual_email" ]; then
  echo "GIT_IDENTITY_MISSING: user.name/user.email"
  errors=$((errors + 1))
fi
if [ -n "$expected_name" ] && [ "$actual_name" != "$expected_name" ]; then
  echo "GIT_IDENTITY_MISMATCH: user.name expected='$expected_name' actual='${actual_name:-unset}'"
  errors=$((errors + 1))
fi
if [ -n "$expected_email" ] && [ "$actual_email" != "$expected_email" ]; then
  echo "GIT_IDENTITY_MISMATCH: user.email expected='$expected_email' actual='${actual_email:-unset}'"
  errors=$((errors + 1))
fi
if [ -n "$expected_login" ] && [ -z "$actual_login" ]; then
  echo "GIT_IDENTITY_MISSING: gh login expected='$expected_login' actual=unavailable"
  errors=$((errors + 1))
elif [ -n "$expected_login" ] && [ "$actual_login" != "$expected_login" ]; then
  echo "GIT_IDENTITY_MISMATCH: gh login expected='$expected_login' actual='$actual_login'"
  errors=$((errors + 1))
fi

if [ "$errors" -gt 0 ]; then
  echo "GIT_IDENTITY_READY: no"
  [ -n "$expected_name" ] && echo "Fix user.name: git config user.name '$expected_name'"
  [ -n "$expected_email" ] && echo "Fix user.email: git config user.email '$expected_email'"
  if [ -n "$expected_login" ]; then
    echo "Fix GitHub auth: gh auth switch -u '$expected_login' || gh auth login --hostname github.com --git-protocol ssh"
  fi
  [ "$STRICT" -eq 1 ] && exit 3
  exit 0
fi

echo "GIT_IDENTITY_READY: yes"
if [ -n "$expected_name" ] || [ -n "$expected_email" ] || [ -n "$expected_login" ]; then
  echo "GIT_IDENTITY_EXPECTATION: enforced"
else
  echo "GIT_IDENTITY_EXPECTATION: unset"
fi
