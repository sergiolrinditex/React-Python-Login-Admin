#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B -S "$ROOT/.claude/bin/check_worktree_deps_visible.py" "$@"
