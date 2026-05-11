#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 -B -S "$ROOT/.claude/bin/reset_orchestrator_state.py"
