"""Trailer parser must be NOISY when required keys are missing (Fix #5).

Coverage:
  - parse_json_trailer accepts the {"claude_trailer": {...}} envelope and
    a bare {"TASK_ID": ...} dict; case-insensitive keys.
  - trailer_missing_required returns required keys per agent role.
  - The SubagentStop hook logs to orchestrator-state/hook-errors.log when a lifecycle/reporting
    agent finishes without required keys.
  - JSON fallback is merged with regex parse (regex wins per-key).
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
    (root / ".claude").mkdir(parents=True)
    contract_src = _BIN.parent / "orchestrator-contract.json"
    if contract_src.exists():
        (root / ".claude" / "orchestrator-contract.json").write_text(contract_src.read_text(encoding="utf-8"), encoding="utf-8")
    return root, td


def _seed():
    import common
    common.save_registry({
        "generated_at": common.now_iso(), "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "active",
                    "task_ids": ["P00-S01-T001"]}],
        "tasks": [{"id": "P00-S01-T001", "title": "x", "phase_id": "P00",
                   "step_id": "P00-S01", "status": "in_progress", "depends_on": []}],
        "journeys": [],
    })
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "last_worker": None, "last_event": None,
        "pending_journey_verifications": [], "last_journey_verified": None,
        "spawn_budget": 20, "spawns_in_current_slice": {},
    })


class JSONTrailerFallbackTests(unittest.TestCase):

    def test_fenced_json_with_envelope(self):
        import hook_capture_subagent_stop as hook
        text = (
            "Some narrative.\n\n"
            "```json\n"
            "{\"claude_trailer\": {\"TASK_ID\": \"P02-S03-T004\", "
            "\"OUTCOME\": \"pass\", \"NEXT_STATUS\": \"ready_for_close\"}}"
            "\n```\n"
        )
        out = hook.parse_json_trailer(text)
        self.assertEqual(out["task_id"], "P02-S03-T004")
        self.assertEqual(out["outcome"], "pass")
        self.assertEqual(out["next_status"], "ready_for_close")

    def test_fenced_json_bare_dict(self):
        import hook_capture_subagent_stop as hook
        text = "```\n{\"TASK_ID\": \"P00-S01-T001\", \"OUTCOME\": \"approved\"}\n```"
        out = hook.parse_json_trailer(text)
        self.assertEqual(out, {"task_id": "P00-S01-T001", "outcome": "approved"})

    def test_no_json_block_returns_empty(self):
        import hook_capture_subagent_stop as hook
        self.assertEqual(hook.parse_json_trailer("plain text without code"), {})
        self.assertEqual(hook.parse_json_trailer(""), {})

    def test_invalid_json_block_is_skipped(self):
        import hook_capture_subagent_stop as hook
        text = "```json\n{not valid json}\n```"
        self.assertEqual(hook.parse_json_trailer(text), {})


class RequiredKeysTests(unittest.TestCase):

    def test_lifecycle_agent_requires_task_outcome_status(self):
        import hook_capture_subagent_stop as hook
        self.assertEqual(hook.required_keys_for("developer"),
                         {"task_id", "outcome", "next_status"})
        self.assertEqual(hook.required_keys_for("tester"),
                         {"task_id", "outcome", "next_status"})

    def test_reporting_agent_requires_task_outcome_only(self):
        import hook_capture_subagent_stop as hook
        self.assertEqual(hook.required_keys_for("validator"),
                         {"task_id", "outcome"})
        # The researcher may also run during bootstrap/docs reconciliation before
        # an active TASK_ID exists, so OUTCOME is required and TASK_ID is allowed
        # but not mandatory. Slice-specific calls still include TASK_ID by agent
        # instruction and are captured in the ledger.
        self.assertEqual(hook.required_keys_for("official-docs-researcher"),
                         {"outcome"})

    def test_non_lifecycle_contract_roles_use_schema_required_keys(self):
        import hook_capture_subagent_stop as hook
        self.assertEqual(hook.required_keys_for("planner"), {"outcome", "context_ready"})
        self.assertEqual(hook.required_keys_for("main-orchestrator"), {"outcome"})
        self.assertEqual(hook.required_keys_for(None), set())

    def test_missing_returns_sorted(self):
        import hook_capture_subagent_stop as hook
        missing = hook.trailer_missing_required(
            {"task_id": "x"}, "developer")
        self.assertEqual(missing, ["next_status", "outcome"])

    def test_missing_returns_empty_when_complete(self):
        import hook_capture_subagent_stop as hook
        missing = hook.trailer_missing_required(
            {"task_id": "x", "outcome": "pass", "next_status": "rfc"},
            "developer")
        self.assertEqual(missing, [])


class HookSurfacesIncompleteTrailerTests(unittest.TestCase):

    def test_developer_without_next_status_logs_error(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                payload = json.dumps({
                    "agent_type": "developer",
                    # NEXT_STATUS missing -> must log
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S01-T001\n"
                        "OUTCOME: pass\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    rc = hook.main()
                self.assertEqual(rc, 0)

                err_log = root / "orchestrator-state" / "hook-errors.log"
                self.assertTrue(err_log.exists(),
                    "incomplete lifecycle trailer must log to orchestrator-state/hook-errors.log")
                body = err_log.read_text(encoding="utf-8")
                self.assertIn("trailer incomplete", body)
                self.assertIn("next_status", body)
        finally:
            td.cleanup()

    def test_planner_without_trailer_logs_error(self):
        """Planner has a schema role; missing OUTCOME must be visible."""
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                payload = json.dumps({
                    "agent_type": "planner",
                    "last_assistant_message": "Just narrative, no trailer.",
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    rc = hook.main()
                self.assertEqual(rc, 0)

                err_log = root / "orchestrator-state" / "hook-errors.log"
                self.assertTrue(err_log.exists(), "planner without required OUTCOME must log a visible trailer error")
                body = err_log.read_text(encoding="utf-8")
                self.assertIn("trailer incomplete", body)
        finally:
            td.cleanup()

    def test_json_fallback_satisfies_required(self):
        root, td = _setup()
        try:
            with _Sandbox(root):
                import common
                _seed()
                payload = json.dumps({
                    "agent_type": "developer",
                    "last_assistant_message": (
                        "Narrative.\n"
                        "```json\n"
                        "{\"claude_trailer\": {\"TASK_ID\": \"P00-S01-T001\", "
                        "\"OUTCOME\": \"success\", \"NEXT_STATUS\": \"validator_tester_pending\"}}"
                        "\n```\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    import hook_capture_subagent_stop as hook
                    rc = hook.main()
                self.assertEqual(rc, 0)

                # Must have advanced status via the JSON fallback.
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "validator_tester_pending",
                    "JSON-fenced trailer must satisfy lifecycle parser")
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
