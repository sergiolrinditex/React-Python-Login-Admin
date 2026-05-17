from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_planner_records_stale_worktree_and_fu_path_drift_lessons() -> None:
    planner = _text(".claude/agents/planner.md")
    assert "Promoted FU path drift" in planner
    assert "find" in planner and "grep" in planner
    assert "stale_worktree_dep_missing" in planner
    assert "must not auto-rebase" in planner
    assert "list_journey_closures.py" in planner


def test_validator_keeps_fu_triage_authority_in_main_orchestrator() -> None:
    validator = _text(".claude/agents/validator.md")
    assert "missing_coverage" in validator
    assert "duplicate_of_done" in validator
    assert "Validator es paralelo/info-only" in validator
    assert "response code is outside frontend write_set" in validator


def test_shared_file_browser_gate_is_documented_and_contractual() -> None:
    developer = _text(".claude/agents/developer.md")
    rules = _text(".claude/rules/02-phase-execution.md")
    checker = _text(".claude/bin/check_handoff_contract.py")
    assert "SHARED_FILE_GUARD: checked" in developer
    assert "errors.ts" in developer and "auth/MFA/ForgotPassword" in developer
    assert "Shared frontend/domain files" in rules
    assert "auto verify-slice is not allowed" in checker


def test_orchestrator_contract_has_learned_triage_rules() -> None:
    contract = json.loads(_text(".claude/orchestrator-contract.json"))
    learned = "\n".join(contract["followup_tasks"].get("learned_triage_rules", []))
    assert "out-of-write_set sibling bug" in learned
    assert "duplicate FU" in learned
    assert "find/grep" in learned
    assert "shared_file_browser_gate" in contract["verification"]
