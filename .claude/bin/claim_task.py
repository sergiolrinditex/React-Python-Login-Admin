#!/usr/bin/env python3
"""Atomically claim a ready DAG task for one worker terminal.

Production is DAG-only: each worker terminal claims exactly one TASK_ID and pins
hooks with CLAUDE_ACTIVE_TASK_ID plus CLAUDE_TASK_PACK. There is no implicit task/phase selector.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from common import (
    file_lock,
    find_phase,
    find_task,
    active_conflict_blockers,
    blocking_open_followups,
    pending_journey_blockers_for_task,
    load_registry,
    load_runtime_state,
    now_iso,
    promote_ready_tasks,
    registry_path,
    runtime_state_path,
    save_registry,
    save_runtime_state,
    task_is_ready,
    task_pack_path,
    write_text,
    workspace_relpath,
    project_root,
)
from stack_profile import load_stack_profile

# `blocked` is a scheduler conflict blocker, but not claim-resumable.
# promote_ready_tasks() converts dependency-unblocked tasks to `ready`; otherwise claim must deny.
ACTIVE_STATUSES = {"in_progress", "validator_tester_pending", "review_pending", "test_pending", "qa_pending", "needs_debug", "ready_for_close", "verified_pending_close"}


def _ensure_minimal_task_pack(task: dict[str, Any]) -> str:
    """Create a per-task pack placeholder for DAG workers.

    The planner overwrites this file with the full source-pack extract before the
    developer starts. The placeholder makes the task-pack path concrete and
    prevents worker terminals from depending on any implicit selector.
    """
    task_id = str(task.get("id") or "").strip()
    path = task_pack_path(task_id)
    if not path.exists():
        acceptance = task.get("acceptance") or []
        commands = task.get("verification_commands") or []
        deps = task.get("depends_on") or []
        conflict_groups = task.get("conflict_groups") or []
        write_set = task.get("write_set") or []
        journey_refs = task.get("journey_refs") or []
        tables = task.get("tables") or []
        lines = [
            f"# Task Pack: {task_id} — {task.get('title') or ''}",
            "",
            "> Minimal pack created by claim_task.py. The planner must enrich this file with",
            "> source-of-truth extracts before developer/tester/validator run.",
            "",
            "## Tarea activa (del registry)",
            "",
            f"- TASK_ID: {task_id}",
            f"- Phase: {task.get('phase_id') or '—'}",
            f"- Step: {task.get('step_id') or '—'}",
            f"- Status at claim: {task.get('status') or '—'}",
            f"- Kind: {task.get('kind') or 'unspecified'}",
            f"- Target: {task.get('target') or '—'}",
            f"- Product increment: {task.get('product_increment') or '—'}",
            f"- Build state: {task.get('build_state') or '—'}",
            f"- Risk level: {task.get('risk_level') or 'medium'}",
            f"- Verify mode: {task.get('verify_mode') or 'human'}",
            f"- Depends on: {', '.join(deps) if deps else '—'}",
            f"- Conflict groups: {', '.join(conflict_groups) if conflict_groups else '—'}",
            f"- Write set: {', '.join(write_set) if write_set else '—'}",
            "",
            "",
            "## Stack profile y UX contract",
            "",
            f"- Stack profile source: {load_stack_profile(project_root()).get('_source', 'default')}",
            f"- Frontend root: {load_stack_profile(project_root()).get('frontend', {}).get('module_root', '—')}",
            f"- Backend root: {load_stack_profile(project_root()).get('backend', {}).get('module_root', '—')}",
            f"- DB engine: {load_stack_profile(project_root()).get('db', {}).get('engine', '—')}",
            f"- Design-token enforcer: {load_stack_profile(project_root()).get('design_tokens_enforcer', '—')}",
            "- UX contract: docs/source-of-truth/UX_CONTRACT.md if present",
            "",
            "## Front → Back → DB wiring (del registry)",
            "",
            f"- Journey refs: {', '.join(journey_refs) if journey_refs else '—'}",
            f"- Pantalla/Ruta: {task.get('route') or '—'}",
            f"- Endpoint: {task.get('endpoint') or '—'}",
            f"- Tablas DB: {', '.join(tables) if tables else '—'}",
            f"- Origen instrucciones: {task.get('origin_instr') or '—'}",
            f"- Origen technical guide: {task.get('origin_techguide') or '—'}",
            "",
            "## Acceptance mínimo",
            "",
        ]
        lines.extend(f"- {item}" for item in acceptance)
        if not acceptance:
            lines.append("- TODO: planner must expand acceptance from source-of-truth docs.")
        lines.extend(["", "## Comandos de verificación", ""])
        lines.extend(f"- `{cmd}`" for cmd in commands)
        if not commands:
            lines.append("- TODO: planner must add verification commands from source-of-truth docs.")
        lines.extend(["", "## Guardrail", "", "If this file still contains this minimal-pack notice when developer starts, STOP and rerun planner.", ""])
        write_text(path, "\n".join(lines))
    return workspace_relpath(path)


def _identity() -> str:
    for key in ("USER", "LOGNAME", "USERNAME"):
        if os.environ.get(key):
            return str(os.environ[key])
    return "unknown"


def claim_task(task_id: str, *, force: bool = False) -> tuple[bool, dict[str, Any]]:
    if not task_id:
        return False, {"error": "missing TASK_ID"}

    with file_lock(registry_path()):
        registry = promote_ready_tasks(load_registry())
        blocking_followups = blocking_open_followups(load_runtime_state())
        if blocking_followups:
            return False, {
                "error": "blocking follow-up proposal(s) must be promoted or waived before claiming new DAG work",
                "blocking_followups": blocking_followups,
            }
        task = find_task(registry, task_id)
        if not task:
            return False, {"error": f"TASK_ID not found in registry: {task_id}"}
        phase = find_phase(registry, task.get("phase_id"))
        if task.get("status") == "done":
            return False, {"error": f"TASK_ID already done: {task_id}", "task": task}
        if task.get("status") == "claimed" and not force:
            return False, {"error": f"TASK_ID already claimed: {task_id}", "task": task}
        if task.get("status") in ACTIVE_STATUSES:
            if not task.get("task_pack_path"):
                task["task_pack_path"] = _ensure_minimal_task_pack(task)
                save_registry(promote_ready_tasks(registry))
            return True, {"status": "already_active", "task": task, "phase": phase}
        if not task_is_ready(registry, task):
            done_ids = {t["id"] for t in registry.get("tasks", []) if t.get("status") == "done"}
            missing = [dep for dep in task.get("depends_on", []) if dep not in done_ids]
            return False, {"error": f"TASK_ID dependencies are not done: {task_id}", "missing_dependencies": missing, "task": task}

        runtime = load_runtime_state()
        journey_blockers = pending_journey_blockers_for_task(task, runtime)
        if journey_blockers and not force:
            return False, {
                "error": f"TASK_ID is deferred by pending journey verification(s): {task_id}",
                "pending_journey_blockers": journey_blockers,
                "hint": "Run /verify-journey <JID>. DAG-only journey gate defers only tasks that reference the pending journey.",
                "task": task,
            }

        conflict_blockers = active_conflict_blockers(registry, task)
        if conflict_blockers and not force:
            return False, {
                "error": f"TASK_ID conflicts with DAG task(s): {task_id}",
                "conflict_blockers": conflict_blockers,
                "task": task,
            }

        task["status"] = "claimed"
        task["claimed_at"] = now_iso()
        task["claimed_by"] = _identity()
        task["claim_terminal_task_env"] = os.environ.get("CLAUDE_ACTIVE_TASK_ID") or os.environ.get("CLAUDE_TASK_ID")
        task["task_pack_path"] = _ensure_minimal_task_pack(task)
        save_registry(promote_ready_tasks(registry))

        # No global DAG task/phase selector file is written. Worker terminals are
        # scoped exclusively by CLAUDE_ACTIVE_TASK_ID + CLAUDE_TASK_PACK.
        with file_lock(runtime_state_path()):
            runtime = load_runtime_state()
            runtime["generated_at"] = now_iso()
            runtime["last_event"] = "task_claimed"
            runtime["last_claimed_task_id"] = task.get("id")
            runtime["last_claimed_phase_id"] = task.get("phase_id")
            save_runtime_state(runtime)
        return True, {"status": "claimed", "task": task, "phase": phase}


def main() -> int:
    parser = argparse.ArgumentParser(description="Claim a ready TASK_ID for this DAG worker terminal.")
    parser.add_argument("task_id", help="TASK_ID to claim, e.g. P02-S03-T001")
    parser.add_argument("--force", action="store_true", help="Reclaim a task already marked claimed")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    ok, result = claim_task(args.task_id, force=args.force)
    result = {"ok": ok, **result}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if ok:
            task = result.get("task") or {}
            print(f"CLAIM_OK {task.get('id')} status={result.get('status')} phase={task.get('phase_id')}")
            pack = task.get("task_pack_path") or f"orchestrator-state/tasks/task-packs/{task.get('id')}.md"
            print(f"Run this terminal with: export CLAUDE_ACTIVE_TASK_ID={task.get('id')} CLAUDE_TASK_PACK={pack}")
        else:
            print(f"CLAIM_DENIED {result.get('error')}")
            if result.get("missing_dependencies"):
                print("Missing dependencies: " + ", ".join(result["missing_dependencies"]))
            if result.get("blocking_followups"):
                for item in result["blocking_followups"]:
                    print(f"Blocking follow-up: {item.get('id')} severity={item.get('severity')} origin={item.get('origin_task_id')} title={item.get('title')}")
            if result.get("pending_journey_blockers"):
                print("Pending journey blockers: " + ", ".join(result["pending_journey_blockers"]))
                print(str(result.get("hint") or ""))
            if result.get("conflict_blockers"):
                for blocker in result["conflict_blockers"]:
                    print(f"Conflict blocker: {blocker.get('task_id')} status={blocker.get('status')} reasons={'; '.join(blocker.get('reasons') or [])}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
