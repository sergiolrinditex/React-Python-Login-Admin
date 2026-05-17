#!/usr/bin/env python3
"""Read-only task context inspector for /next-slice.

The Claude command should not hand-roll JSON snippets that assume a particular
registry shape. The canonical bootstrap writes tasks as a list, but some older
or migrated projects may still expose a mapping keyed by TASK_ID. This helper
normalizes both shapes and prints the small context /next-slice needs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import load_registry, load_runtime_state, project_root, workspace_root

ACTIVE_STATUSES = {
    "claimed",
    "in_progress",
    "validator_tester_pending",
    "needs_debug",
    "ready_for_close",
    "verified_pending_close",
}


def _normalize_items(raw: Any, *, id_key: str = "id") -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = []
        for key, value in raw.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault(id_key, str(key))
                items.append(item)
        return items
    return []


def _task_by_id(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(t.get("id")): t for t in tasks if t.get("id")}


def _git_branch(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "branch", "--show-current"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )
        return proc.stdout.strip() or "detached-or-unknown"
    except Exception:
        return "unknown"


def _exists_pair(root: Path, workspace: Path, rel: str) -> dict[str, Any]:
    workspace_path = workspace / rel
    canonical_path = root / rel
    return {
        "relative": rel,
        "workspace": str(workspace_path),
        "workspace_exists": workspace_path.exists(),
        "canonical": str(canonical_path),
        "canonical_exists": canonical_path.exists(),
    }


def _public_task(task: dict[str, Any] | None) -> dict[str, Any] | None:
    if not task:
        return None
    keep = [
        "id",
        "title",
        "status",
        "phase_id",
        "step_id",
        "depends_on",
        "journey_refs",
        "conflict_group",
        "write_set",
        "risk_level",
        "verify_mode",
        "task_pack_path",
        "acceptance",
        "verify_minimo",
        "verify",
    ]
    return {key: task.get(key) for key in keep if key in task}


def build_snapshot(task_id: str | None = None) -> dict[str, Any]:
    root = project_root()
    workspace = workspace_root()
    registry = load_registry()
    runtime = load_runtime_state()
    tasks = _normalize_items(registry.get("tasks"))
    phases = _normalize_items(registry.get("phases"))
    by_id = _task_by_id(tasks)
    task = by_id.get(str(task_id)) if task_id else None
    ready = [t for t in tasks if str(t.get("status") or "") == "ready"]
    active = [t for t in tasks if str(t.get("status") or "") in ACTIVE_STATUSES]
    done = [t for t in tasks if str(t.get("status") or "") == "done"]

    if task_id:
        task_pack_rel = f"orchestrator-state/tasks/task-packs/{task_id}.md"
        handoff_rel = f"orchestrator-state/tasks/handoffs/{task_id}.md"
    else:
        task_pack_rel = "orchestrator-state/tasks/task-packs/<TASK_ID>.md"
        handoff_rel = "orchestrator-state/tasks/handoffs/<TASK_ID>.md"

    warnings: list[str] = []
    if task_id and not task:
        warnings.append(f"TASK_ID {task_id} not found in registry tasks")
    pack = _exists_pair(root, workspace, task_pack_rel)
    handoff = _exists_pair(root, workspace, handoff_rel)
    if task_id and not pack["workspace_exists"] and pack["canonical_exists"]:
        warnings.append("task pack is missing in workspace but exists in canonical root; this is normal before planner/materialization")
    if task_id and not handoff["workspace_exists"] and not handoff["canonical_exists"]:
        warnings.append("handoff does not exist yet; this is normal before the slice pipeline starts")

    return {
        "ok": bool(not task_id or task),
        "task_id": task_id,
        "canonical_root": str(root),
        "workspace_root": str(workspace),
        "current_branch": _git_branch(workspace),
        "env": {
            "CLAUDE_ORCHESTRATOR_ROOT": os.environ.get("CLAUDE_ORCHESTRATOR_ROOT"),
            "CLAUDE_WORKTREE_ROOT": os.environ.get("CLAUDE_WORKTREE_ROOT"),
            "CLAUDE_ACTIVE_TASK_ID": os.environ.get("CLAUDE_ACTIVE_TASK_ID"),
            "CLAUDE_TASK_PACK": os.environ.get("CLAUDE_TASK_PACK"),
        },
        "dag_mode": (registry.get("task_dag") or {}).get("mode"),
        "phase_order": registry.get("phase_order") or [p.get("id") for p in phases if p.get("id")],
        "task": _public_task(task),
        "counts": {
            "tasks": len(tasks),
            "ready": len(ready),
            "active": len(active),
            "done": len(done),
        },
        "ready_tasks": [_public_task(t) for t in ready[:8]],
        "active_tasks": [_public_task(t) for t in active[:8]],
        "last_done_tasks": [_public_task(t) for t in done[-5:]],
        "runtime": {
            "last_worker": runtime.get("last_worker"),
            "last_event": runtime.get("last_event"),
            "last_claimed_task_id": runtime.get("last_claimed_task_id"),
            "pending_journey_verifications": runtime.get("pending_journey_verifications") or [],
            "open_followups": runtime.get("open_followups") or [],
        },
        "paths": {
            "task_pack": pack,
            "handoff": handoff,
        },
        "warnings": warnings,
    }


def _short_task(task: dict[str, Any] | None) -> str:
    if not task:
        return "—"
    return f"{task.get('id')} | {task.get('status')} | {str(task.get('title') or '')[:90]}"


def print_markdown(snapshot: dict[str, Any]) -> None:
    print("# Task context snapshot")
    print()
    print(f"- Canonical root: `{snapshot.get('canonical_root')}`")
    print(f"- Workspace root: `{snapshot.get('workspace_root')}`")
    print(f"- Branch: `{snapshot.get('current_branch')}`")
    print(f"- DAG mode: `{snapshot.get('dag_mode')}`")
    print(f"- Phase order: `{', '.join(snapshot.get('phase_order') or [])}`")
    counts = snapshot.get("counts") or {}
    print(f"- Counts: tasks={counts.get('tasks')} ready={counts.get('ready')} active={counts.get('active')} done={counts.get('done')}")
    print()
    print("## Requested task")
    print(_short_task(snapshot.get("task")))
    if snapshot.get("task"):
        task = snapshot["task"]
        print(f"- Depends on: `{', '.join(task.get('depends_on') or []) or '—'}`")
        print(f"- Journey refs: `{', '.join(task.get('journey_refs') or []) or '—'}`")
        if task.get("task_pack_path"):
            print(f"- Registry task_pack_path: `{task.get('task_pack_path')}`")
    print()
    print("## Paths")
    for key in ("task_pack", "handoff"):
        info = (snapshot.get("paths") or {}).get(key) or {}
        print(
            f"- {key}: workspace={'yes' if info.get('workspace_exists') else 'no'} "
            f"canonical={'yes' if info.get('canonical_exists') else 'no'} `{info.get('relative')}`"
        )
    print()
    print("## Runtime")
    runtime = snapshot.get("runtime") or {}
    print(f"- last_worker: `{runtime.get('last_worker') or '—'}`")
    print(f"- last_event: `{runtime.get('last_event') or '—'}`")
    print(f"- last_claimed_task_id: `{runtime.get('last_claimed_task_id') or '—'}`")
    pending = runtime.get("pending_journey_verifications") or []
    print(f"- pending_journey_verifications: `{', '.join(pending) if pending else 'none'}`")
    followups = runtime.get("open_followups") or []
    print(f"- open_followups: `{len(followups)}`")
    print()
    print("## Ready tasks")
    for task in snapshot.get("ready_tasks") or []:
        print(f"- {_short_task(task)}")
    if not snapshot.get("ready_tasks"):
        print("- none")
    print()
    print("## Active tasks")
    for task in snapshot.get("active_tasks") or []:
        print(f"- {_short_task(task)}")
    if not snapshot.get("active_tasks"):
        print("- none")
    warnings = snapshot.get("warnings") or []
    if warnings:
        print()
        print("## Warnings")
        for warning in warnings:
            print(f"- {warning}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect one DAG task context without mutating state.")
    parser.add_argument("--task", dest="task_id", default=os.environ.get("CLAUDE_ACTIVE_TASK_ID"))
    parser.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    args = parser.parse_args(argv)
    snapshot = build_snapshot(args.task_id)
    if args.json:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print_markdown(snapshot)
    return 0 if snapshot.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
