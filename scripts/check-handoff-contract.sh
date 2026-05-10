#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 -B -S "$ROOT/.claude/bin/check_handoff_contract.py" "$@"
