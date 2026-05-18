from __future__ import annotations

import json
import sys
from io import StringIO
from unittest import mock


def _seed_registry(common, *, task_ids=None, statuses=None, journey_task_ids=None, adjacency=None, journey_status="pending"):
    task_ids = task_ids or ["P00-S01-T001", "P00-S01-T002", "P00-S01-T003"]
    statuses = statuses or {
        "P00-S01-T001": "done",
        "P00-S01-T002": "ready_for_close",
        "P00-S01-T003": "done",
    }
    tasks = []
    for tid in task_ids:
        tasks.append({
            "id": tid,
            "title": tid,
            "phase_id": tid.split("-", 1)[0],
            "step_id": "-".join(tid.split("-")[:2]),
            "status": statuses.get(tid, "blocked"),
            "depends_on": [],
        })
    registry = {
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "Phase 0", "status": "active", "task_ids": task_ids}],
        "tasks": tasks,
        "journeys": [{
            "id": "J1",
            "title": "unordered journey",
            # Deliberately not topological: this used to break code that used task_ids[-1].
            "task_ids": journey_task_ids or ["P00-S01-T003", "P00-S01-T001", "P00-S01-T002"],
            "verification_status": journey_status,
        }],
        "task_dag": {
            "mode": "explicit_dag",
            "nodes": task_ids,
            "adjacency_list": adjacency or {
                "P00-S01-T001": ["P00-S01-T002"],
                "P00-S01-T003": ["P00-S01-T002"],
                "P00-S01-T002": [],
            },
        },
    }
    common.save_registry(registry)
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "next_ready_phase_id": "P00",
        "last_claimed_task_id": "P00-S01-T002",
        "last_worker": None,
        "last_event": None,
        "pending_journey_verifications": [],
        "last_journey_verified": None,
        "spawn_budget": 20,
        "spawns_in_current_slice": {},
    })
    return registry


def _fire_hook(agent_type: str, message: str) -> int:
    payload = json.dumps({"agent_type": agent_type, "last_assistant_message": message})
    with mock.patch.object(sys, "stdin", StringIO(payload)):
        import hook_capture_subagent_stop as hook
        return hook.main()


def _closer_trailer(task_id: str, *, extra: list[str] | None = None) -> str:
    lines = [
        "CLAUDE_TRAILER:",
        f"TASK_ID: {task_id}",
        "OUTCOME: committed",
        "NEXT_STATUS: done",
        f"REPORT: orchestrator-state/tasks/reports/{task_id}.md",
        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
        "GIT_READY: yes",
        "PUSH_READY: yes",
        "GIT_WORKFLOW_READY: yes",
        "WORKTREES_CLEANED: yes",
    ]
    if extra:
        lines.extend(extra)
    return "\n".join(lines) + "\n"



def _write_verified_handoff(common, task_id: str) -> None:
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

def test_journey_closure_is_status_based_not_source_order(tmp_project):
    import common

    registry = _seed_registry(common)

    assert common.journey_completion_task_ids(registry, registry["journeys"][0]) == ["P00-S01-T002"]
    assert common.journeys_closing_at_task(registry, "P00-S01-T003") == []
    assert common.journeys_closing_at_task(registry, "P00-S01-T002") == ["J1"]


def test_list_journey_closures_simulates_current_task_as_done(tmp_project):
    import common
    import list_journey_closures

    registry = _seed_registry(common, statuses={
        "P00-S01-T001": "done",
        "P00-S01-T002": "ready_for_close",
        "P00-S01-T003": "done",
    })

    result = list_journey_closures.classify_journey_closures(registry, "P00-S01-T002")

    assert result["ok"]
    assert [j["id"] for j in result["closing_journeys"]] == ["J1"]
    assert result["closing_journeys"][0]["terminal_task_ids"] == ["P00-S01-T002"]


def test_closer_inline_journey_verification_marks_registry_verified(tmp_project):
    import common

    _seed_registry(common)
    _write_verified_handoff(common, "P00-S01-T002")

    rc = _fire_hook("closer", _closer_trailer(
        "P00-S01-T002",
        extra=["JOURNEY_VERIFIED_INLINE: J1"],
    ))

    assert rc == 0
    registry = common.load_registry()
    journey = common.find_journey(registry, "J1")
    task = common.find_task(registry, "P00-S01-T002")
    runtime = common.load_runtime_state()
    assert task["status"] == "done"
    assert journey["verification_status"] == "verified"
    assert runtime["pending_journey_verifications"] == []
    assert runtime["last_journey_verified"] == "J1"


def test_closer_infers_pending_journey_when_trailer_omits_journey_line(tmp_project):
    import common

    _seed_registry(common)
    _write_verified_handoff(common, "P00-S01-T002")

    rc = _fire_hook("closer", _closer_trailer("P00-S01-T002"))

    assert rc == 0
    runtime = common.load_runtime_state()
    registry = common.load_registry()
    assert "J1" in runtime["pending_journey_verifications"]
    assert common.find_journey(registry, "J1")["verification_status"] == "pending"


def test_bootstrap_enriches_journey_task_order_and_terminal_frontier():
    import bootstrap_source_of_truth

    tasks = [
        {"id": "P00-S01-T001"},
        {"id": "P00-S01-T002"},
        {"id": "P00-S01-T003"},
    ]
    task_dag = {
        "nodes": ["P00-S01-T001", "P00-S01-T003", "P00-S01-T002"],
        "adjacency_list": {
            "P00-S01-T001": ["P00-S01-T002"],
            "P00-S01-T003": ["P00-S01-T002"],
            "P00-S01-T002": [],
        },
    }
    journeys = [{
        "id": "J1",
        "task_ids": ["P00-S01-T002", "P00-S01-T001", "P00-S01-T003"],
    }]

    out = bootstrap_source_of_truth.enrich_journey_completion_metadata(journeys, tasks, task_dag)[0]

    assert out["task_ids_source_order"] == ["P00-S01-T002", "P00-S01-T001", "P00-S01-T003"]
    assert out["task_ids"] == ["P00-S01-T001", "P00-S01-T003", "P00-S01-T002"]
    assert out["terminal_task_ids"] == ["P00-S01-T002"]
    assert out["completion_policy"] == "all_task_ids_done"
