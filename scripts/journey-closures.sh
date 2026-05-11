#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B -S "$ROOT/.claude/bin/list_journey_closures.py" "$@"
