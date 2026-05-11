#!/usr/bin/env python3
"""PostToolUse hook — pure observability.

Appends one line per tool use to `orchestrator-state/tasks/ledger.jsonl` so the closer
and evidence-report have end-to-end traceability. NEVER blocks, NEVER denies.
"""
from __future__ import annotations

import json
import sys

from common import (
    append_jsonl,
    effective_active_task_id,
    find_task,
    ledger_path,
    load_active_task,
    load_registry,
    load_runtime_state,
    log_hook_error,
    now_iso,
)


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        data = json.loads(raw)
        tool_name = data.get("tool_name")
        tool_input = data.get("tool_input", {}) or {}
        active = load_active_task()
        runtime = load_runtime_state()
        task_id = effective_active_task_id(active)
        phase_id = runtime.get("active_phase_id")
        if task_id and task_id != active.get("id"):
            # Parallel DAG workers pin state with CLAUDE_ACTIVE_TASK_ID; the
            # singleton active-task.json may point at another terminal's slice.
            # Derive the phase from registry when possible so ledger lines stay
            # scoped to the worker node, not the global pointer.
            task = find_task(load_registry(), task_id)
            if task:
                phase_id = task.get("phase_id") or phase_id

        record = {
            "ts": now_iso(),
            "event": "post_tool_use",
            "tool_name": tool_name,
            "active_phase_id": phase_id,
            "active_task_id": task_id,
        }
        if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
            record["file_path"] = tool_input.get("file_path") or tool_input.get("notebook_path")
        elif tool_name == "Bash":
            record["command"] = (tool_input.get("command") or "")[:500]
        append_jsonl(ledger_path(), record)
    except Exception as exc:
        # Never block on hook failures — but leave a visible trail.
        log_hook_error("hook_update_ledger", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
