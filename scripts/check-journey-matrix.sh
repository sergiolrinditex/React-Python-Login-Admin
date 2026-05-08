#!/usr/bin/env bash
# Drift check entre la Journey Coverage Matrix y los artefactos generados.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 -B -S "$ROOT/.claude/bin/check_journey_matrix.py" "$@"
