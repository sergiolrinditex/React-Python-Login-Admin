"""End-to-end choreography across hooks + helpers + lifecycle.

These tests exercise the whole pipeline at the hook boundary. They model the
production DAG contract:

    developer -> validator/tester -> slice-verifier -> closer

The closer is the only actor that can mark a task done, and it may do so only
after a valid verify-slice handoff exists on disk.
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
        (root / ".claude" / "orchestrator-contract.json").write_text(
            contract_src.read_text(encoding="utf-8"), encoding="utf-8"
        )


class _Sandbox:
    """Point CLAUDE_PROJECT_DIR at a tmpdir and reset lock counters."""

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


def _setup_tmp_project() -> tuple[Path, tempfile.TemporaryDirectory]:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "orchestrator-state" / "tasks").mkdir(parents=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True)
    _copy_contract(root)
    return root, td


def _seed_two_task_registry(*, journeys: list[dict] | None = None) -> None:
    import common

    registry = {
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{
            "id": "P00", "title": "Phase 0", "status": "active",
            "task_ids": ["P00-S01-T001", "P00-S01-T002"],
        }],
        "tasks": [
            {
                "id": "P00-S01-T001",
                "title": "first slice",
                "phase_id": "P00",
                "step_id": "P00-S01",
                "status": "in_progress",
                "depends_on": [],
            },
            {
                "id": "P00-S01-T002",
                "title": "second slice",
                "phase_id": "P00",
                "step_id": "P00-S01",
                "status": "blocked",
                "depends_on": ["P00-S01-T001"],
            },
        ],
        "journeys": journeys or [],
    }
    common.save_registry(registry)
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "last_worker": None,
        "last_event": None,
        "pending_journey_verifications": [],
        "last_journey_verified": None,
        "spawn_budget": 20,
        "spawns_in_current_slice": {},
    })


def _fire_subagent_stop(agent_type: str, message: str) -> int:
    payload = json.dumps({
        "agent_type": agent_type,
        "last_assistant_message": message,
    })
    with mock.patch.object(sys, "stdin", StringIO(payload)):
        import hook_capture_subagent_stop as hook
        return hook.main()


def _trailer(task_id: str, outcome: str, next_status: str, *,
             handoff: str | None = None,
             evidence: str | None = None,
             extras: list[str] | None = None) -> str:
    lines = [
        "CLAUDE_TRAILER:",
        f"TASK_ID: {task_id}",
        f"OUTCOME: {outcome}",
        f"NEXT_STATUS: {next_status}",
    ]
    if handoff:
        lines.append(f"HANDOFF: {handoff}")
    if evidence:
        lines.append(f"EVIDENCE: {evidence}")
    if extras:
        lines.extend(extras)
    return "\n".join(lines) + "\n"


def _write_valid_verified_handoff(root: Path, task_id: str) -> None:
    """Write a cumulative handoff that satisfies ready+verify checks."""
    handoff = root / "orchestrator-state" / "tasks" / "handoffs" / f"{task_id}.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir = root / "orchestrator-state" / "tasks" / "evidence" / task_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    handoff.write_text(f"""# Handoff {task_id}

## Developer handoff
- TASK_ID: {task_id}
- OUTCOME: success

## validator
- TASK_ID: {task_id}
- OUTCOME: approved

## tester
- TASK_ID: {task_id}
- OUTCOME: pass

## verify-slice
- TASK_ID: {task_id}
- AGENT: slice-verifier
- MODE: pre-closer
- MCP_BROWSER: chrome-devtools
- VERIFY_OUTCOME: verified
- DATA_CONTRACT_ROWS: VDC-001
- DATA_SETUP: sandbox-user-1 + seeded record A
- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active
- FLOWS_TESTED: login happy path
- EVIDENCE: orchestrator-state/tasks/evidence/{task_id}/verify-proof.md
""", encoding="utf-8")


def _verify_then_close(task_id: str = "P00-S01-T001", *, journey: str | None = None) -> None:
    _fire_subagent_stop("slice-verifier", _trailer(
        task_id, "verified", "verified_pending_close",
        handoff=f"orchestrator-state/tasks/handoffs/{task_id}.md",
        evidence=f"orchestrator-state/tasks/evidence/{task_id}/verify-proof.md",
        extras=["VERIFY_OUTCOME: verified"],
    ))
    extras = [
        f"REPORT: orchestrator-state/tasks/reports/{task_id}.md",
        "REPORT_READY: yes",
        "BASELINE_SYNC_READY: yes",
        "GIT_READY: yes",
        "PUSH_READY: yes",
        "GIT_WORKFLOW_READY: yes",
        "WORKTREES_CLEANED: yes",
    ]
    if journey:
        extras.append(f"JOURNEY_PENDING_VERIFY: {journey}")
    _fire_subagent_stop("closer", _trailer(task_id, "committed", "done", extras=extras))


class FullPipelineChoreographyTests(unittest.TestCase):

    def test_developer_validator_tester_slice_verifier_closer_converge_to_done(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()

                rc = _fire_subagent_stop("developer", _trailer(
                    "P00-S01-T001", "success", "validator_tester_pending",
                    handoff="orchestrator-state/tasks/handoffs/P00-S01-T001.md",
                ))
                self.assertEqual(rc, 0)

                _fire_subagent_stop("validator", _trailer(
                    "P00-S01-T001", "approved", "ready_for_close",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "validator_tester_pending")
                self.assertEqual(task.get("validator_outcome"), "approved")

                _fire_subagent_stop("tester", _trailer(
                    "P00-S01-T001", "pass", "ready_for_close",
                    evidence="orchestrator-state/tasks/evidence/P00-S01-T001",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "ready_for_close")
                self.assertEqual(task.get("validator_outcome"), "approved")

                _write_valid_verified_handoff(root, "P00-S01-T001")
                _fire_subagent_stop("slice-verifier", _trailer(
                    "P00-S01-T001", "verified", "verified_pending_close",
                    handoff="orchestrator-state/tasks/handoffs/P00-S01-T001.md",
                    evidence="orchestrator-state/tasks/evidence/P00-S01-T001/verify-proof.md",
                    extras=["VERIFY_OUTCOME: verified"],
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "verified_pending_close")

                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "done")
                self.assertEqual(common.load_runtime_state()["last_worker"], "closer")
                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 5)
        finally:
            td.cleanup()

    def test_closer_done_without_verify_handoff_is_blocked(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "blocked")
                self.assertEqual(task.get("last_blocker", {}).get("reason"),
                                 "closer_handoff_contract_failed")
        finally:
            td.cleanup()

    def test_closing_T001_promotes_T002_to_ready(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T002")["status"], "blocked")
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _verify_then_close()
                t002 = common.find_task(common.load_registry(), "P00-S01-T002")
                self.assertEqual(t002["status"], "ready")
        finally:
            td.cleanup()


class JourneyClosingChoreographyTests(unittest.TestCase):

    def _seed_with_journey(self) -> None:
        _seed_two_task_registry(journeys=[{
            "id": "J1",
            "title": "First journey",
            "milestone": "M0",
            "task_ids": ["P00-S01-T001"],
            "verification_status": "pending",
        }])

    def test_closer_emits_journey_pending_verify_lands_in_runtime_state(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                self._seed_with_journey()
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _verify_then_close(journey="J1")
                rt = common.load_runtime_state()
                self.assertIn("J1", rt["pending_journey_verifications"])
                self.assertEqual(rt["last_event"], "journey_pending_verify")
        finally:
            td.cleanup()

    def test_verify_journey_with_verified_clears_pending_and_marks_registry(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                self._seed_with_journey()
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _verify_then_close(journey="J1")
                _fire_subagent_stop("verify-journey", _trailer(
                    "P00-S01-T001", "verified", "done",
                    extras=["JOURNEY_ID: J1", "JOURNEY_VERIFY_OUTCOME: verified"],
                ))
                rt = common.load_runtime_state()
                self.assertEqual(rt["pending_journey_verifications"], [])
                self.assertEqual(rt["last_journey_verified"], "J1")
                journey = common.find_journey(common.load_registry(), "J1")
                self.assertEqual(journey["verification_status"], "verified")
                self.assertIsNotNone(journey.get("verified_at"))
        finally:
            td.cleanup()

    def test_verify_journey_with_issues_found_keeps_pending(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                self._seed_with_journey()
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _verify_then_close(journey="J1")
                _fire_subagent_stop("verify-journey", _trailer(
                    "P00-S01-T001", "issues_found", "needs_debug",
                    extras=["JOURNEY_ID: J1", "JOURNEY_VERIFY_OUTCOME: issues_found"],
                ))
                self.assertIn("J1", common.load_runtime_state()["pending_journey_verifications"])
        finally:
            td.cleanup()

    def test_journey_verify_waived_clears_pending_with_reason(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                os.environ["CLAUDE_ALLOW_JOURNEY_WAIVER"] = "J1"
                self.addCleanup(os.environ.pop, "CLAUDE_ALLOW_JOURNEY_WAIVER", None)
                self._seed_with_journey()
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _verify_then_close(journey="J1")
                _fire_subagent_stop("verify-journey", _trailer(
                    "P00-S01-T001", "waived", "done",
                    extras=[
                        "JOURNEY_ID: J1",
                        "JOURNEY_VERIFY_WAIVED: backend on holiday - human signed off",
                    ],
                ))
                rt = common.load_runtime_state()
                self.assertEqual(rt["pending_journey_verifications"], [])
                journey = common.find_journey(common.load_registry(), "J1")
                self.assertEqual(journey["verification_status"], "waived")
                self.assertIn("backend on holiday", journey.get("waiver_reason", ""))
        finally:
            td.cleanup()


class DebuggerCycleChoreographyTests(unittest.TestCase):

    def test_tester_fail_then_debugger_then_tester_pass(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                _fire_subagent_stop("tester", _trailer("P00-S01-T001", "fail", "needs_debug"))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "needs_debug")
                _fire_subagent_stop("debugger", _trailer(
                    "P00-S01-T001", "fixed", "validator_tester_pending",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "validator_tester_pending")
                self.assertEqual(task.get("last_updated_by"), "debugger")
                _fire_subagent_stop("tester", _trailer("P00-S01-T001", "pass", "ready_for_close"))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "ready_for_close")
                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 3)
        finally:
            td.cleanup()


class SliceVerifierChoreographyTests(unittest.TestCase):

    def test_premature_closer_block_then_slice_verifier_rescues_to_done(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                _fire_subagent_stop("tester", _trailer("P00-S01-T001", "pass", "ready_for_close"))
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "blocked")

                _write_valid_verified_handoff(root, "P00-S01-T001")
                _fire_subagent_stop("slice-verifier", _trailer(
                    "P00-S01-T001", "verified", "verified_pending_close",
                    handoff="orchestrator-state/tasks/handoffs/P00-S01-T001.md",
                    evidence="orchestrator-state/tasks/evidence/P00-S01-T001/verify-proof.md",
                    extras=["VERIFY_OUTCOME: verified"],
                ))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "verified_pending_close")
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "done")
        finally:
            td.cleanup()

    def test_pr_flow_closer_done_requires_merged_and_canonical_main_synced(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                (root / "docs" / "source-of-truth").mkdir(parents=True, exist_ok=True)
                (root / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text(
                    "git_workflow: pr-flow\n",
                    encoding="utf-8",
                )
                _seed_two_task_registry()
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _fire_subagent_stop("slice-verifier", _trailer(
                    "P00-S01-T001", "verified", "verified_pending_close",
                    handoff="orchestrator-state/tasks/handoffs/P00-S01-T001.md",
                    evidence="orchestrator-state/tasks/evidence/P00-S01-T001/verify-proof.md",
                    extras=["VERIFY_OUTCOME: verified"],
                ))
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "PR_READY: yes",
                        "MERGED: auto-queued",
                        "CANONICAL_MAIN_SYNCED: no",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "blocked")

                _seed_two_task_registry()
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _fire_subagent_stop("slice-verifier", _trailer(
                    "P00-S01-T001", "verified", "verified_pending_close",
                    handoff="orchestrator-state/tasks/handoffs/P00-S01-T001.md",
                    evidence="orchestrator-state/tasks/evidence/P00-S01-T001/verify-proof.md",
                    extras=["VERIFY_OUTCOME: verified"],
                ))
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "PR_READY: yes",
                        "MERGED: yes",
                        "CANONICAL_MAIN_SYNCED: yes",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "done")
        finally:
            td.cleanup()

    def test_slice_verifier_issues_found_routes_to_needs_debug(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                _fire_subagent_stop("slice-verifier", _trailer(
                    "P00-S01-T001", "issues_found", "needs_debug",
                    handoff="orchestrator-state/tasks/handoffs/P00-S01-T001.md",
                    evidence="orchestrator-state/tasks/evidence/P00-S01-T001/verify-issues.md",
                    extras=["VERIFY_OUTCOME: issues_found"],
                ))
                self.assertEqual(common.find_task(common.load_registry(), "P00-S01-T001")["status"], "needs_debug")
        finally:
            td.cleanup()


class SpawnBudgetChoreographyTests(unittest.TestCase):

    def test_21st_agent_call_is_denied_after_budget_completed_stops(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                state = common.load_runtime_state()
                state["spawn_budget"] = 5
                common.save_runtime_state(state)
                for _ in range(5):
                    _fire_subagent_stop("developer", _trailer(
                        "P00-S01-T001", "in_progress", "in_progress",
                    ))
                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 5)

                pre_payload = json.dumps({
                    "tool_name": "Agent",
                    "tool_input": {"subagent_type": "developer"},
                })
                buf = StringIO()
                with mock.patch.object(sys, "stdin", StringIO(pre_payload)), \
                     mock.patch.object(sys, "stdout", buf), \
                     mock.patch.dict(os.environ, {"CLAUDE_ACTIVE_TASK_ID": "P00-S01-T001"}, clear=False):
                    import hook_spawn_budget as gate
                    rc = gate.main()
                self.assertEqual(rc, 0)
                decision = json.loads(buf.getvalue().strip())
                self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
                msg = decision["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertIn("P00-S01-T001", msg)
                self.assertIn("5/5", msg)
        finally:
            td.cleanup()

    def test_under_budget_hook_produces_no_output(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                state = common.load_runtime_state()
                state["spawn_budget"] = 5
                common.save_runtime_state(state)
                for _ in range(2):
                    _fire_subagent_stop("developer", _trailer(
                        "P00-S01-T001", "in_progress", "in_progress",
                    ))
                pre_payload = json.dumps({
                    "tool_name": "Agent",
                    "tool_input": {"subagent_type": "validator"},
                })
                buf = StringIO()
                with mock.patch.object(sys, "stdin", StringIO(pre_payload)), \
                     mock.patch.object(sys, "stdout", buf), \
                     mock.patch.dict(os.environ, {"CLAUDE_ACTIVE_TASK_ID": "P00-S01-T001"}, clear=False):
                    import hook_spawn_budget as gate
                    rc = gate.main()
                self.assertEqual(rc, 0)
                self.assertEqual(buf.getvalue(), "")
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)

    def test_pr_flow_closer_done_requires_actual_merge_and_main_sync(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                (root / "docs" / "source-of-truth").mkdir(parents=True, exist_ok=True)
                (root / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text(
                    "profile_version: stack-profile-v1\ngit_workflow: pr-flow\n", encoding="utf-8"
                )
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "WORKTREES_CLEANED: yes",
                        "GIT_WORKFLOW_READY: no",
                        "PR_READY: yes",
                        "MERGED: no",
                        "CANONICAL_MAIN_SYNCED: no",
                    ],
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "blocked")

                _seed_two_task_registry()
                _write_valid_verified_handoff(root, "P00-S01-T001")
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "WORKTREES_CLEANED: yes",
                        "GIT_WORKFLOW_READY: yes",
                        "PR_READY: yes",
                        "MERGED: yes",
                        "CANONICAL_MAIN_SYNCED: yes",
                    ],
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "done")
        finally:
            td.cleanup()
