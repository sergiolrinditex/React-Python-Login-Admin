from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import inspect_task_state  # noqa: E402


class InspectTaskStateTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / "orchestrator-state" / "tasks").mkdir(parents=True)
        (self.root / "orchestrator-state" / "memory").mkdir(parents=True)
        self.prev_project = os.environ.get("CLAUDE_PROJECT_DIR")
        self.prev_root = os.environ.get("CLAUDE_ORCHESTRATOR_ROOT")
        self.prev_worktree = os.environ.get("CLAUDE_WORKTREE_ROOT")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        os.environ.pop("CLAUDE_ORCHESTRATOR_ROOT", None)
        os.environ.pop("CLAUDE_WORKTREE_ROOT", None)

    def tearDown(self):
        if self.prev_project is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self.prev_project
        if self.prev_root is None:
            os.environ.pop("CLAUDE_ORCHESTRATOR_ROOT", None)
        else:
            os.environ["CLAUDE_ORCHESTRATOR_ROOT"] = self.prev_root
        if self.prev_worktree is None:
            os.environ.pop("CLAUDE_WORKTREE_ROOT", None)
        else:
            os.environ["CLAUDE_WORKTREE_ROOT"] = self.prev_worktree
        self.td.cleanup()

    def _write_runtime(self):
        runtime = {
            "last_worker": "tester",
            "last_event": "subagent_stop",
            "pending_journey_verifications": [],
            "open_followups": [],
        }
        (self.root / "orchestrator-state" / "tasks" / "runtime-state.json").write_text(json.dumps(runtime), encoding="utf-8")

    def test_reads_canonical_list_tasks_without_dict_get_assumption(self):
        registry = {
            "task_dag": {"mode": "explicit_dag"},
            "phase_order": ["P00"],
            "tasks": [
                {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "status": "ready", "depends_on": []},
                {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "status": "done", "depends_on": ["P00-S01-T001"]},
            ],
        }
        (self.root / "orchestrator-state" / "tasks" / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
        self._write_runtime()
        snap = inspect_task_state.build_snapshot("P00-S01-T001")
        self.assertTrue(snap["ok"])
        self.assertEqual(snap["task"]["id"], "P00-S01-T001")
        self.assertEqual(snap["counts"]["ready"], 1)
        self.assertEqual(snap["counts"]["done"], 1)

    def test_tolerates_legacy_dict_tasks_shape(self):
        registry = {
            "task_dag": {"mode": "explicit_dag"},
            "phase_order": ["P00"],
            "tasks": {
                "P00-S01-T001": {"title": "A", "phase_id": "P00", "status": "ready", "depends_on": []},
                "P00-S01-T002": {"title": "B", "phase_id": "P00", "status": "done", "depends_on": []},
            },
        }
        (self.root / "orchestrator-state" / "tasks" / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
        self._write_runtime()
        snap = inspect_task_state.build_snapshot("P00-S01-T001")
        self.assertTrue(snap["ok"])
        self.assertEqual(snap["task"]["id"], "P00-S01-T001")
        self.assertEqual(snap["counts"], {"tasks": 2, "ready": 1, "active": 0, "done": 1})

    def test_reports_canonical_pack_when_workspace_pack_missing(self):
        workspace = self.root / "worktrees" / "P00-S01-T001"
        workspace.mkdir(parents=True)
        os.environ["CLAUDE_ORCHESTRATOR_ROOT"] = str(self.root)
        os.environ["CLAUDE_WORKTREE_ROOT"] = str(workspace)
        registry = {
            "task_dag": {"mode": "explicit_dag"},
            "tasks": [{"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "status": "ready"}],
        }
        (self.root / "orchestrator-state" / "tasks" / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
        self._write_runtime()
        pack = self.root / "orchestrator-state" / "tasks" / "task-packs" / "P00-S01-T001.md"
        pack.parent.mkdir(parents=True)
        pack.write_text("# pack", encoding="utf-8")
        snap = inspect_task_state.build_snapshot("P00-S01-T001")
        self.assertFalse(snap["paths"]["task_pack"]["workspace_exists"])
        self.assertTrue(snap["paths"]["task_pack"]["canonical_exists"])
        self.assertTrue(any("canonical root" in w for w in snap["warnings"]))

    def test_print_markdown_emits_single_snapshot_heading(self):
        registry = {
            "task_dag": {"mode": "explicit_dag"},
            "phase_order": ["P00"],
            "tasks": [{"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "status": "ready", "depends_on": []}],
        }
        (self.root / "orchestrator-state" / "tasks" / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
        self._write_runtime()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            inspect_task_state.main(["--task", "P00-S01-T001"])
        self.assertEqual(buf.getvalue().count("# Task context snapshot"), 1)


if __name__ == "__main__":
    unittest.main()
