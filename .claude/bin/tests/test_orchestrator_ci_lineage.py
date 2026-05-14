"""
Orchestrator CI lineage sentinel (P02-S05-T004).

Pins the 7 unit-test cases that PR #17 (commit 8e52ed3, mergedAt 2026-05-13T21:13:24Z)
restored to green on the 'Orchestrator tests' workflow. If any of these regress,
this sentinel fails, making the regression explicit in CI and during local runs.

Slice: P02-S05-T004 (Runtime follow-up from FU-20260513210148)
Phase: P02 -- Core Features (orchestrator-internal)
Dependencies: .claude/bin/tests/test_journey_state.py,
              .claude/bin/tests/test_stack_profile_contract.py

Acceptance lineage (FU-20260513210148 -> P02-S05-T004):
    - test_journey_state.py (x5):
        test_add_pending_is_idempotent
        test_add_pending_preserves_order_for_multiple
        test_waive_records_reason
        test_hook_integration_closer_emits_pending
        test_hook_integration_issues_found_keeps_pending
    - test_stack_profile_contract.py (x2):
        test_git_workflow_direct_main_alias_pushes_to_main
        test_git_workflow_amends_late_ledger_before_push
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

LOGGER = logging.getLogger("orchestrator.ci_lineage_sentinel")

# Resolve the repo root from this file location (.claude/bin/tests/ -> repo root).
REPO = Path(__file__).resolve().parents[3]

# Pytest node IDs for the 7 anchor tests pinned by PR #17.
_PINNED: tuple[str, ...] = (
    ".claude/bin/tests/test_journey_state.py::test_add_pending_is_idempotent",
    ".claude/bin/tests/test_journey_state.py::test_add_pending_preserves_order_for_multiple",
    ".claude/bin/tests/test_journey_state.py::test_waive_records_reason",
    ".claude/bin/tests/test_journey_state.py::test_hook_integration_closer_emits_pending",
    ".claude/bin/tests/test_journey_state.py::test_hook_integration_issues_found_keeps_pending",
    ".claude/bin/tests/test_stack_profile_contract.py::test_git_workflow_direct_main_alias_pushes_to_main",
    ".claude/bin/tests/test_stack_profile_contract.py::test_git_workflow_amends_late_ledger_before_push",
)


def test_pr17_anchor_tests_still_pass() -> None:
    """Re-runs the 7 PR #17 anchor tests via subprocess pytest.

    Purpose: any future revert of the PR #17 fix surfaces here before
    reaching CI.  Uses subprocess so the runner state is isolated.

    Args: none (pytest-style function).
    Returns: None -- asserts on returncode.
    Raises: AssertionError if any anchor test fails or errors.
    """
    LOGGER.info(
        "ci_lineage.before pinned_count=%d repo=%s",
        len(_PINNED),
        REPO,
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=short", *_PINNED],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )
    LOGGER.info(
        "ci_lineage.after returncode=%d stdout_tail=%r",
        result.returncode,
        result.stdout[-400:] if result.stdout else "",
    )
    if result.returncode != 0:
        LOGGER.error(
            "ci_lineage.error PR #17 anchors regressed returncode=%d",
            result.returncode,
        )
        raise AssertionError(
            "PR #17 orchestrator-CI anchor tests regressed.\n"
            "stdout:\n" + result.stdout + "\nstderr:\n" + result.stderr
        )
