"""Race entre validator‖tester paralelos sobre la misma task.

Garantía clave del framework (CLAUDE.md §Parallel-pair status ownership):

- `tester` es dueño de `task.status` (lifecycle).
- `validator` es informacional: su `NEXT_STATUS` se guarda como
  `task.validator_next_status` y NO sobrescribe `task.status`.

Si el orden de llegada de los dos SubagentStop alterase el status final, el
sistema cerraría tasks como `ready_for_close` cuando el tester había fallado, o
viceversa. Estos tests simulan ambos órdenes y verifican que el tester gana
siempre.
"""
from __future__ import annotations

import io
import sys

import common
import hook_capture_subagent_stop as hook
from _helpers import make_subagent_stop_payload


def _run_hook(monkeypatch, agent_type: str, trailer_lines: list[str]) -> int:
    """Inyecta un payload por stdin y ejecuta hook.main() — como hace Claude Code."""
    payload = make_subagent_stop_payload(agent_type, trailer_lines)
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    return hook.main()


def _trailer(task_id: str, outcome: str, next_status: str) -> list[str]:
    return [
        f"TASK_ID: {task_id}",
        f"OUTCOME: {outcome}",
        f"NEXT_STATUS: {next_status}",
        f"HANDOFF: orchestrator-state/tasks/handoffs/{task_id}.md",
    ]


def test_tester_pass_then_validator_approves_status_stays_ready_for_close(
    seeded_registry, monkeypatch
):
    """Caso normal: tester pasa primero, validator aprueba después."""
    tid = "P00-S01-T001"

    # tester gana lifecycle.
    assert _run_hook(monkeypatch, "tester", _trailer(tid, "pass", "ready_for_close")) == 0
    reg = common.load_registry()
    task = common.find_task(reg, tid)
    assert task["status"] == "ready_for_close"
    assert task["last_updated_by"] == "tester"

    # validator llega después → NO debe sobrescribir status.
    assert _run_hook(monkeypatch, "validator", _trailer(tid, "approved", "ready_for_close")) == 0
    reg = common.load_registry()
    task = common.find_task(reg, tid)
    assert task["status"] == "ready_for_close"
    assert task["validator_outcome"] == "approved"
    assert task["validator_next_status"] == "ready_for_close"
    # last_updated_by sí refleja al validator (es metadata, no status)
    assert task["last_updated_by"] == "validator"


def test_validator_first_then_tester_pass_status_owned_by_tester(
    seeded_registry, monkeypatch
):
    """Race invertida: validator emite primero, tester segundo. tester debe ganar."""
    tid = "P00-S01-T001"

    # validator emite primero — pero como es info-only NO mueve status.
    assert _run_hook(monkeypatch, "validator", _trailer(tid, "approved", "ready_for_close")) == 0
    reg = common.load_registry()
    task = common.find_task(reg, tid)
    # Status original ("ready") no se ha movido.
    assert task["status"] == "ready"
    assert task["validator_outcome"] == "approved"

    # tester llega después y empuja a ready_for_close.
    assert _run_hook(monkeypatch, "tester", _trailer(tid, "pass", "ready_for_close")) == 0
    reg = common.load_registry()
    task = common.find_task(reg, tid)
    assert task["status"] == "ready_for_close"
    # validator metadata sigue ahí (no se borra al pasar tester).
    assert task["validator_outcome"] == "approved"


def test_validator_disagrees_with_tester_validator_does_not_override(
    seeded_registry, monkeypatch
):
    """Si validator dice changes_requested pero tester pasa, status sigue
    ready_for_close (el closer mirará el handoff y ahí rechazará)."""
    tid = "P00-S01-T001"

    _run_hook(monkeypatch, "tester", _trailer(tid, "pass", "ready_for_close"))
    _run_hook(monkeypatch, "validator", _trailer(tid, "changes_requested", "needs_debug"))

    reg = common.load_registry()
    task = common.find_task(reg, tid)
    # Status NO retrocede a needs_debug por culpa del validator.
    assert task["status"] == "ready_for_close"
    assert task["validator_outcome"] == "changes_requested"
    assert task["validator_next_status"] == "needs_debug"


def test_official_docs_researcher_is_info_only_too(seeded_registry, monkeypatch):
    """researcher corre paralelo con developer; tampoco debe mover status."""
    tid = "P00-S01-T001"

    _run_hook(monkeypatch, "official-docs-researcher", [
        f"TASK_ID: {tid}",
        "OUTCOME: verified",
        f"HANDOFF: orchestrator-state/tasks/handoffs/{tid}.md",
    ])
    reg = common.load_registry()
    task = common.find_task(reg, tid)
    assert task["status"] == "ready"  # sin cambios
    assert (task.get("official-docs-researcher_outcome") or task.get("official_docs_researcher_outcome")) == "verified"


def test_tester_fail_sets_needs_debug(seeded_registry, monkeypatch):
    """Cuando tester falla, status va a needs_debug (entrada al ciclo del debugger)."""
    tid = "P00-S01-T001"

    _run_hook(monkeypatch, "tester", _trailer(tid, "fail", "needs_debug"))
    reg = common.load_registry()
    task = common.find_task(reg, tid)
    assert task["status"] == "needs_debug"
    assert task["last_outcome"] == "fail"


def test_missing_trailer_is_no_op_not_corruption(seeded_registry, monkeypatch):
    """Si un agente olvida el trailer, el hook no debe romper ni mutar el registry."""
    tid = "P00-S01-T001"
    pre = common.load_registry()
    pre_status = common.find_task(pre, tid)["status"]

    payload = '{"agent_type": "tester", "last_assistant_message": "no trailer here, just narrative"}'
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert hook.main() == 0

    post = common.load_registry()
    assert common.find_task(post, tid)["status"] == pre_status
