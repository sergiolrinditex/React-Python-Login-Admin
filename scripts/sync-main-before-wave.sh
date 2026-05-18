#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
exec python3 -B -S "$ROOT/scripts/sync_main_before_wave.py" "$@"
