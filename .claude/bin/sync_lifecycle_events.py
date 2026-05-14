#!/usr/bin/env python3
"""Replay committed per-slice lifecycle events into local DAG runtime state.

Why this exists:
- In branch/PR workflows the closer commits code + slice artifacts from a task
  worktree, but the SubagentStop hook mutates the canonical scheduler registry
  after the commit/PR transport.
- Therefore `registry.json` must be treated as local runtime state. A hard reset
  or stale worktree must not be the source of truth for whether a merged slice is
  done.
- `orchestrator-state/tasks/lifecycle-events/<TASK_ID>.json` is the committed,
  conflict-free signal. Replaying these files is idempotent and safe.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import (
    append_jsonl,
    file_lock,
    find_task,
    ledger_path,
    load_registry,
    load_runtime_state,
    log_hook_error,
    log_hook_info,
    now_iso,
    promote_ready_tasks,
    registry_path,
    runtime_state_path,
    save_registry,
    save_runtime_state,
    state_dir,
    sync_runtime_state_from_registry,
)

RUNTIME_SKIP_PATHS = [
    "orchestrator-state/tasks/registry.json",
    "orchestrator-state/tasks/runtime-state.json",
    "orchestrator-state/tasks/ledger.jsonl",
    "orchestrator-state/tasks/bash-ledger.jsonl",
    "orchestrator-state/memory/PROGRESS.md",
    "orchestrator-state/memory/task-dag.json",
    "orchestrator-state/memory/task-dag.md",
    "orchestrator-state/memory/execution-graph.json",
    "orchestrator-state/memory/stack-profile.json",
    "orchestrator-state/memory/source-manifest.json",
    "orchestrator-state/hook-errors.log",
    "orchestrator-state/hook-info.log",
]


def _repo_root() -> Path:
    return state_dir().parent


def _git(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(_repo_root()), text=True, capture_output=True, check=check, timeout=20)


def protect_runtime_paths_from_git() -> list[str]:
    """Mark already-tracked local runtime files as skip-worktree.

    This is a migration guard for repos that used older versions where
    registry/runtime were tracked. It does not hardcode project state and it is
    local-only; it simply prevents local scheduler mutations from making `main`
    dirty or blocking a PR fast-forward.
    """
    protected: list[str] = []
    try:
        inside = _git("rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0:
            return protected
        for rel in RUNTIME_SKIP_PATHS:
            tracked = _git("ls-files", "--error-unmatch", rel)
            if tracked.returncode == 0:
                _git("update-index", "--skip-worktree", "--", rel)
                protected.append(rel)
    except Exception as exc:
        log_hook_error("sync_lifecycle_events.protect_runtime_paths", exc)
    return protected


def _event_paths() -> list[Path]:
    events_dir = state_dir() / "tasks" / "lifecycle-events"
    if not events_dir.is_dir():
        return []
    return sorted(events_dir.glob("*.json"))


def _load_event(path: Path) -> dict[str, Any] | None:
    try:
        event = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log_hook_error("sync_lifecycle_events.load_event", exc)
        return None
    if not isinstance(event, dict):
        return None
    if event.get("schema") != "orquestador.lifecycle-event.v1":
        return None
    task_id = str(event.get("task_id") or "").strip()
    if not task_id:
        return None
    if str(event.get("agent_type") or "") != "closer":
        return None
    if str(event.get("outcome") or "") != "committed":
        return None
    if str(event.get("next_status") or "") != "done":
        return None
    return event


def apply_events(*, dry_run: bool = False) -> dict[str, Any]:
    protected = protect_runtime_paths_from_git()
    paths = _event_paths()
    events = [ev for p in paths if (ev := _load_event(p))]
    applied: list[str] = []
    already: list[str] = []
    missing: list[str] = []
    changed_tasks: list[dict[str, Any]] = []

    if not events:
        return {"ok": True, "events": 0, "applied": [], "already": [], "missing": [], "protected": protected}

    with file_lock(registry_path()):
        registry = load_registry()
        for event in events:
            task_id = str(event["task_id"])
            task = find_task(registry, task_id)
            if not task:
                missing.append(task_id)
                continue
            if task.get("status") == "done" and task.get("last_updated_by") == "closer":
                already.append(task_id)
                continue
            before = {"status": task.get("status"), "last_updated_by": task.get("last_updated_by")}
            paths_obj = event.get("paths") if isinstance(event.get("paths"), dict) else {}
            if not dry_run:
                task["status"] = "done"
                task["last_outcome"] = "committed"
                task["last_updated_by"] = "closer"
                task["last_stop_at"] = event.get("created_at") or now_iso()
                if paths_obj.get("handoff"):
                    task["handoff_path"] = str(paths_obj["handoff"])
                if paths_obj.get("evidence"):
                    task["evidence_dir"] = str(paths_obj["evidence"])
                if paths_obj.get("report"):
                    task["report_path"] = str(paths_obj["report"])
            applied.append(task_id)
            changed_tasks.append({"task_id": task_id, "before": before, "after": {"status": "done", "last_updated_by": "closer"}})
        if not dry_run and applied:
            save_registry(promote_ready_tasks(registry))
            sync_runtime_state_from_registry(load_registry())
            with file_lock(runtime_state_path()):
                runtime = load_runtime_state()
                runtime["last_event"] = "lifecycle_events_synced"
                runtime["last_stop_at"] = now_iso()
                save_runtime_state(runtime)
            try:
                append_jsonl(ledger_path(), {"ts": now_iso(), "event": "lifecycle_events_synced", "applied": applied})
            except Exception:
                pass
            log_hook_info("sync_lifecycle_events", f"applied close events: {applied}")
    return {
        "ok": True,
        "events": len(events),
        "applied": applied,
        "already": already,
        "missing": missing,
        "changed_tasks": changed_tasks,
        "protected": protected,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay committed close lifecycle events into local registry/runtime state.")
    parser.add_argument("--apply", action="store_true", help="Persist registry/runtime changes. Without it, dry-run.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = apply_events(dry_run=not args.apply)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"LIFECYCLE_EVENTS_READY: yes")
        print(f"LIFECYCLE_EVENTS_TOTAL: {result.get('events', 0)}")
        print(f"LIFECYCLE_EVENTS_APPLIED: {','.join(result.get('applied') or []) or 'none'}")
        if result.get("missing"):
            print(f"LIFECYCLE_EVENTS_MISSING_TASKS: {','.join(result['missing'])}")
        if result.get("protected"):
            print(f"RUNTIME_GIT_PROTECTED: {len(result['protected'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
