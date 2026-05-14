#!/usr/bin/env python3
"""Write a committed, per-slice lifecycle event for post-merge DAG recovery.

The canonical registry/runtime files are local scheduler state and may be
ignored or skip-worktree in branch-based flows. A close event is small,
per-TASK_ID, conflict-free, and travels in the slice PR. After merge,
`sync_lifecycle_events.py` can replay it to rehydrate local registry state even
if a user reset the canonical root or a worktree carried a stale registry file.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import (
    find_task,
    load_registry,
    now_iso,
    per_slice_tasks_dir,
    project_root,
    workspace_root,
)


def _git_value(args: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True, check=False, timeout=10)
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def build_event(task_id: str, *, next_status: str = "done", outcome: str = "committed") -> dict[str, Any]:
    registry = load_registry()
    task = find_task(registry, task_id)
    if not task:
        raise SystemExit(f"ERROR: TASK_ID not found in canonical registry: {task_id}")
    workspace = workspace_root()
    canonical = project_root()
    rel_base = Path("orchestrator-state/tasks")
    event = {
        "schema": "orquestador.lifecycle-event.v1",
        "task_id": task_id,
        "agent_type": "closer",
        "outcome": outcome,
        "next_status": next_status,
        "created_at": now_iso(),
        "source": "git-add-slice",
        "previous_status": task.get("status"),
        "previous_last_updated_by": task.get("last_updated_by"),
        "phase_id": task.get("phase_id"),
        "title": task.get("title"),
        "paths": {
            "handoff": (rel_base / "handoffs" / f"{task_id}.md").as_posix(),
            "evidence": (rel_base / "evidence" / task_id).as_posix(),
            "report": (rel_base / "reports" / f"{task_id}.md").as_posix(),
            "task_pack": (rel_base / "task-packs" / f"{task_id}.md").as_posix(),
        },
        "git": {
            "branch": _git_value(["branch", "--show-current"], workspace),
            "head": _git_value(["rev-parse", "--verify", "HEAD"], workspace),
        },
        "root_split": {
            "canonical_root_hint": _rel(canonical, canonical.parent),
            "workspace_root_hint": _rel(workspace, workspace.parent),
        },
    }
    return event


def write_event(task_id: str, *, next_status: str = "done", outcome: str = "committed") -> Path:
    events_dir = per_slice_tasks_dir() / "lifecycle-events"
    events_dir.mkdir(parents=True, exist_ok=True)
    path = events_dir / f"{task_id}.json"
    event = build_event(task_id, next_status=next_status, outcome=outcome)
    path.write_text(json.dumps(event, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a per-TASK_ID lifecycle close event into the active checkout.")
    parser.add_argument("task_id")
    parser.add_argument("--next-status", default="done", choices=["done"])
    parser.add_argument("--outcome", default="committed", choices=["committed"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    path = write_event(args.task_id, next_status=args.next_status, outcome=args.outcome)
    if args.json:
        print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False))
    else:
        print(f"LIFECYCLE_EVENT_READY: yes")
        print(f"LIFECYCLE_EVENT: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
