#!/usr/bin/env bash
# Stack-agnostic design-token dispatcher. Concrete rules live in .claude/enforcers/.
set -euo pipefail
TOOL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$TOOL_ROOT}"
ENFORCER="$(python3 -B -S "$TOOL_ROOT/.claude/bin/stack_profile.py" --root "$PROJECT_ROOT" --get design_tokens_enforcer --default none)"
ENFORCER="${ENFORCER//[^A-Za-z0-9_-]/}"
if [ -z "$ENFORCER" ]; then ENFORCER="none"; fi
PLUGIN="$TOOL_ROOT/.claude/enforcers/${ENFORCER}.sh"
if [ ! -x "$PLUGIN" ]; then
  echo "❌ Design-token enforcer not found or not executable: .claude/enforcers/${ENFORCER}.sh" >&2
  echo "Set design_tokens_enforcer in docs/source-of-truth/STACK_PROFILE.yaml." >&2
  exit 2
fi
exec "$PLUGIN" --project-root "$PROJECT_ROOT" "$@"
