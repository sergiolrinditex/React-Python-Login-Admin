#!/usr/bin/env python3
"""Stop hook — schedule deferred worktree cleanup after Claude hooks finish.

`cleanup-worktrees.sh` queues the active task worktree instead of deleting it
while Claude is still running SubagentStop/Stop hooks. This hook schedules a
delayed janitor from the canonical root, so normal closes clean themselves
without risking loss of the closer trailer.
"""
from __future__ import annotations

import os
import subprocess
import sys

from common import project_root, log_hook_error


def main() -> int:
    try:
        try:
            sys.stdin.read()
        except Exception:
            pass
        if os.environ.get("CLAUDE_DEFERRED_CLEANUP_DISABLE") == "1":
            return 0

        root = project_root()
        req_dir = root / "orchestrator-state" / "tasks" / "cleanup-requests"
        if not req_dir.exists() or not any(req_dir.glob("*.json")):
            return 0

        delay = os.environ.get("CLAUDE_DEFERRED_CLEANUP_DELAY", "10")
        interval = os.environ.get("CLAUDE_DEFERRED_CLEANUP_INTERVAL", "15")
        timeout = os.environ.get("CLAUDE_DEFERRED_CLEANUP_TIMEOUT", "600")
        log_dir = root / "orchestrator-state" / "tasks"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "cleanup-deferred-hook.log"
        script = root / "scripts" / "cleanup-deferred-worktrees-loop.sh"
        if not script.exists():
            script = root / "scripts" / "cleanup-deferred-worktrees.sh"
        if not script.exists():
            return 0

        env = os.environ.copy()
        env["CLAUDE_ORCHESTRATOR_ROOT"] = str(root)
        # The child is an external janitor, not the old task checkout.
        for key in ("CLAUDE_PROJECT_DIR", "CLAUDE_WORKTREE_ROOT", "CLAUDE_WORKSPACE_ROOT"):
            env.pop(key, None)
        if script.name == "cleanup-deferred-worktrees-loop.sh":
            cmd = [
                "bash",
                str(script),
                "--initial-delay",
                str(delay),
                "--interval",
                str(interval),
                "--timeout",
                str(timeout),
                "--quiet",
            ]
        else:
            cmd = [
                "bash",
                "-lc",
                "sleep \"$1\"; cd \"$2\" && bash scripts/cleanup-deferred-worktrees.sh --apply --quiet",
                "cleanup-deferred-hook",
                str(delay),
                str(root),
            ]
        with log_path.open("a", encoding="utf-8") as log:
            subprocess.Popen(
                cmd,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                env=env,
                start_new_session=True,
                close_fds=True,
            )
    except Exception as exc:
        log_hook_error("hook_finalize_deferred_cleanup", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
