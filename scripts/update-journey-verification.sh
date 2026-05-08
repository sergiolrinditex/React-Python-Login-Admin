#!/usr/bin/env bash
set -euo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
exec python3 -B -S "$ROOT/.claude/bin/update_journey_verification.py" "$@"
