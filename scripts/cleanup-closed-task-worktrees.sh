#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec python3 -B -S "$ROOT/scripts/cleanup_closed_task_worktrees.py" "$@"
