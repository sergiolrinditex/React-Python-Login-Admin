#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# Baseline writes are allowed only through this audited sync script.
export CLAUDE_ALLOW_BASELINE_SYNC_WRITES=1
python3 -B -S .claude/bin/sync_product_baseline.py "$@"
