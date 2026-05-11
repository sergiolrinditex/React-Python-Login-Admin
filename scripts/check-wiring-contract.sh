#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B "$ROOT/.claude/bin/check_wiring_contract.py" "$@"
