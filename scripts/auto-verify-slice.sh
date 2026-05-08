#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B "$ROOT/.claude/bin/auto_verify_slice.py" "$@"
