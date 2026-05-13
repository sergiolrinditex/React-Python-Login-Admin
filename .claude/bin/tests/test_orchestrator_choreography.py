"""End-to-end choreography across hooks + helpers + lifecycle.

Existing tests cover individual building blocks (trailer parsing, lock order,
validator/tester race, spawn budget arithmetic). These tests exercise the
WHOLE pipeline: planner → developer → validator ‖ tester → debugger? → closer
→ /verify-journey, mutating registry + runtime-state via the real
SubagentStop hook and asserting they converge to the expected state at every
step. The point is to catch regressions in the *interaction* of components,
not in any single component.

All tests use unittest.TestCase (not pytest fixtures) so unittest discover
picks them up. Each test isolates state in a tempdir and clears the
module-level lock counter on entry/exit.
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


# ---------------------------------------------------------------------------
# Shared harness (kept here intentionally — these tests are about cross-hook
# choreography, so the harness replays the real flow rather than reusing
# fixtures from other test files that test isolated invariants).
# ---------------------------------------------------------------------------


class _Sandbox:
    """Point CLAUDE_PROJECT_DIR at a tmpdir and reset the module-level
    lock counter so each test starts clean."""

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
    """Two-task registry where T001 is in_progress and T002 depends on T001.

    After T001 reaches `done`, promote_ready_tasks must flip T002 to `ready` —
    that promotion is one of the things the choreography asserts.
    """
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
    """Invoke the SubagentStop hook with a synthetic payload. Returns rc."""
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


# ---------------------------------------------------------------------------
# 1) Full pipeline: developer → validator ‖ tester → closer → done
# ---------------------------------------------------------------------------
class FullPipelineChoreographyTests(unittest.TestCase):

    def test_developer_validator_tester_closer_converge_to_done(self):
        """Five subagent stops in canonical order. Asserts:
          - validator_outcome survives across the tester write,
          - tester is the one who flips task.status,
          - closer's next_status (`done`) is the final state,
          - spawn count for the slice equals the number of stops fired.
        """
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()

                # 1. developer — claims/in_progress + handoff init.
                rc = _fire_subagent_stop("developer", _trailer(
                    "P00-S01-T001", "success", "validator_tester_pending",
                    handoff="orchestrator-state/tasks/handoffs/P00-S01-T001.md",
                ))
                self.assertEqual(rc, 0)

                # 2. validator (INFO_ONLY) — approves; must NOT change status.
                _fire_subagent_stop("validator", _trailer(
                    "P00-S01-T001", "approved", "ready_for_close",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "validator_tester_pending",
                    "validator must not overwrite developer's status")
                self.assertEqual(task.get("validator_outcome"), "approved")

                # 3. tester — pass; flips status to ready_for_close.
                _fire_subagent_stop("tester", _trailer(
                    "P00-S01-T001", "pass", "ready_for_close",
                    evidence="orchestrator-state/tasks/evidence/P00-S01-T001",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "ready_for_close")
                # Validator metadata still present after tester wrote.
                self.assertEqual(task.get("validator_outcome"), "approved",
                    "validator_outcome must survive subsequent tester write")

                # 4. closer — done.
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))
                reg = common.load_registry()
                task = common.find_task(reg, "P00-S01-T001")
                self.assertEqual(task["status"], "done")

                # Runtime-state final snapshot — last worker is closer.
                rt = common.load_runtime_state()
                self.assertEqual(rt["last_worker"], "closer")

                # Spawn count = 4 (developer, validator, tester, closer).
                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 4)
        finally:
            td.cleanup()

    def test_closing_T001_promotes_T002_to_ready(self):
        """When T001 is marked `done`, promote_ready_tasks (called inside
        the SubagentStop hook) must flip T002 from `blocked` to `ready`.
        Without that promotion, the planner would never pick T002 next."""
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()

                # T002 starts as blocked.
                self.assertEqual(
                    common.find_task(common.load_registry(), "P00-S01-T002")["status"],
                    "blocked",
                )

                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "WORKTREES_CLEANED: yes",
                    ],
                ))

                t002 = common.find_task(common.load_registry(), "P00-S01-T002")
                self.assertEqual(t002["status"], "ready",
                    "closing T001 must auto-promote T002 — the planner depends "
                    "on this promotion to pick the next slice")
        finally:
            td.cleanup()


# ---------------------------------------------------------------------------
# 2) Journey gate
# ---------------------------------------------------------------------------
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

                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "WORKTREES_CLEANED: yes",
                        "JOURNEY_PENDING_VERIFY: J1",
                    ],
                ))

                rt = common.load_runtime_state()
                self.assertIn("J1", rt["pending_journey_verifications"],
                    "closer's JOURNEY_PENDING_VERIFY must land in runtime-state")
                self.assertEqual(rt["last_event"], "journey_pending_verify",
                    "last_event must reflect the journey-pending mutation, "
                    "not the generic 'subagent_stop'")
        finally:
            td.cleanup()

    def test_verify_journey_with_verified_clears_pending_and_marks_registry(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                self._seed_with_journey()

                # Closer first.
                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "WORKTREES_CLEANED: yes",
                        "JOURNEY_PENDING_VERIFY: J1",
                    ],
                ))
                # Then /verify-journey reports verified.
                _fire_subagent_stop("verify-journey", _trailer(
                    "P00-S01-T001", "verified", "done",
                    extras=["JOURNEY_ID: J1", "JOURNEY_VERIFY_OUTCOME: verified"],
                ))

                rt = common.load_runtime_state()
                self.assertEqual(rt["pending_journey_verifications"], [],
                    "verified journey must drop out of pending list")
                self.assertEqual(rt["last_journey_verified"], "J1")

                journey = common.find_journey(common.load_registry(), "J1")
                self.assertEqual(journey["verification_status"], "verified")
                self.assertIsNotNone(journey.get("verified_at"))
        finally:
            td.cleanup()

    def test_verify_journey_with_issues_found_keeps_pending(self):
        """`issues_found` does NOT clear pending — debugger must fix first.
        Regression guard against accidentally treating both outcomes alike."""
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                self._seed_with_journey()

                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "WORKTREES_CLEANED: yes",
                        "JOURNEY_PENDING_VERIFY: J1",
                    ],
                ))
                _fire_subagent_stop("verify-journey", _trailer(
                    "P00-S01-T001", "issues_found", "needs_debug",
                    extras=["JOURNEY_ID: J1", "JOURNEY_VERIFY_OUTCOME: issues_found"],
                ))

                rt = common.load_runtime_state()
                self.assertIn("J1", rt["pending_journey_verifications"],
                    "issues_found must NOT clear pending; debugger fixes first")
        finally:
            td.cleanup()

    def test_journey_verify_waived_clears_pending_with_reason(self):
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                self._seed_with_journey()

                _fire_subagent_stop("closer", _trailer(
                    "P00-S01-T001", "committed", "done",
                    extras=[
                        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
                        "REPORT_READY: yes",
                        "BASELINE_SYNC_READY: yes",
                        "GIT_READY: yes",
                        "PUSH_READY: yes",
                        "WORKTREES_CLEANED: yes",
                        "JOURNEY_PENDING_VERIFY: J1",
                    ],
                ))
                _fire_subagent_stop("verify-journey", _trailer(
                    "P00-S01-T001", "waived", "done",
                    extras=[
                        "JOURNEY_ID: J1",
                        "JOURNEY_VERIFY_WAIVED: backend on holiday — human signed off",
                    ],
                ))

                rt = common.load_runtime_state()
                self.assertEqual(rt["pending_journey_verifications"], [])
                journey = common.find_journey(common.load_registry(), "J1")
                self.assertEqual(journey["verification_status"], "waived")
                self.assertIn("backend on holiday", journey.get("waiver_reason", ""))
        finally:
            td.cleanup()


# ---------------------------------------------------------------------------
# 3) Debugger cycle: tester fail → debugger → tester pass
# ---------------------------------------------------------------------------
class DebuggerCycleChoreographyTests(unittest.TestCase):

    def test_tester_fail_then_debugger_then_tester_pass(self):
        """Three stops simulate the canonical cycle:
            tester fail → status=needs_debug
            debugger    → status=validator_tester_pending, last_updated_by=debugger
            tester pass → status=ready_for_close
        Spawn count must be 3 (no leakage from previous tests)."""
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()

                _fire_subagent_stop("tester", _trailer(
                    "P00-S01-T001", "fail", "needs_debug",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "needs_debug")

                _fire_subagent_stop("debugger", _trailer(
                    "P00-S01-T001", "fixed", "validator_tester_pending",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "validator_tester_pending")
                self.assertEqual(task.get("last_updated_by"), "debugger")

                _fire_subagent_stop("tester", _trailer(
                    "P00-S01-T001", "pass", "ready_for_close",
                ))
                task = common.find_task(common.load_registry(), "P00-S01-T001")
                self.assertEqual(task["status"], "ready_for_close")

                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 3)
        finally:
            td.cleanup()


# ---------------------------------------------------------------------------
# 4) Spawn budget — PreToolUse Agent denies the (budget+1)-th spawn
# ---------------------------------------------------------------------------
class SpawnBudgetChoreographyTests(unittest.TestCase):

    def test_21st_agent_call_is_denied_after_budget_completed_stops(self):
        """Use a small budget (5) for speed. After 5 SubagentStop, the 6th
        Agent call (PreToolUse) must return permissionDecision: deny with
        the active TASK_ID and the count in the message. Below the budget
        the hook produces no output — the absence of output is the
        permission `allow`."""
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                # Override budget to 5 for speed.
                state = common.load_runtime_state()
                state["spawn_budget"] = 5
                common.save_runtime_state(state)

                # Fire 5 stops without completing the task (status stays
                # in_progress so the slice keeps consuming budget).
                for _ in range(5):
                    _fire_subagent_stop("developer", _trailer(
                        "P00-S01-T001", "in_progress", "in_progress",
                    ))
                self.assertEqual(common.get_spawn_count("P00-S01-T001"), 5)

                # PreToolUse Agent — must DENY.
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
                output = buf.getvalue().strip()
                self.assertTrue(output, "hook must emit JSON when denying")
                decision = json.loads(output)
                self.assertEqual(
                    decision["hookSpecificOutput"]["permissionDecision"], "deny")
                msg = decision["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertIn("P00-S01-T001", msg)
                self.assertIn("5/5", msg)
        finally:
            td.cleanup()

    def test_under_budget_hook_produces_no_output(self):
        """At count < budget the hook is silent (Claude Code reads silence
        as `allow`). This is the path that runs ~20 times per slice — it
        must not print anything."""
        root, td = _setup_tmp_project()
        try:
            with _Sandbox(root):
                import common
                _seed_two_task_registry()
                state = common.load_runtime_state()
                state["spawn_budget"] = 5
                common.save_runtime_state(state)
                # Only 2 stops — well under the budget.
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
                self.assertEqual(buf.getvalue(), "",
                    "below-budget hook must be silent")
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
