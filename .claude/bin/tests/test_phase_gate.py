"""End-of-phase gate contract."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


def _copy_contract(root: Path) -> None:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    contract_src = _BIN.parent / "orchestrator-contract.json"
    if contract_src.exists():
        (root / ".claude" / "orchestrator-contract.json").write_text(contract_src.read_text(encoding="utf-8"), encoding="utf-8")

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
    (root / "orchestrator-state" / "tasks" / "reports").mkdir(parents=True)
    (root / "orchestrator-state" / "tasks" / "handoffs").mkdir(parents=True)
    (root / "orchestrator-state" / "tasks" / "evidence").mkdir(parents=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True)
    _copy_contract(root)
    return root, td


def _seed_closed_phase(common, root: Path, *, journey_status="verified", pending=None):
    tasks = [
        {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "done", "depends_on": [], "handoff_path": "orchestrator-state/tasks/handoffs/P00-S01-T001.md", "evidence_dir": "orchestrator-state/tasks/evidence/P00-S01-T001", "report_path": "orchestrator-state/tasks/reports/P00-S01-T001.md"},
        {"id": "P00-S02-T001", "title": "J", "phase_id": "P00", "step_id": "P00-S02", "status": "done", "depends_on": ["P00-S01-T001"], "handoff_path": "orchestrator-state/tasks/handoffs/P00-S02-T001.md", "evidence_dir": "orchestrator-state/tasks/evidence/P00-S02-T001", "report_path": "orchestrator-state/tasks/reports/P00-S02-T001.md"},
    ]
    for task in tasks:
        (root / task["handoff_path"]).write_text(f"# {task['id']}\n", encoding="utf-8")
        (root / task["evidence_dir"]).mkdir(parents=True, exist_ok=True)
        (root / task["report_path"]).write_text(f"# report {task['id']}\n", encoding="utf-8")
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "complete", "task_ids": [t["id"] for t in tasks]}],
        "tasks": tasks,
        "journeys": [{"id": "J101", "task_ids": ["P00-S01-T001", "P00-S02-T001"], "verification_status": journey_status}],
        "task_dag": boot.build_task_dag(tasks),
    })
    common.save_runtime_state({"pending_journey_verifications": pending or [], "spawns_in_current_slice": {}})


def test_phase_gate_passes_closed_phase_with_verified_closing_journey():
    root, td = _setup_root()
    try:
        with _Sandbox(root):
            import common
            import check_phase_gate
            _seed_closed_phase(common, root)
            result = check_phase_gate.validate_phase_gate(common.load_registry(), common.load_runtime_state(), phase_id="P00")
            assert result["ok"] is True
            assert result["counts"]["closing_journeys"] == 1
    finally:
        td.cleanup()


def test_phase_gate_blocks_pending_journey_and_missing_done_task():
    root, td = _setup_root()
    try:
        with _Sandbox(root):
            import common
            import check_phase_gate
            _seed_closed_phase(common, root, journey_status="pending", pending=["J101"])
            registry = common.load_registry()
            registry["tasks"][1]["status"] = "ready_for_close"
            common.save_registry(registry)
            result = check_phase_gate.validate_phase_gate(common.load_registry(), common.load_runtime_state(), phase_id="P00")
            assert result["ok"] is False
            assert any("tasks not done" in e for e in result["errors"])
            assert any("pending journey" in e for e in result["errors"])
    finally:
        td.cleanup()


def test_closer_hook_refuses_false_done_without_push_cleanup_proof():
    root, td = _setup_root()
    try:
        with _Sandbox(root):
            import common
            import hook_capture_subagent_stop
            tasks = [{"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "ready_for_close", "depends_on": []}]
            common.save_registry({
                "generated_at": common.now_iso(),
                "project_prefix": "TEST",
                "phase_order": ["P00"],
                "phases": [{"id": "P00", "title": "P0", "status": "active", "task_ids": ["P00-S01-T001"]}],
                "tasks": tasks,
                "journeys": [],
                "task_dag": boot.build_task_dag(tasks),
            })
            common.save_runtime_state({"pending_journey_verifications": [], "spawns_in_current_slice": {}})
            payload = json.dumps({
                "agent_type": "closer",
                "last_assistant_message": (
                    "CLAUDE_TRAILER:\n"
                    "TASK_ID: P00-S01-T001\n"
                    "OUTCOME: committed\n"
                    "NEXT_STATUS: done\n"
                    "HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md\n"
                    "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md\n"
                    "REPORT_READY: yes\n"
                    "BASELINE_SYNC_READY: yes\n"
                    "GIT_READY: yes\n"
                    "PUSH_READY: no\n"
                    "WORKTREES_CLEANED: yes\n"
                ),
            })
            with mock.patch.object(sys, "stdin", StringIO(payload)):
                hook_capture_subagent_stop.main()
            task = common.load_registry()["tasks"][0]
            assert task["status"] == "blocked"
            err_log = root / "orchestrator-state" / "hook-errors.log"
            assert "closer attempted NEXT_STATUS=done" in err_log.read_text(encoding="utf-8")
    finally:
        td.cleanup()
