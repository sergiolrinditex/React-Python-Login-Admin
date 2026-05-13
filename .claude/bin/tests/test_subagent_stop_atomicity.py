"""SubagentStop must commit registry + runtime-state under a single ordered
critical section.

Coverage:
  - End-to-end: a single hook invocation moves registry.task.status AND
    runtime-state.last_worker together — never just one.
  - Lock ordering: remove_pending_journey_verification + waive_journey_verification
    take registry BEFORE runtime-state (project-wide convention to avoid
    deadlocks against the SubagentStop hook).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
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


def _setup_tmp_project():
    """Returns (tmp_path: Path, cleanup: callable)."""
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "orchestrator-state" / "tasks").mkdir(parents=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True)
    _copy_contract(root)
    return root, td


class _Sandbox:
    def __init__(self, root: Path):
        self.root = root

    def __enter__(self):
        self._prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        # Reset module-level lock counter between tests.
        import common
        common._LOCK_DEPTH.clear()
        return self

    def __exit__(self, *exc):
        if self._prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._prev


def _seed_minimal_registry():
    import common
    registry = {
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "Phase 0", "status": "active",
                    "task_ids": ["P00-S01-T001"]}],
        "tasks": [{
            "id": "P00-S01-T001",
            "title": "seed",
            "phase_id": "P00",
            "step_id": "P00-S01",
            "status": "in_progress",
            "depends_on": [],
        }],
        "journeys": [],
    }
    common.save_registry(registry)
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "last_worker": None,
        "last_event": None,
        "pending_journey_verifications": [],
        "last_journey_verified": None,
    })


class HookEndToEndAtomicityTests(unittest.TestCase):

    def test_tester_pass_advances_both_registry_and_runtime_state(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_minimal_registry()

                payload = json.dumps({
                    "agent_type": "tester",
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S01-T001\n"
                        "OUTCOME: pass\n"
                        "NEXT_STATUS: ready_for_close\n"
                        "HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md\n"
                        "EVIDENCE: orchestrator-state/tasks/evidence/P00-S01-T001\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    rc = hook.main()
                self.assertEqual(rc, 0)

                reg = common.load_registry()
                rt  = common.load_runtime_state()
                task = common.find_task(reg, "P00-S01-T001")
                self.assertEqual(task["status"], "ready_for_close",
                    "registry must reflect tester's NEXT_STATUS")
                self.assertEqual(rt["last_worker"], "tester",
                    "runtime-state must reflect the same hook invocation — "
                    "not committing both is exactly the bug Fix #3 addresses")
                self.assertEqual(rt["last_event"], "subagent_stop")
                self.assertEqual(rt["last_trailer"]["task_id"], "P00-S01-T001")
        finally:
            td.cleanup()

    def test_validator_is_informational_does_not_change_status(self):
        """Validator (INFO_ONLY) must not move task.status, but its outcome
        must still be recorded for the closer to read. Regression guard."""
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_minimal_registry()

                payload = json.dumps({
                    "agent_type": "validator",
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S01-T001\n"
                        "OUTCOME: approved\n"
                        "NEXT_STATUS: ready_for_close\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    rc = hook.main()
                self.assertEqual(rc, 0)

                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "in_progress",
                    "validator (INFO_ONLY) must NOT mutate task.status")
                self.assertEqual(task.get("validator_outcome"), "approved")
                self.assertEqual(task.get("validator_next_status"), "ready_for_close")
        finally:
            td.cleanup()


class JourneyHelpersLockOrderTests(unittest.TestCase):
    """remove_pending_journey_verification + waive_journey_verification used
    to acquire (runtime-state -> registry); SubagentStop main() takes
    (registry -> runtime-state). Cross-process flock with opposite orders
    is a textbook deadlock pattern. We assert the helpers now match
    project-wide order by inspecting the source for the inversion fix."""

    def _read_source(self):
        return (_BIN / "common.py").read_text(encoding="utf-8")

    def test_remove_pending_acquires_registry_before_runtime_state(self):
        src = self._read_source()
        i = src.index("def remove_pending_journey_verification")
        body = src[i:i + 2000]
        idx_registry = body.find("file_lock(registry_path())")
        idx_runtime  = body.find("file_lock(runtime_state_path())")
        self.assertGreater(idx_registry, 0)
        self.assertGreater(idx_runtime, 0)
        self.assertLess(idx_registry, idx_runtime,
            "remove_pending_journey_verification must acquire registry BEFORE "
            "runtime-state (project-wide lock order)")

    def test_waive_acquires_registry_before_runtime_state(self):
        src = self._read_source()
        i = src.index("def waive_journey_verification")
        body = src[i:i + 2000]
        idx_registry = body.find("file_lock(registry_path())")
        idx_runtime  = body.find("file_lock(runtime_state_path())")
        self.assertGreater(idx_registry, 0)
        self.assertGreater(idx_runtime, 0)
        self.assertLess(idx_registry, idx_runtime)


if __name__ == "__main__":
    unittest.main(verbosity=2)

class DagScopeMismatchTests(unittest.TestCase):

    def test_env_scoped_worker_does_not_apply_mismatched_journey_mutations(self):
        """A parallel terminal is scoped by CLAUDE_ACTIVE_TASK_ID.

        If a subagent accidentally reports another TASK_ID, neither the task
        lifecycle nor journey-pending state may mutate. Otherwise one terminal
        could unblock/block a different DAG node or create a false journey gate.
        """
        root, td = _setup_tmp_project()
        old_active = os.environ.get("CLAUDE_ACTIVE_TASK_ID")
        try:
            with _Sandbox(root):
                import common
                _seed_minimal_registry()
                os.environ["CLAUDE_ACTIVE_TASK_ID"] = "P00-S01-T001"

                payload = json.dumps({
                    "agent_type": "closer",
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S99-T999\n"
                        "OUTCOME: pass\n"
                        "NEXT_STATUS: done\n"
                        "JOURNEY_PENDING_VERIFY: J999\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    rc = hook.main()
                self.assertEqual(rc, 0)

                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "in_progress")
                runtime = common.load_runtime_state()
                self.assertEqual(runtime.get("pending_journey_verifications"), [])
                self.assertTrue(runtime.get("last_trailer", {}).get("task_id_mismatch"))
                self.assertTrue((root / "orchestrator-state" / "hook-errors.log").exists())
        finally:
            if old_active is None:
                os.environ.pop("CLAUDE_ACTIVE_TASK_ID", None)
            else:
                os.environ["CLAUDE_ACTIVE_TASK_ID"] = old_active
            td.cleanup()

class UnknownAgentMutationTests(unittest.TestCase):

    def test_unknown_agent_trailer_cannot_mutate_task_status(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_minimal_registry()
                payload = json.dumps({
                    "agent_type": "random-helper",
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S01-T001\n"
                        "OUTCOME: pass\n"
                        "NEXT_STATUS: done\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    rc = hook.main()
                self.assertEqual(rc, 0)
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "in_progress")
                runtime = common.load_runtime_state()
                self.assertEqual(runtime["last_worker"], "random-helper")
        finally:
            td.cleanup()
