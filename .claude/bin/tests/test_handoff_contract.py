from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(tmp_path: Path, handoff_text: str, task_id: str = "P00-S01-T001"):
    handoffs = tmp_path / "orchestrator-state" / "tasks" / "handoffs"
    handoffs.mkdir(parents=True)
    (handoffs / f"{task_id}.md").write_text(handoff_text, encoding="utf-8")
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / ".claude/bin/check_handoff_contract.py"),
            task_id,
            "--require-ready-for-close",
            "--require-verify-slice",
            "--json",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_handoff_contract_accepts_canonical_sections(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## Developer run
- AGENT: developer
- TASK_ID: {task_id}
- OUTCOME: success
- NEXT_STATUS: validator_tester_pending

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
- EVIDENCE: orchestrator-state/tasks/evidence/{task_id}/verify-*
""",
        task_id,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"ok": true' in result.stdout


def test_handoff_contract_accepts_cycle_alias_sections(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## validator
- AGENT: validator
- TASK_ID: {task_id}
- OUTCOME: changes_requested

## validator (cycle 2)
- AGENT: validator
- TASK_ID: {task_id}
- OUTCOME: approved

## tester
- AGENT: tester
- TASK_ID: {task_id}
- OUTCOME: fail

## tester (cycle 2)
- AGENT: tester
- TASK_ID: {task_id}
- OUTCOME: pass

## verify slice
- TASK_ID: {task_id}
- VERIFY_OUTCOME: verified
""",
        task_id,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_handoff_contract_uses_workspace_path_when_worktree_differs_from_canonical(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    canonical = tmp_path / "main"
    workspace = tmp_path / "wt"
    handoffs = workspace / "orchestrator-state" / "tasks" / "handoffs"
    handoffs.mkdir(parents=True)
    (handoffs / f"{task_id}.md").write_text(
        f"""
# Task Handoff — {task_id}

## Validator review
- TASK_ID: {task_id}
- OUTCOME: approved

## Tester run
- TASK_ID: {task_id}
- OUTCOME: pass

## verify-slice
- TASK_ID: {task_id}
- VERIFY_OUTCOME: verified
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["CLAUDE_ORCHESTRATOR_ROOT"] = str(canonical)
    env["CLAUDE_PROJECT_DIR"] = str(workspace)
    env["CLAUDE_WORKTREE_ROOT"] = str(workspace)
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / ".claude/bin/check_handoff_contract.py"),
            task_id,
            "--require-ready-for-close",
            "--require-verify-slice",
            "--json",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"handoff": "orchestrator-state/tasks/handoffs/P00-S01-T001.md"' in result.stdout


def test_handoff_contract_rejects_missing_validator_tester_outcomes(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## Validator review
- scope: OK

## Tester run
- tests_backend: 10 pass

## verify-slice
- TASK_ID: {task_id}
- VERIFY_OUTCOME: verified
""",
        task_id,
    )
    assert result.returncode == 2
    assert "missing Validator review OUTCOME" in result.stdout
    assert "missing Tester run OUTCOME" in result.stdout


def test_handoff_contract_rejects_verify_task_id_mismatch(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## Validator review
- OUTCOME: approved

## Tester run
- OUTCOME: pass

## verify-slice
- TASK_ID: P99-S99-T999
- VERIFY_OUTCOME: verified
""",
        task_id,
    )
    assert result.returncode == 2
    assert "TASK_ID lines for another task" in result.stdout or "TASK_ID mismatch" in result.stdout


def test_verify_slice_and_closer_reference_mechanical_handoff_check() -> None:
    verify = (ROOT / ".claude/commands/verify-slice.md").read_text(encoding="utf-8")
    closer = (ROOT / ".claude/agents/closer.md").read_text(encoding="utf-8")
    assert "./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice" in verify
    assert "./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice" in closer
    assert "el handoff debe contener resultado machine-readable" in closer


def test_validator_and_tester_prompts_require_handoff_outcome_lines() -> None:
    validator = (ROOT / ".claude/agents/validator.md").read_text(encoding="utf-8")
    tester = (ROOT / ".claude/agents/tester.md").read_text(encoding="utf-8")
    assert "El `closer` lee estas líneas, no el chat trailer" in validator
    assert "- OUTCOME: approved|changes_requested|blocked" in validator
    assert "El `closer` lee estas líneas, no el chat trailer" in tester
    assert "- OUTCOME: pass|fail|blocked" in tester


def test_handoff_contract_rejects_unregistered_followup_candidate(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
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
- VERIFY_OUTCOME: verified
- followup_candidate: yes
- scope_classification: missing_real_data
- why_not_debugger: requires provided verification data outside this task
""",
        task_id,
    )
    assert result.returncode == 2
    assert "no formal FOLLOWUP_ID" in result.stdout


def test_handoff_contract_accepts_registered_followup_candidate(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
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
- VERIFY_OUTCOME: verified
- followup_candidate: yes
- FOLLOWUP_ID: FU-TEST-001
- scope_classification: missing_real_data
- why_not_debugger: requires provided verification data outside this task
""",
        task_id,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_handoff_contract_rejects_stale_verify_after_debugger_cycle(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## Validator review
- TASK_ID: {task_id}
- OUTCOME: approved

## Tester run
- TASK_ID: {task_id}
- OUTCOME: pass

## verify-slice
- TASK_ID: {task_id}
- VERIFY_OUTCOME: verified

## Debugger fix
- TASK_ID: {task_id}
- OUTCOME: fixed
- NEXT_STATUS: validator_tester_pending

## validator (cycle 2)
- TASK_ID: {task_id}
- OUTCOME: approved

## tester (cycle 2)
- TASK_ID: {task_id}
- OUTCOME: pass
""",
        task_id,
    )
    assert result.returncode == 2
    assert "stale verify-slice" in result.stdout


def test_handoff_contract_accepts_verify_after_debugger_retest(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## Validator review
- TASK_ID: {task_id}
- OUTCOME: changes_requested

## Tester run
- TASK_ID: {task_id}
- OUTCOME: fail

## Debugger fix
- TASK_ID: {task_id}
- OUTCOME: fixed
- NEXT_STATUS: validator_tester_pending

## validator (cycle 2)
- TASK_ID: {task_id}
- OUTCOME: approved

## tester (cycle 2)
- TASK_ID: {task_id}
- OUTCOME: pass

## verify-slice
- TASK_ID: {task_id}
- VERIFY_OUTCOME: verified
""",
        task_id,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_handoff_contract_accepts_slice_verifier_heading_alias(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## Validator review
- TASK_ID: {task_id}
- OUTCOME: approved

## Tester run
- TASK_ID: {task_id}
- OUTCOME: pass

## slice-verifier (cycle 2)
- TASK_ID: {task_id}
- VERIFY_OUTCOME: verified
""",
        task_id,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_handoff_contract_treats_blocked_verify_as_valid_but_not_closeable(tmp_path: Path) -> None:
    task_id = "P00-S01-T001"
    result = _run(
        tmp_path,
        f"""
# Task Handoff — {task_id}

## Validator review
- TASK_ID: {task_id}
- OUTCOME: approved

## Tester run
- TASK_ID: {task_id}
- OUTCOME: pass

## verify-slice
- TASK_ID: {task_id}
- VERIFY_OUTCOME: blocked
- BLOCKER_REASON: browser_mcp_unavailable
""",
        task_id,
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "verify-slice not verified" in output
    assert "invalid verify-slice VERIFY_OUTCOME" not in output
