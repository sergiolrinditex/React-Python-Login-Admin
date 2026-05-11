"""DAG-only task scoping has no global task/implicit selector files."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
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


def _seed(root: Path):
    (root / "orchestrator-state" / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True, exist_ok=True)
    import common
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "active", "task_ids": ["P00-S01-T001"]}],
        "tasks": [{"id": "P00-S01-T001", "title": "Task", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": []}],
        "journeys": [],
        "task_dag": {"mode": "explicit_dag"},
    })
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "spawn_budget": 20,
        "spawns_in_current_slice": {},
    })


class DagWorkerTaskScopeTests(unittest.TestCase):
    def test_no_implicit_selector_helpers_are_exposed(self):
        import common
        self.assertFalse(hasattr(common, "save_" + "worker_task"))
        self.assertFalse(hasattr(common, "save_" + "worker_phase"))
        self.assertFalse(hasattr(common, "dag_worker_pointer_migration_flag"))
        self.assertFalse(hasattr(common, "load_worker_task"))

    def test_explicit_dag_requires_env_override_for_effective_task(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with _Sandbox(root):
                import common
                _seed(root)
                self.assertIsNone(common.effective_worker_task_id())
                with mock.patch.dict(os.environ, {"CLAUDE_ACTIVE_TASK_ID": "P00-S01-T001"}, clear=False):
                    self.assertEqual(common.effective_worker_task_id(), "P00-S01-T001")
                    registry = common.load_registry()
                    self.assertEqual(common.find_task(registry, "P00-S01-T001").get("id"), "P00-S01-T001")

    def test_sync_does_not_create_task_or_phase_pointer_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with _Sandbox(root):
                import common
                _seed(root)
                mem = root / "orchestrator-state" / "memory"
                common.sync_runtime_state_from_registry(common.load_registry())
                produced = [p.name for p in mem.iterdir() if p.is_file()]
                self.assertEqual(produced, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
