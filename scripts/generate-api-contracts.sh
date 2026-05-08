#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$ROOT_DIR}" python3 -B -S "$ROOT_DIR/.claude/bin/generate_api_contracts.py" "$@"
