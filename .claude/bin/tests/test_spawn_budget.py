"""Spawn-budget invariant (Fix #4) is mechanically tracked in runtime-state.

Coverage:
  - bump_spawn_count increments per task and per agent.
  - The counter resets when the DAG task changes (no leakage between slices).
  - Budget exceedance is logged to orchestrator-state/hook-errors.log so SessionStart shows it.
  - SessionStart context shows the count vs. budget for the DAG task.
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


class _Sandbox:
    def __init__(self, root: Path):
        self.root = root

    def __enter__(self):
        self._prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        import common
        common._LOCK_DEPTH.clear()
        return self

    def __exit__(self, *exc):
        if self._prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._prev


def _setup():
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "orchestrator-state" / "tasks").mkdir(parents=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True)
    return root, td


def _seed():
    import common
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "active",
                    "task_ids": ["P00-S01-T001"]}],
        "tasks": [{"id": "P00-S01-T001", "title": "x", "phase_id": "P00",
                   "step_id": "P00-S01", "status": "in_progress", "depends_on": []}],
        "journeys": [],
        "task_dag": {"mode": "explicit_dag"},
    })
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "last_worker": None,
        "last_event": None,
        "pending_journey_verifications": [],
        "last_journey_verified": None,
        "spawn_budget": 20,
        "spawns_in_current_slice": {},
    })


class BumpSpawnCountTests(unittest.TestCase):

    def test_bump_increments_task_and_agent_counters(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                self.assertEqual(common.bump_spawn_count("P00-S01-T001", "developer"), 1)
                self.assertEqual(common.bump_spawn_count("P00-S01-T001", "validator"), 2)
                self.assertEqual(common.bump_spawn_count("P00-S01-T001", "tester"), 3)

                state = common.load_runtime_state()
                counts = state["spawns_in_current_slice"]
                self.assertEqual(counts["P00-S01-T001"], 3)
                self.assertEqual(counts["agent:developer"], 1)
                self.assertEqual(counts["agent:validator"], 1)
                self.assertEqual(counts["agent:tester"], 1)
                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 3)
                self.assertEqual(common.get_spawn_budget(), 20)
        finally:
            td.cleanup()

    def test_bump_keeps_independent_dag_task_counters(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                common.bump_spawn_count("P00-S01-T001", "developer")
                common.bump_spawn_count("P00-S01-T001", "validator")
                # New DAG task — counters may coexist for independent terminals.
                self.assertEqual(common.bump_spawn_count("P00-S01-T002", "developer"), 1)
                state = common.load_runtime_state()
                counts = state["spawns_in_current_slice"]
                self.assertEqual(counts["P00-S01-T001"], 2)
                self.assertEqual(counts["P00-S01-T002"], 1)
        finally:
            td.cleanup()

    def test_bump_with_none_task_is_no_op(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                self.assertEqual(common.bump_spawn_count(None, "developer"), 0)
                self.assertEqual(common.get_spawn_count(None), 0)
        finally:
            td.cleanup()

    def test_reset_spawn_counter_clears_all(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                common.bump_spawn_count("P00-S01-T001", "developer")
                common.bump_spawn_count("P00-S01-T001", "validator")
                common.reset_spawn_counter()
                self.assertEqual(common.load_runtime_state()["spawns_in_current_slice"], {})
        finally:
            td.cleanup()


class SubagentStopBumpsCounterTests(unittest.TestCase):

    def test_hook_invocation_bumps_counter(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                payload = json.dumps({
                    "agent_type": "developer",
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S01-T001\n"
                        "OUTCOME: pass\n"
                        "NEXT_STATUS: review_pending\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    hook.main()

                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 1,
                    "SubagentStop must bump the counter for the DAG task")
        finally:
            td.cleanup()

    def test_exceeding_budget_writes_to_hook_errors_log(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                # Pre-load 20 spawns directly so the next one exceeds.
                for i in range(20):
                    common.bump_spawn_count("P00-S01-T001", f"agent_{i}")

                payload = json.dumps({
                    "agent_type": "extra",
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S01-T001\n"
                        "OUTCOME: pass\n"
                        "NEXT_STATUS: review_pending\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    hook.main()

                err_log = root / "orchestrator-state" / "hook-errors.log"
                self.assertTrue(err_log.exists(), "exceeding budget must log")
                body = err_log.read_text(encoding="utf-8")
                self.assertIn("spawn budget exceeded", body)
                self.assertIn("P00-S01-T001", body)
        finally:
            td.cleanup()


class SessionStartShowsBudgetTests(unittest.TestCase):

    def test_session_context_includes_spawn_line(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                common.bump_spawn_count("P00-S01-T001", "developer")
                common.bump_spawn_count("P00-S01-T001", "validator")

                import hook_session_context as session_hook
                with mock.patch.dict(os.environ, {"CLAUDE_ACTIVE_TASK_ID": "P00-S01-T001"}, clear=False):
                    ctx = session_hook.build_context()
                self.assertIn("Spawns this slice: 2/20", ctx)
        finally:
            td.cleanup()

    def test_session_context_marks_at_budget(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                for i in range(20):
                    common.bump_spawn_count("P00-S01-T001", f"a{i}")

                import hook_session_context as session_hook
                with mock.patch.dict(os.environ, {"CLAUDE_ACTIVE_TASK_ID": "P00-S01-T001"}, clear=False):
                    ctx = session_hook.build_context()
                self.assertIn("over budget", ctx)


        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
