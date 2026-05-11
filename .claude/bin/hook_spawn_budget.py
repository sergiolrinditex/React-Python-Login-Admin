#!/usr/bin/env python3
"""PreToolUse hook for the Agent tool: enforce the per-slice spawn budget.

SubagentStart cannot block creation in Claude Code; PreToolUse on the Agent
call can. This hook is intentionally conservative and stdlib-only:
  - If the tool is not Agent, it exits cleanly.
  - If no DAG task exists yet, it exits cleanly.
  - If the DAG task has already consumed the budget recorded by
    SubagentStop, it denies the next Agent call and tells Claude what to do.

The SubagentStop hook remains the source of truth for completed-spawn counts;
this hook prevents the obvious 21st spawn after twenty completed subagents. It is
not a scheduler and does not try to reserve parallel in-flight spawns.
"""
from __future__ import annotations

import json
import sys

from common import dag_worker_task_id, get_spawn_budget, get_spawn_count, log_hook_error


def _agent_name(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return "unknown"
    for key in ("subagent_type", "agent_type", "name", "teammate_name"):
        val = tool_input.get(key)
        if val:
            return str(val)
    return "unknown"


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        payload = json.loads(raw)
        tool_name = str(payload.get("tool_name") or "")
        if tool_name != "Agent":
            return 0

        task_id = dag_worker_task_id()
        if not task_id:
            return 0

        count = get_spawn_count(str(task_id))
        budget = get_spawn_budget()
        if count >= budget:
            agent = _agent_name(payload)
            _deny(
                f"Spawn budget reached for slice {task_id}: {count}/{budget}. "
                f"Do not spawn agent '{agent}'. Run /clear, inspect orchestrator-state/tasks/runtime-state.json, "
                "or split/waive the slice explicitly before continuing."
            )
    except Exception as exc:  # hooks must never crash the pipeline silently
        log_hook_error("hook_spawn_budget", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
