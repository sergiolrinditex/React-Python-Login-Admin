#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B -S "$ROOT/scripts/check_staged_deletions.py" "$@"
