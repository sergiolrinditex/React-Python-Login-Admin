"""Estado de journeys en runtime-state.json + registry.json.

Garantías que los tests verifican (rules/04-traceability.md §Journey state):

1. `add_pending_journey_verification` es idempotente.
2. `remove_pending_journey_verification` con `mark_verified=True` muta también
   el registry (`verification_status: verified`, `verified_at`).
3. `waive_journey_verification` registra el motivo y marca `waived`.
4. El SubagentStop hook integra todo: parsea trailer del closer y de
   /verify-journey, mutando estado correctamente.
"""
from __future__ import annotations

import io
import sys

import common
import hook_capture_subagent_stop as hook
from _helpers import make_subagent_stop_payload


def _seed_journey(jid: str = "J101", *, task_id: str = "P00-S01-T001", task_status: str = "done") -> None:
    registry = common.load_registry()
    for task in registry.get("tasks", []) or []:
        if task.get("id") == task_id:
            task["status"] = task_status
    registry.setdefault("journeys", []).append({
        "id": jid,
        "title": f"Journey {jid}",
        "milestone": "M1",
        "screens": ["/login", "/home"],
        "task_ids": [task_id],
        "completion_policy": "all_task_ids_done",
        "verification_status": "pending",
        "verified_at": None,
    })
    common.save_registry(registry)



def _write_verified_handoff(task_id: str = "P00-S01-T001") -> None:
    handoff = common.project_root() / "orchestrator-state" / "tasks" / "handoffs" / f"{task_id}.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        f"# Handoff {task_id}\n\n"
        f"## Validator review\n- TASK_ID: {task_id}\n- OUTCOME: approved\n\n"
        f"## Tester run\n- TASK_ID: {task_id}\n- OUTCOME: pass\n\n"
        f"## verify-slice\n"
        f"- TASK_ID: {task_id}\n"
        f"- AGENT: slice-verifier\n"
        f"- MODE: pre-closer\n"
        f"- MCP_BROWSER: chrome-devtools\n"
        f"- VERIFY_OUTCOME: verified\n"
        f"- DATA_CONTRACT_ROWS: VDC-001\n"
        f"- DATA_SETUP: sandbox-user-1 + seeded record A\n"
        f"- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active\n"
        f"- FLOWS_TESTED: login happy path\n"
        f"- EVIDENCE: orchestrator-state/tasks/evidence/{task_id}/verify-*\n",
        encoding="utf-8",
    )

def test_add_pending_is_idempotent(seeded_registry):
    _seed_journey("J101")
    common.add_pending_journey_verification("J101")
    common.add_pending_journey_verification("J101")
    common.add_pending_journey_verification("J101")
    state = common.load_runtime_state()
    assert state["pending_journey_verifications"] == ["J101"]


def test_add_pending_preserves_order_for_multiple(seeded_registry):
    _seed_journey("J101")
    _seed_journey("J102")
    _seed_journey("J103")
    common.add_pending_journey_verification("J103")
    common.add_pending_journey_verification("J101")
    common.add_pending_journey_verification("J102")
    state = common.load_runtime_state()
    assert state["pending_journey_verifications"] == ["J103", "J101", "J102"]


def test_remove_pending_marks_verified_in_registry(seeded_registry):
    _seed_journey("J101")
    common.add_pending_journey_verification("J101")
    common.remove_pending_journey_verification("J101", mark_verified=True)

    state = common.load_runtime_state()
    assert state["pending_journey_verifications"] == []
    assert state["last_journey_verified"] == "J101"

    registry = common.load_registry()
    journey = next(j for j in registry["journeys"] if j["id"] == "J101")
    assert journey["verification_status"] == "verified"
    assert journey["verified_at"]  # ISO timestamp set


def test_remove_pending_without_mark_verified_does_not_touch_registry(seeded_registry):
    _seed_journey("J101")
    common.add_pending_journey_verification("J101")
    common.remove_pending_journey_verification("J101", mark_verified=False)

    registry = common.load_registry()
    journey = next(j for j in registry["journeys"] if j["id"] == "J101")
    assert journey["verification_status"] == "pending"


def test_waive_records_reason(seeded_registry, monkeypatch):
    _seed_journey("J101")
    common.add_pending_journey_verification("J101")
    monkeypatch.setenv("CLAUDE_ALLOW_JOURNEY_WAIVER", "J101")
    common.waive_journey_verification("J101", "human override 2026-04-26")

    state = common.load_runtime_state()
    assert state["pending_journey_verifications"] == []

    registry = common.load_registry()
    journey = next(j for j in registry["journeys"] if j["id"] == "J101")
    assert journey["verification_status"] == "waived"
    assert journey["waiver_reason"] == "human override 2026-04-26"


def test_hook_integration_closer_emits_pending(seeded_registry, monkeypatch):
    """Simula el cierre de la ÚLTIMA slice de un journey: closer emite
    JOURNEY_PENDING_VERIFY → hook lo añade a runtime-state."""
    _seed_journey("J101")
    _write_verified_handoff("P00-S01-T001")

    payload = make_subagent_stop_payload("closer", [
        "TASK_ID: P00-S01-T001",
        "OUTCOME: committed",
        "NEXT_STATUS: done",
        "HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md",
        "REPORT_READY: yes",
        "BASELINE_SYNC_READY: yes",
        "GIT_READY: yes",
        "PUSH_READY: yes",
        "GIT_WORKFLOW_READY: yes",
        "WORKTREES_CLEANED: yes",
        "JOURNEY_PENDING_VERIFY: J101",
    ])
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert hook.main() == 0

    state = common.load_runtime_state()
    assert "J101" in state["pending_journey_verifications"]


def test_hook_integration_verify_journey_clears_pending(seeded_registry, monkeypatch):
    """Simula que /verify-journey emite el outcome verified → el hook lo
    quita de pending y marca el registry."""
    _seed_journey("J101")
    common.add_pending_journey_verification("J101")

    payload = make_subagent_stop_payload("verify-journey", [
        "JOURNEY_ID: J101",
        "JOURNEY_VERIFY_OUTCOME: verified",
    ])
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert hook.main() == 0

    state = common.load_runtime_state()
    assert "J101" not in state["pending_journey_verifications"]
    assert state["last_journey_verified"] == "J101"

    registry = common.load_registry()
    journey = next(j for j in registry["journeys"] if j["id"] == "J101")
    assert journey["verification_status"] == "verified"


def test_hook_integration_issues_found_keeps_pending(seeded_registry, monkeypatch):
    """Si /verify-journey reporta issues_found, el journey sigue en pending
    (debugger debe arreglarlo)."""
    _seed_journey("J101")
    common.add_pending_journey_verification("J101")

    payload = make_subagent_stop_payload("verify-journey", [
        "JOURNEY_ID: J101",
        "JOURNEY_VERIFY_OUTCOME: issues_found",
    ])
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert hook.main() == 0

    state = common.load_runtime_state()
    assert "J101" in state["pending_journey_verifications"]


def test_journeys_closing_at_task_detects_last_task(seeded_registry):
    _seed_journey("J101")
    closing = common.journeys_closing_at_task(common.load_registry(), "P00-S01-T001")
    assert closing == ["J101"]

    not_closing = common.journeys_closing_at_task(common.load_registry(), "P02-S01-T002")
    assert not_closing == []


def test_get_pending_handles_missing_dependency_column_state_without_field(seeded_registry):
    """Una runtime-state missing_dependency_column sin la clave debe devolver []."""
    state = common.load_runtime_state()
    state.pop("pending_journey_verifications", None)
    common.save_runtime_state(state)
    assert common.get_pending_journey_verifications() == []
