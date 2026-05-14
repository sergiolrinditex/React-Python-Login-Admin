#!/usr/bin/env python3
"""Print the current DAG execution wave and copy/paste worker commands.

This is the mechanical counterpart of `/next-wave`: it does not claim tasks,
spawn agents, or mutate registry.json. It reads the generated registry/task DAG,
applies the same readiness rule used by `claim_task.py`, and prints the tasks
that can safely run in parallel in the earliest incomplete phase.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from typing import Any

from check_task_dag import validate_registry_dag
from stack_profile import load_stack_profile
from common import (
    SCHEDULER_ACTIVE_STATUSES,
    project_root,
    load_registry,
    load_runtime_state,
    blocking_open_followups,
    pending_journey_blockers_for_task,
    promote_ready_tasks,
    task_conflict_reasons,
    task_is_ready,
)


def _phase_tasks(registry: dict[str, Any], phase_id: str) -> list[dict[str, Any]]:
    return [t for t in registry.get("tasks", []) if t.get("phase_id") == phase_id]


def _earliest_incomplete_phase(registry: dict[str, Any]) -> str | None:
    for phase_id in registry.get("phase_order", []):
        tasks = _phase_tasks(registry, phase_id)
        if tasks and not all(t.get("status") == "done" for t in tasks):
            return phase_id
    return None


def _active_conflict_reason(task: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for other in registry.get("tasks", []) or []:
        if other.get("id") == task.get("id"):
            continue
        status = other.get("status")
        is_blocker = status in SCHEDULER_ACTIVE_STATUSES or (status == "blocked" and task_is_ready(registry, other))
        if is_blocker:
            for reason in task_conflict_reasons(task, other):
                item = f"active {other.get('id')}: {reason}"
                if item not in reasons:
                    reasons.append(item)
    return reasons


def _selected_conflict_reason(task: dict[str, Any], selected: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for other in selected:
        for reason in task_conflict_reasons(task, other):
            item = f"selected {other.get('id')}: {reason}"
            if item not in reasons:
                reasons.append(item)
    return reasons


def compute_wave(registry: dict[str, Any], *, phase_id: str | None = None, limit: int | None = None) -> dict[str, Any]:
    # Work on a copy; /next-wave must not mutate registry state.
    registry = promote_ready_tasks(copy.deepcopy(registry))
    runtime = load_runtime_state()
    pending = [str(j).strip() for j in (runtime.get("pending_journey_verifications") or []) if str(j).strip()]
    blocking_followups = blocking_open_followups(runtime)
    dag, warnings, errors = validate_registry_dag(registry)
    errors = list(errors or [])
    if dag.get("mode") != "explicit_dag":
        errors.append("production DAG-only requires task_dag.mode=explicit_dag; fix Coverage Registry Depends on and rerun bootstrap")
    selected_phase = phase_id or _earliest_incomplete_phase(registry)
    selected: list[dict[str, Any]] = []
    deferred_conflicts: list[dict[str, Any]] = []
    deferred_journey_gate: list[dict[str, Any]] = []
    ready_total = 0

    if selected_phase and not blocking_followups and not errors:
        for task in _phase_tasks(registry, selected_phase):
            status = task.get("status")
            if status == "done" or status in SCHEDULER_ACTIVE_STATUSES or (status == "blocked" and task_is_ready(registry, task)):
                continue
            if status == "ready" and task_is_ready(registry, task):
                ready_total += 1
                journey_blockers = pending_journey_blockers_for_task(task, runtime)
                if journey_blockers:
                    enriched = dict(task)
                    enriched["journey_gate_blockers"] = journey_blockers
                    enriched["journey_gate_reason"] = "pending journeys: " + ", ".join(journey_blockers)
                    deferred_journey_gate.append(enriched)
                    continue
                active_reasons = _active_conflict_reason(task, registry)
                selected_reasons = _selected_conflict_reason(task, selected)
                reasons = active_reasons + selected_reasons
                enriched = dict(task)
                if reasons:
                    enriched["conflict_risk"] = "alto"
                    enriched["conflict_reason"] = "; ".join(reasons)
                    deferred_conflicts.append(enriched)
                    continue
                enriched["conflict_risk"] = "bajo"
                enriched["conflict_reason"] = "—"
                selected.append(enriched)
                if limit and len(selected) >= limit:
                    break

    return {
        "ok": not errors and not blocking_followups,
        "dag_mode": dag.get("mode"),
        "phase": selected_phase,
        "ready_total": ready_total,
        "ready_count": len(selected),
        "recommended_parallel_terminals": len(selected),
        "ready": selected,
        "deferred_due_conflicts": deferred_conflicts,
        "deferred_due_journey_gate": deferred_journey_gate,
        "warnings": warnings,
        "errors": errors,
        "pending_journey_verifications": pending,
        "blocking_followups": blocking_followups,
    }


def _git_workflow() -> str:
    raw = str(load_stack_profile(project_root()).get("git_workflow") or "push-to-main")
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    if safe in {"direct-main", "direct-main-push", "push-main"}:
        return "push-to-main"
    if safe == "gitflow":
        return "git-flow"
    return safe or "push-to-main"


def _terminal_command(task_id: str) -> str:
    # Do not pre-claim here. `/next-slice <TASK_ID>` performs the atomic claim
    # after the human approves the plan, avoiding a double-claim denial. The
    # task-pack export gives every downstream agent a per-node path; DAG-only
    # has no implicit global selector. For pr-flow projects the terminal is moved
    # into a per-TASK_ID worktree/branch before Claude Code starts, so validator,
    # tester, debugger, verify-slice and closer all look at the same checkout.
    pack = f"orchestrator-state/tasks/task-packs/{task_id}.md"
    claude_cmd = f'claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice {task_id}"'
    workflow = _git_workflow()
    if workflow == "push-to-main":
        return (
            "unset CLAUDE_ACTIVE_TASK_ID CLAUDE_TASK_PACK CLAUDE_WORKTREE_ROOT CLAUDE_ORCHESTRATOR_ROOT && "
            f"export CLAUDE_ACTIVE_TASK_ID={task_id} "
            f"CLAUDE_TASK_PACK={pack} && "
            f"echo 'Ahora ejecuta en Claude Code: {claude_cmd}'"
        )
    return (
        'unset CLAUDE_ACTIVE_TASK_ID CLAUDE_TASK_PACK CLAUDE_WORKTREE_ROOT CLAUDE_ORCHESTRATOR_ROOT COMPOSE_PROJECT_NAME && '
        'BOOTSTRAP_ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)}" && '
        'ROOT="$(bash "$BOOTSTRAP_ROOT/scripts/ensure-task-worktree.sh" --print-root)" && '
        f'WT="$(bash "$ROOT/scripts/ensure-task-worktree.sh" {task_id})" && '
        'cd "$WT" && '
        f'PACK="$WT/{pack}" && '
        f'if [ ! -f "$PACK" ]; then PACK="$ROOT/{pack}"; fi && '
        # COMPOSE_PROJECT_NAME: pin docker-compose project to canonical root
        # so parallel terminals SHARE the same stack (postgres, redis, ...)
        # instead of each worktree spinning up its own (port collisions).
        # Honour any value the user pre-exported; otherwise derive from
        # the canonical root basename.
        'COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$ROOT" | tr "[:upper:]" "[:lower:]" | tr -c "a-z0-9-" "-")}" && '
        f'export COMPOSE_PROJECT_NAME CLAUDE_ORCHESTRATOR_ROOT="$ROOT" CLAUDE_WORKTREE_ROOT="$WT" '
        f'CLAUDE_ACTIVE_TASK_ID={task_id} CLAUDE_TASK_PACK="$PACK" && '
        f"echo 'Ahora ejecuta en Claude Code: {claude_cmd}'"
    )


def _md_cell(value: object) -> str:
    return str(value if value is not None else "").replace("\n", "<br>").replace("|", "\\|")


def print_markdown(result: dict[str, Any]) -> None:
    print("# DAG wave propuesta")
    print()
    print("> **Antes de reclamar una task en este terminal**, limpia las 5")
    print("> variables de scope para no mezclar contextos entre slices ni")
    print("> arrancar un docker-stack paralelo:")
    print(">")
    print("> ```bash")
    print("> unset CLAUDE_ACTIVE_TASK_ID")
    print("> unset CLAUDE_TASK_PACK")
    print("> unset CLAUDE_WORKTREE_ROOT")
    print("> unset CLAUDE_ORCHESTRATOR_ROOT")
    print("> unset COMPOSE_PROJECT_NAME  # se re-deriva del basename del repo")
    print("> ```")
    print()
    print(f"- DAG mode: `{result.get('dag_mode')}`")
    print(f"- Phase: `{result.get('phase') or '—'}`")
    print(f"- Ready nodes total: {result.get('ready_total', result.get('ready_count'))}")
    print(f"- Ready nodes seguros: {result.get('ready_count')}")
    print(f"- Recomendación de paralelo: {result.get('recommended_parallel_terminals')} terminales")
    pending = result.get("pending_journey_verifications") or []
    if pending:
        print()
        print("## Journeys pendientes")
        print("- DAG-only: solo se difieren las tasks que referencian esos journeys; las ramas independientes pueden continuar.")
        for jid in pending:
            print(f"- `{jid}` pendiente: `/verify-journey {jid}`")
    blocking_followups = result.get("blocking_followups") or []
    if blocking_followups:
        print()
        print("## Bloqueado por follow-ups sin promover")
        print("Promueve o descarta estos hallazgos antes de abrir una nueva wave:")
        for item in blocking_followups:
            print(f"- `{item.get('id')}` severity={item.get('severity')} origin={item.get('origin_task_id')} — {item.get('title')}")
        print()
        print("Comandos:")
        print("```bash")
        print("./scripts/register-followup-task.sh list")
        print('claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"')
        print("# o, con decisión humana explícita:")
        print("./scripts/register-followup-task.sh waive <FOLLOWUP_ID> --reason '<motivo>'")
        print("```")
    if result.get("warnings"):
        print()
        print("## Warnings")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result.get("errors"):
        print()
        print("## Errors")
        for error in result["errors"]:
            print(f"- {error}")
    ready = result.get("ready") or []
    if not ready:
        print()
        print("No hay nodos ready ejecutables en esta phase.")
    else:
        print()
        print("| TASK_ID | Título | Depends on | Conflict groups | Write set | Comando terminal |")
        print("|---|---|---|---|---|---|")
        for task in ready:
            tid = task.get("id")
            title = _md_cell(task.get("title") or "")
            deps = _md_cell(", ".join(task.get("depends_on") or []) or "—")
            groups = _md_cell(", ".join(task.get("conflict_groups") or []) or "—")
            writes = _md_cell(", ".join(task.get("write_set") or []) or "—")
            cmd = _md_cell(_terminal_command(tid))
            print(f"| `{tid}` | {title} | {deps} | {groups} | {writes} | `{cmd}` |")
        print()
        print("## Copia y pega por terminal")
        for idx, task in enumerate(ready, start=1):
            tid = task.get("id")
            print()
            print(f"### Terminal {idx} — {tid}")
            print("```bash")
            print(_terminal_command(tid))
            print("```")
            print(
                "Después, en ese terminal worker: "
                f"`claude --agent main-orchestrator --permission-mode bypassPermissions \"/next-slice {tid}\"`"
            )

    deferred_journey = result.get("deferred_due_journey_gate") or []
    if deferred_journey:
        print()
        print("## Diferidos por journey gate")
        print()
        print("Estos nodos están ready por dependencias, pero referencian journeys pendientes de verificación:")
        print()
        print("| TASK_ID | Título | Journey pendiente |")
        print("|---|---|---|")
        for task in deferred_journey:
            tid = task.get("id")
            title = str(task.get("title") or "").replace("|", "\\|")
            reason = str(task.get("journey_gate_reason") or "").replace("|", "\\|")
            print(f"| `{tid}` | {title} | {reason} |")

    deferred = result.get("deferred_due_conflicts") or []
    if deferred:
        print()
        print("## Serializados por conflicto")
        print()
        print("Estos nodos están ready por dependencias, pero NO se proponen en la misma wave para evitar corrupción de ficheros/estado:")
        print()
        print("| TASK_ID | Título | Motivo |")
        print("|---|---|---|")
        for task in deferred:
            tid = task.get("id")
            title = str(task.get("title") or "").replace("|", "\\|")
            reason = str(task.get("conflict_reason") or "").replace("|", "\\|")
            print(f"| `{tid}` | {title} | {reason} |")


def main() -> int:
    parser = argparse.ArgumentParser(description="List current DAG wave with copy/paste worker commands.")
    parser.add_argument("--phase", help="Phase ID to inspect, e.g. P03. Defaults to earliest incomplete phase.")
    parser.add_argument("--limit", type=int, help="Max safe ready tasks to print.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = compute_wave(load_registry(), phase_id=args.phase, limit=args.limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_markdown(result)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
