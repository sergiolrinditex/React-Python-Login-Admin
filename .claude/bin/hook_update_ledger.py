#!/usr/bin/env python3
"""PostToolUse hook — pure observability.

Write/Edit/MultiEdit/NotebookEdit events are appended to the canonical
`orchestrator-state/tasks/ledger.jsonl`. Bash events are appended to
`orchestrator-state/tasks/bash-ledger.jsonl`, which is git-ignored on purpose.

Why split them? In DAG production mode the closer creates an atomic commit and
then runs the configured Git workflow. Claude Code PostToolUse hooks run *after*
each Bash command. If every Bash call appends to the tracked ledger, the hook can
re-dirty the worktree immediately after commit/push and send close workflows into
`git status` / `stash pop` loops. Bash traceability remains available in the
runtime ledger without affecting Git cleanliness.

The hook NEVER blocks and NEVER denies.
"""
from __future__ import annotations

import json
import sys

from common import (
    dag_worker_task_id,
    append_jsonl,
    bash_ledger_path,
    find_task,
    ledger_path,
    load_registry,
    log_hook_error,
    now_iso,
)

def _ledger_for_tool(tool_name: str):
    if tool_name == "Bash":
        return bash_ledger_path()
    return ledger_path()


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        data = json.loads(raw)
        tool_name = data.get("tool_name")
        tool_input = data.get("tool_input", {}) or {}
        task_id = dag_worker_task_id()
        phase_id = None
        if task_id:
            task = find_task(load_registry(), task_id)
            if task:
                phase_id = task.get("phase_id")

        record = {
            "ts": now_iso(),
            "event": "post_tool_use",
            "tool_name": tool_name,
            "phase_id": phase_id,
            "task_id": task_id,
        }
        if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
            record["file_path"] = tool_input.get("file_path") or tool_input.get("notebook_path")
        elif tool_name == "Bash":
            record["command"] = (tool_input.get("command") or "")[:500]
            record["runtime_only"] = True
        else:
            # Settings currently call this hook only for Write/Edit/MultiEdit/
            # NotebookEdit/Bash, but remain permissive if future tools are added.
            record["tool_input_keys"] = sorted(tool_input.keys())[:20]
        append_jsonl(_ledger_for_tool(str(tool_name)), record)
    except Exception as exc:
        # Never block on hook failures — but leave a visible trail.
        log_hook_error("hook_update_ledger", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
