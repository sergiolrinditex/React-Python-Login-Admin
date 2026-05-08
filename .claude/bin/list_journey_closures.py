#!/usr/bin/env python3
"""List journeys that would become ready for verification when a TASK_ID closes.

This is the runtime-safe replacement for checking registry.journeys[].task_ids[-1].
In a DAG, the human-authored Slices cell is not authoritative ordering; a journey
is ready for verification when all of its declared task_ids are done, treating
the current TASK_ID as done for the purpose of pre-close planning.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from common import (
    find_task,
    journey_completion_task_ids,
    journeys_closing_at_task,
    load_registry,
)

DONE_JOURNEY_STATES = {"verified", "waived"}


def classify_journey_closures(registry: dict[str, Any], task_id: str, *, assume_current_done: bool = True) -> dict[str, Any]:
    tasks_by_id = {str(t.get("id")): t for t in registry.get("tasks", []) or [] if t.get("id")}
    current = tasks_by_id.get(task_id)
    if not current:
        return {"ok": False, "task_id": task_id, "error": f"TASK_ID not found: {task_id}", "closing_journeys": [], "participating_journeys": []}

    simulated = json.loads(json.dumps(registry))
    if assume_current_done:
        sim_task = find_task(simulated, task_id)
        if sim_task:
            sim_task["status"] = "done"

    closing_ids = set(journeys_closing_at_task(simulated, task_id))
    participating: list[dict[str, Any]] = []
    closing: list[dict[str, Any]] = []
    for journey in simulated.get("journeys", []) or []:
        task_ids = [str(t) for t in (journey.get("task_ids") or []) if t]
        if task_id not in task_ids:
            continue
        status = str(journey.get("verification_status") or "pending")
        terminal = list(journey.get("terminal_task_ids") or journey_completion_task_ids(simulated, journey))
        missing_after_current = [
            tid for tid in task_ids
            if tid != task_id and str((find_task(simulated, tid) or {}).get("status") or "") != "done"
        ]
        row = {
            "id": journey.get("id"),
            "title": journey.get("title"),
            "verification_status": status,
            "task_ids": task_ids,
            "terminal_task_ids": terminal,
            "completion_policy": journey.get("completion_policy") or "all_task_ids_done",
            "missing_dependencies_after_current_done": missing_after_current,
            "ready_to_verify_after_current_done": journey.get("id") in closing_ids,
            "already_closed": status in DONE_JOURNEY_STATES,
        }
        participating.append(row)
        if row["ready_to_verify_after_current_done"]:
            closing.append(row)

    return {
        "ok": True,
        "task_id": task_id,
        "assume_current_done": assume_current_done,
        "closing_journeys": closing,
        "participating_journeys": participating,
    }


def print_text(result: dict[str, Any]) -> None:
    if not result.get("ok"):
        print(f"Journey closures: ERROR {result.get('error')}")
        return
    print(f"Journey closures for {result.get('task_id')} (assuming current done={result.get('assume_current_done')})")
    closing = result.get("closing_journeys") or []
    if not closing:
        print("- closing_journeys: none")
    else:
        print("- closing_journeys:")
        for row in closing:
            terminal = ", ".join(row.get("terminal_task_ids") or []) or "—"
            print(f"  - {row.get('id')} status={row.get('verification_status')} terminal={terminal}")
    participating = result.get("participating_journeys") or []
    if participating:
        print("- participating_journeys:")
        for row in participating:
            missing = ", ".join(row.get("missing_dependencies_after_current_done") or []) or "—"
            print(f"  - {row.get('id')} ready={row.get('ready_to_verify_after_current_done')} missing_after_current_done={missing}")


def main() -> int:
    parser = argparse.ArgumentParser(description="List journeys that close when TASK_ID closes.")
    parser.add_argument("task_id", help="TASK_ID to inspect")
    parser.add_argument("--current-status", action="store_true", help="Do not simulate current TASK_ID as done")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = classify_journey_closures(load_registry(), args.task_id, assume_current_done=not args.current_status)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
