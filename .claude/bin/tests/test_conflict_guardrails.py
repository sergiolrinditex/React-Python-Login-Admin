"""DAG conflict guardrails: conflict_groups/write_set are source-of-truth.

These tests pin the safety layer that sits beside the dependency DAG: two tasks
can be dependency-ready but still must not run in the same wave if they touch the
same shared files or conflict groups.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import bootstrap_source_of_truth as boot  # noqa: E402


class _Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self.prev = None

    def __enter__(self):
        self.prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        import common
        common._LOCK_DEPTH.clear()
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self.prev


def _setup_root():
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "orchestrator-state" / "tasks").mkdir(parents=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True)
    return root, td


def _conflict_checklist() -> str:
    return """# App Implementation Checklist

## Coverage Registry

| Slice ID | Tipo | Target | Step | Depends on | Conflict group | Write set | Verify mínimo |
|---|---|---|---|---|---|---|---|
| P00-S01-T001 | flutter | A page | Step 0.1 | — | router | app/lib/core/router.dart | test A |
| P00-S01-T002 | flutter | B page | Step 0.1 | — | router | app/lib/core/router.dart | test B |
| P00-S01-T003 | api | Health | Step 0.1 | — | api:health | api/src/health.py | test C |

# Phase 0 — Test phase

## Step 0.1 — Roots
- roots exist
"""


def test_bootstrap_parses_conflict_groups_and_write_set():
    _, tasks = boot.build_phases_and_tasks(Path("APP_IMPLEMENTATION_CHECKLIST.md"), _conflict_checklist())
    by_id = {t["id"]: t for t in tasks}
    assert by_id["P00-S01-T001"]["conflict_groups"] == ["router"]
    assert by_id["P00-S01-T001"]["write_set"] == ["app/lib/core/router.dart"]
    dag = boot.build_task_dag(tasks)
    assert dag["conflict_groups"]["P00-S01-T001"] == ["router"]
    assert dag["write_set"]["P00-S01-T002"] == ["app/lib/core/router.dart"]


def test_next_wave_serializes_ready_conflicts_and_keeps_safe_nodes_parallel():
    root, td = _setup_root()
    try:
        with _Sandbox(root):
            import common
            import next_wave
            _, tasks = boot.build_phases_and_tasks(Path("APP_IMPLEMENTATION_CHECKLIST.md"), _conflict_checklist())
            common.save_registry({
                "generated_at": common.now_iso(),
                "project_prefix": "TEST",
                "phase_order": ["P00"],
                "phases": [{"id": "P00", "title": "P0", "status": "ready", "task_ids": [t["id"] for t in tasks]}],
                "tasks": tasks,
                "journeys": [],
                "task_dag": boot.build_task_dag(tasks),
            })
            common.save_runtime_state({"pending_journey_verifications": [], "spawns_in_current_slice": {}})
            result = next_wave.compute_wave(common.load_registry())
            assert result["ready_total"] == 3
            assert [t["id"] for t in result["ready"]] == ["P00-S01-T001", "P00-S01-T003"]
            assert [t["id"] for t in result["deferred_due_conflicts"]] == ["P00-S01-T002"]
            assert "router" in result["deferred_due_conflicts"][0]["conflict_reason"]
    finally:
        td.cleanup()


def test_claim_task_denies_active_conflict_even_when_dependencies_are_ready():
    root, td = _setup_root()
    try:
        with _Sandbox(root):
            import common
            import claim_task
            tasks = [
                {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "claimed", "depends_on": [], "conflict_groups": ["router"], "write_set": ["app/lib/core/router.dart"]},
                {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": [], "conflict_groups": ["router"], "write_set": ["app/lib/core/router.dart"]},
            ]
            common.save_registry({
                "generated_at": common.now_iso(),
                "project_prefix": "TEST",
                "phase_order": ["P00"],
                "phases": [{"id": "P00", "title": "P0", "status": "active", "task_ids": [t["id"] for t in tasks]}],
                "tasks": tasks,
                "journeys": [],
                "task_dag": boot.build_task_dag(tasks),
            })
            common.save_runtime_state({"pending_journey_verifications": [], "spawns_in_current_slice": {}})
            ok, result = claim_task.claim_task("P00-S01-T002")
            assert ok is False
            assert result["conflict_blockers"][0]["task_id"] == "P00-S01-T001"
            assert common.load_registry()["tasks"][1]["status"] == "ready"
    finally:
        td.cleanup()


def test_validator_tester_pending_is_active_conflict_blocker():
    root, td = _setup_root()
    try:
        with _Sandbox(root):
            import common
            import claim_task
            tasks = [
                {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "validator_tester_pending", "depends_on": [], "conflict_groups": ["router"], "write_set": ["app/lib/core/router.dart"]},
                {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": [], "conflict_groups": ["router"], "write_set": ["app/lib/core/router.dart"]},
            ]
            common.save_registry({
                "generated_at": common.now_iso(),
                "project_prefix": "TEST",
                "phase_order": ["P00"],
                "phases": [{"id": "P00", "title": "P0", "status": "active", "task_ids": [t["id"] for t in tasks]}],
                "tasks": tasks,
                "journeys": [],
                "task_dag": boot.build_task_dag(tasks),
            })
            common.save_runtime_state({"pending_journey_verifications": [], "spawns_in_current_slice": {}})
            ok, result = claim_task.claim_task("P00-S01-T002")
            assert ok is False
            assert result["conflict_blockers"][0]["task_id"] == "P00-S01-T001"
    finally:
        td.cleanup()


def test_dependency_blocked_tasks_do_not_serialize_current_wave():
    root, td = _setup_root()
    try:
        with _Sandbox(root):
            import common
            import next_wave
            tasks = [
                {"id": "P00-S01-T001", "title": "Ready A", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": [], "conflict_groups": ["scripts"], "write_set": ["scripts/a.sh"], "dependency_mode": "explicit_dag"},
                {"id": "P00-S01-T002", "title": "Blocked future", "phase_id": "P00", "step_id": "P00-S01", "status": "blocked", "depends_on": ["P99-S01-T001"], "conflict_groups": ["scripts"], "write_set": ["scripts/**"], "dependency_mode": "explicit_dag"},
                {"id": "P99-S01-T001", "title": "Missing dep", "phase_id": "P99", "step_id": "P99-S01", "status": "blocked", "depends_on": [], "conflict_groups": [], "write_set": [], "dependency_mode": "explicit_dag"},
            ]
            common.save_registry({
                "generated_at": common.now_iso(),
                "project_prefix": "TEST",
                "phase_order": ["P00", "P99"],
                "phases": [
                    {"id": "P00", "title": "P0", "status": "active", "task_ids": ["P00-S01-T001", "P00-S01-T002"]},
                    {"id": "P99", "title": "P99", "status": "blocked", "task_ids": ["P99-S01-T001"]},
                ],
                "tasks": tasks,
                "journeys": [],
                "task_dag": boot.build_task_dag(tasks),
            })
            common.save_runtime_state({"pending_journey_verifications": [], "spawns_in_current_slice": {}})
            result = next_wave.compute_wave(common.load_registry())
            assert [t["id"] for t in result["ready"]] == ["P00-S01-T001"]
            assert result["deferred_due_conflicts"] == []
    finally:
        td.cleanup()
