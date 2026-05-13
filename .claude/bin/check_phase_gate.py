#!/usr/bin/env python3
"""Validate a phase gate before advancing to the next phase.

The phase gate is the mechanical end-of-phase counterpart to /verify-slice and
/verify-journey. It proves that every task in a phase is truly closed and that
journey-closing slices did not leave pending verification behind.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from check_task_dag import validate_registry_dag
from common import blocking_open_followups, journey_completion_task_ids, load_registry, load_runtime_state, project_root

DONE_JOURNEY_STATES = {"verified", "waived"}


def _phase_ids(registry: dict[str, Any]) -> list[str]:
    return [str(p.get("id")) for p in registry.get("phases", []) if p.get("id")]


def _find_phase(registry: dict[str, Any], phase_id: str | None) -> dict[str, Any] | None:
    if not phase_id:
        return None
    for phase in registry.get("phases", []) or []:
        if phase.get("id") == phase_id:
            return phase
    return None


def _default_phase_id(registry: dict[str, Any], runtime: dict[str, Any]) -> str | None:
    """Return the first phase that is not fully done.

    DAG-only mode has no runtime implicit selector singleton; phase gates should be
    called with an explicit phase_id when possible. This auto-selection is only a
    convenience for interactive maintenance; scripts should pass phase_id explicitly.
    """
    tasks = registry.get("tasks", []) or []
    by_phase = {}
    for task in tasks:
        by_phase.setdefault(str(task.get("phase_id") or ""), []).append(task)
    for phase_id in _phase_ids(registry):
        phase_tasks = by_phase.get(phase_id, [])
        if not phase_tasks or any(str(t.get("status") or "") != "done" for t in phase_tasks):
            return phase_id
    ids = _phase_ids(registry)
    return ids[-1] if ids else None


def _path_exists(root: Path, rel: str | None) -> bool:
    if not rel:
        return False
    return (root / str(rel)).exists()


def _check_git_clean(root: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for optional git cleanliness checks."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, text=True, capture_output=True, timeout=10)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            warnings.append("git check skipped: not inside a git work tree")
            return errors, warnings
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, timeout=10)
        if branch.stdout.strip() != "main":
            errors.append(f"git branch is not main: {branch.stdout.strip() or '(detached)'}")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, timeout=10)
        if status.stdout.strip():
            errors.append("git working tree is not clean")
        upstream = subprocess.run(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"], cwd=root, text=True, capture_output=True, timeout=10)
        if upstream.returncode == 0:
            parts = upstream.stdout.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
                if behind:
                    errors.append(f"main is behind origin/main by {behind} commit(s)")
                if ahead:
                    errors.append(f"main has {ahead} unpushed commit(s)")
        else:
            warnings.append("git upstream check skipped: origin/main not available")
    except Exception as exc:  # pragma: no cover - defensive for unusual git installs
        warnings.append(f"git check skipped: {type(exc).__name__}: {exc}")
    return errors, warnings


def validate_phase_gate(registry: dict[str, Any], runtime: dict[str, Any], *, phase_id: str | None = None,
                        strict_artifacts: bool = True, require_git_clean: bool = False) -> dict[str, Any]:
    root = project_root()
    selected = phase_id or _default_phase_id(registry, runtime)
    phase = _find_phase(registry, selected)
    errors: list[str] = []
    warnings: list[str] = []
    if not phase:
        return {"ok": False, "phase_id": selected, "errors": [f"unknown phase: {selected}"], "warnings": [], "counts": {}}

    dag, dag_warnings, dag_errors = validate_registry_dag(registry)
    warnings.extend(dag_warnings)
    errors.extend(dag_errors)

    phase_task_ids = list(phase.get("task_ids") or [])
    tasks_by_id = {t.get("id"): t for t in registry.get("tasks", []) or []}
    phase_tasks = [tasks_by_id.get(tid) for tid in phase_task_ids if tasks_by_id.get(tid)]
    missing_task_rows = [tid for tid in phase_task_ids if tid not in tasks_by_id]
    for tid in missing_task_rows:
        errors.append(f"phase {selected} references missing task {tid}")

    incomplete: list[dict[str, str]] = []
    for task in phase_tasks:
        if task.get("status") != "done":
            incomplete.append({"task_id": str(task.get("id")), "status": str(task.get("status"))})
    if incomplete:
        errors.append("phase has tasks not done: " + ", ".join(f"{x['task_id']}={x['status']}" for x in incomplete[:12]))

    artifact_errors: list[str] = []
    if strict_artifacts and not incomplete:
        for task in phase_tasks:
            tid = str(task.get("id"))
            if not _path_exists(root, task.get("handoff_path")):
                artifact_errors.append(f"{tid}: missing handoff {task.get('handoff_path') or '(unset)'}")
            report_path = task.get("report_path") or f"orchestrator-state/tasks/reports/{tid}.md"
            if not _path_exists(root, report_path):
                artifact_errors.append(f"{tid}: missing closer report {report_path}")
            evidence_dir = task.get("evidence_dir") or f"orchestrator-state/tasks/evidence/{tid}"
            if not _path_exists(root, evidence_dir):
                artifact_errors.append(f"{tid}: missing evidence dir {evidence_dir}")
    errors.extend(artifact_errors)

    pending = [str(j) for j in (runtime.get("pending_journey_verifications") or []) if j]
    if pending:
        errors.append("pending journey verifications block phase gate: " + ", ".join(pending))

    blocking_followups = blocking_open_followups(runtime)
    if blocking_followups:
        errors.append("blocking follow-up proposals must be promoted or waived: " + ", ".join(str(x.get("id")) for x in blocking_followups))

    phase_task_set = set(phase_task_ids)
    phase_order = [str(p.get("id")) for p in registry.get("phases", []) or [] if p.get("id")]
    phase_idx = {pid: i for i, pid in enumerate(phase_order)}
    task_phase = {str(t.get("id")): str(t.get("phase_id")) for t in registry.get("tasks", []) or [] if t.get("id")}

    closing_journeys: list[dict[str, Any]] = []
    for journey in registry.get("journeys", []) or []:
        task_ids = [str(t) for t in (journey.get("task_ids") or []) if t]
        if not task_ids:
            continue
        terminal_ids = [str(t) for t in (journey.get("terminal_task_ids") or journey_completion_task_ids(registry, journey)) if t]
        if not terminal_ids:
            continue
        # A multi-terminal journey closes at the latest terminal phase, not at
        # whichever terminal happens to appear first in source order.
        terminal_phase_ids = [task_phase.get(tid) for tid in terminal_ids if task_phase.get(tid)]
        if terminal_phase_ids and selected in phase_idx:
            completion_phase_id = max(terminal_phase_ids, key=lambda pid: phase_idx.get(pid, -1))
            if completion_phase_id != selected:
                continue
        elif not any(tid in phase_task_set for tid in terminal_ids):
            continue
        status = str(journey.get("verification_status") or "pending")
        closing_journeys.append({"id": journey.get("id"), "status": status, "terminal_task_ids": terminal_ids})
        if status not in DONE_JOURNEY_STATES:
            errors.append(f"journey {journey.get('id')} closes in {selected} but is not verified/waived: {status}")

    if require_git_clean:
        git_errors, git_warnings = _check_git_clean(root)
        errors.extend(git_errors)
        warnings.extend(git_warnings)

    return {
        "ok": not errors,
        "phase_id": selected,
        "dag_mode": dag.get("mode"),
        "counts": {
            "phase_tasks": len(phase_tasks),
            "incomplete_tasks": len(incomplete),
            "artifact_errors": len(artifact_errors),
            "pending_journeys": len(pending),
            "blocking_followups": len(blocking_followups),
            "closing_journeys": len(closing_journeys),
        },
        "incomplete_tasks": incomplete,
        "closing_journeys": closing_journeys,
        "pending_journey_verifications": pending,
        "blocking_followups": blocking_followups,
        "errors": errors,
        "warnings": warnings,
    }


def print_text(result: dict[str, Any]) -> None:
    status = "OK" if result.get("ok") else "BLOCKED"
    print(f"Phase gate: {status} phase={result.get('phase_id')} mode={result.get('dag_mode')}")
    counts = result.get("counts") or {}
    print(
        "Counts: "
        f"tasks={counts.get('phase_tasks', 0)} "
        f"incomplete={counts.get('incomplete_tasks', 0)} "
        f"pending_journeys={counts.get('pending_journeys', 0)} "
        f"blocking_followups={counts.get('blocking_followups', 0)} "
        f"closing_journeys={counts.get('closing_journeys', 0)} "
        f"artifact_errors={counts.get('artifact_errors', 0)}"
    )
    if result.get("closing_journeys"):
        print("Closing journeys:")
        for journey in result["closing_journeys"]:
            print(f"- {journey.get('id')} status={journey.get('status')} terminal_task_ids={', '.join(journey.get('terminal_task_ids') or [])}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("errors"):
        print("Errors:")
        for error in result["errors"]:
            print(f"- {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an end-of-phase gate.")
    parser.add_argument("phase_id", nargs="?", help="Phase ID, e.g. P03. Defaults to first non-done DAG phase.")
    parser.add_argument("--no-strict-artifacts", action="store_true", help="Do not require handoff/report/evidence files for done tasks.")
    parser.add_argument("--require-git-clean", action="store_true", help="Require main branch clean and synced with origin/main when git is available.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_phase_gate(
        load_registry(),
        load_runtime_state(),
        phase_id=args.phase_id,
        strict_artifacts=not args.no_strict_artifacts,
        require_git_clean=args.require_git_clean,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
