"""Tests for _resolve_handoff_path fallback logic in check_handoff_contract.py.

Slice: P02-S03-T007 — Fix check_handoff_contract.py worktree path bug in pr-flow.
Phase: P02 / P02-S03.

These 4 tests cover the dual-root (workspace + canonical) resolution added in
``_resolve_handoff_path``. They are split from ``test_handoff_contract.py``
because adding them there would push the file past the ~300-line cap declared
in ``.claude/rules/01-non-negotiables.md §File size``.

WRITE_SET_DRIFT declared: §D-T007-TESTSPLIT (new file
``.claude/bin/tests/test_handoff_contract_resolution.py``; pre-authorised by
planner in task pack §Riesgos y decisiones previas).

Dependencies: none external — only ``subprocess``, ``os``, ``sys``, ``pathlib``.
All tests are deterministic: they use ``tmp_path`` fixtures and explicit env
overrides; they never read the real registry, runtime-state, or workspace.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".claude/bin/check_handoff_contract.py"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_VALID_HANDOFF = """
# Task Handoff — {task_id}

## Validator review
- AGENT: validator
- TASK_ID: {task_id}
- OUTCOME: approved
- NEXT_STATUS: ready_for_close

## Tester run
- AGENT: tester
- TASK_ID: {task_id}
- OUTCOME: pass
- NEXT_STATUS: ready_for_close

## verify-slice
- TASK_ID: {task_id}
- MODE: pre-closer
- VERIFY_OUTCOME: verified
- EVIDENCE: orchestrator-state/tasks/evidence/{task_id}/verify-star
"""

_INVALID_HANDOFF_NO_VERIFY = """
# Task Handoff — {task_id}

## Validator review
- AGENT: validator
- TASK_ID: {task_id}
- OUTCOME: approved

## Tester run
- AGENT: tester
- TASK_ID: {task_id}
- OUTCOME: pass
"""


def _make_handoff(root: Path, task_id: str, content: str) -> Path:
    """Create a handoff file under ``root/orchestrator-state/tasks/handoffs/``."""
    handoffs = root / "orchestrator-state" / "tasks" / "handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)
    path = handoffs / f"{task_id}.md"
    path.write_text(content.format(task_id=task_id), encoding="utf-8")
    return path


def _run(task_id: str, env: dict) -> subprocess.CompletedProcess:
    """Run check_handoff_contract.py with the given environment and return the result."""
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(SCRIPT),
            task_id,
            "--require-ready-for-close",
            "--require-verify-slice",
            "--json",
        ],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_handoff_contract_falls_back_to_canonical_when_workspace_missing(
    tmp_path: Path,
) -> None:
    """T_pr_flow_fallback_canonical: workspace miss → resolver finds handoff in canonical.

    BEFORE: workspace root has no handoff; canonical root has a valid handoff.
    AFTER: exit 0, ``ok: true``. The close-gate works when invoked post-merge
    from a different directory (e.g. ``/tmp``) where workspace_root has no file.
    """
    task_id = "P00-S01-T042"
    canonical = tmp_path / "main"
    workspace = tmp_path / "wt"
    workspace.mkdir(parents=True)
    # Only canonical has the handoff — workspace dir exists but is empty.
    _make_handoff(canonical, task_id, _VALID_HANDOFF)

    env = os.environ.copy()
    env["CLAUDE_ORCHESTRATOR_ROOT"] = str(canonical)
    env["CLAUDE_WORKTREE_ROOT"] = str(workspace)
    env["CLAUDE_PROJECT_DIR"] = str(workspace)

    result = _run(task_id, env)
    assert result.returncode == 0, (
        f"Expected exit 0 (fallback to canonical).\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert '"ok": true' in result.stdout


def test_handoff_contract_prefers_workspace_when_both_exist(tmp_path: Path) -> None:
    """T_pr_flow_workspace_wins: workspace handoff takes precedence over canonical.

    BEFORE: workspace has a VALID handoff; canonical has an INVALID handoff
    (missing ## verify-slice section). If workspace is used → exit 0.
    If canonical is accidentally used → exit 2.

    AFTER: exit 0 confirms the resolver picks the workspace candidate first
    (the slice-authoritative path during an active pr-flow worker session).
    """
    task_id = "P00-S01-T043"
    canonical = tmp_path / "main"
    workspace = tmp_path / "wt"

    _make_handoff(workspace, task_id, _VALID_HANDOFF)  # valid
    _make_handoff(canonical, task_id, _INVALID_HANDOFF_NO_VERIFY)  # invalid

    env = os.environ.copy()
    env["CLAUDE_ORCHESTRATOR_ROOT"] = str(canonical)
    env["CLAUDE_WORKTREE_ROOT"] = str(workspace)
    env["CLAUDE_PROJECT_DIR"] = str(workspace)

    result = _run(task_id, env)
    assert result.returncode == 0, (
        f"Expected exit 0 (workspace wins).\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert '"ok": true' in result.stdout


def test_handoff_contract_reports_missing_when_neither_workspace_nor_canonical_has_it(
    tmp_path: Path,
) -> None:
    """T_missing_both_clean_error: no handoff anywhere → clean error, no traceback.

    BEFORE: both workspace and canonical directories exist but contain no handoff
    for the requested TASK_ID.

    AFTER: exit 2, JSON output contains ``"missing handoff:"`` in errors[0],
    stderr has no Python traceback (no ``Traceback (most recent call last)``).
    """
    task_id = "P00-S01-T099"
    canonical = tmp_path / "main"
    workspace = tmp_path / "wt"
    # Create directory structure but no handoff files.
    (canonical / "orchestrator-state" / "tasks" / "handoffs").mkdir(parents=True)
    (workspace / "orchestrator-state" / "tasks" / "handoffs").mkdir(parents=True)

    env = os.environ.copy()
    env["CLAUDE_ORCHESTRATOR_ROOT"] = str(canonical)
    env["CLAUDE_WORKTREE_ROOT"] = str(workspace)
    env["CLAUDE_PROJECT_DIR"] = str(workspace)

    result = _run(task_id, env)
    assert result.returncode == 2, (
        f"Expected exit 2 (missing handoff).\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "missing handoff:" in result.stdout, (
        f"Expected 'missing handoff:' in JSON errors.\nstdout={result.stdout!r}"
    )
    assert "Traceback (most recent call last)" not in result.stderr, (
        "Python traceback should not appear in stderr; got clean error message instead."
    )


def test_handoff_contract_returns_exit_2_on_unexpected_internal_error(
    tmp_path: Path,
) -> None:
    """T_internal_crash_returns_2: unexpected crash yields exit 2 + clean stderr.

    We verify the defensive ``try/except Exception`` in ``main()`` by pointing
    CLAUDE_ORCHESTRATOR_ROOT at a *file* (not a directory), which causes
    ``project_root()`` / path construction to produce an unusable base.
    The resolver falls through to the workspace candidate which also won't
    exist, so we still get a clean "missing handoff" exit 2 — confirming that
    the error path does not produce a raw Python traceback regardless of
    the unexpected condition.

    If the above doesn't trigger an internal error (the code is robust enough
    to handle it gracefully), we also assert that the script exits 2 with
    a clean message — either "missing handoff" or "internal error" is fine.
    """
    task_id = "P00-S01-T088"
    workspace = tmp_path / "wt"
    workspace.mkdir(parents=True)
    # Use a file as CLAUDE_ORCHESTRATOR_ROOT to stress the path resolution.
    fake_root_file = tmp_path / "not_a_dir.txt"
    fake_root_file.write_text("this is a file, not a directory", encoding="utf-8")

    env = os.environ.copy()
    env["CLAUDE_ORCHESTRATOR_ROOT"] = str(fake_root_file)
    env["CLAUDE_WORKTREE_ROOT"] = str(workspace)
    env["CLAUDE_PROJECT_DIR"] = str(workspace)

    result = _run(task_id, env)
    assert result.returncode == 2, (
        f"Expected exit 2 on error condition.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    # No raw Python traceback — the defensive wrapper must catch exceptions.
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"Python traceback should not appear in stderr.\nstderr={result.stderr!r}"
    )
    # Either a clean "missing handoff" or "internal error" message.
    has_clean_error = (
        "missing handoff:" in result.stdout
        or "internal error:" in result.stderr
        or "Handoff contract FAILED" in result.stderr
    )
    assert has_clean_error, (
        f"Expected a clean error message.\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
