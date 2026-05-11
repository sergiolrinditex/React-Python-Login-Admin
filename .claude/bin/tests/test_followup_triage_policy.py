from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_followup_script_enforces_triage_terms() -> None:
    text = (ROOT / ".claude/bin/register_followup_task.py").read_text(encoding="utf-8")
    assert "FOLLOWUP_SCOPE_CLASSIFICATIONS" in text
    assert "in_scope_defect" in text
    assert "Refusing follow-up proposal classified as in_scope_defect" in text
    assert "blocking follow-up proposals require --why-not-debugger" in text


def test_agents_distinguish_debugger_retest_from_followup() -> None:
    required = {
        ".claude/agents/main-orchestrator.md": ["FU no es un escape para bugs", "debugger -> retest"],
        ".claude/agents/planner.md": ["Follow-up triage gate", "no crea FU por bugs de implementación"],
        ".claude/agents/validator.md": ["In-scope defect", "No crees FU", "--why-not-debugger"],
        ".claude/agents/tester.md": ["In-scope defect", "No crees FU", "--why-not-debugger"],
        ".claude/agents/debugger.md": ["No crees FU para evitar un fix posible", "--why-not-debugger"],
        ".claude/agents/closer.md": ["El closer nunca ejecuta `promote` automáticamente"],
    }
    for rel, needles in required.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text, f"{rel} missing {needle!r}"


def test_commands_and_docs_require_followup_triage() -> None:
    paths = [
        ".claude/commands/register-followup.md",
        ".claude/commands/promote-followup.md",
        ".claude/commands/verify-slice.md",
        ".claude/commands/next-slice.md",
        ".claude/rules/05-runtime-write-contract.md",
        "README.md",
        "CHEATSHEET.md",
        "docs/guides/CHEATSHEET.md",
    ]
    for rel in paths:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "--scope-classification" in text, rel
        assert "--why-not-debugger" in text or rel.endswith("next-slice.md"), rel
    cheat = (ROOT / "CHEATSHEET.md").read_text(encoding="utf-8")
    assert "Defecto dentro del TASK_ID -> debugger/retest, NO FU." in cheat


def test_contract_declares_followup_triage_policy() -> None:
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    followups = contract["followup_tasks"]
    assert followups["rejected_scope_classification"] == "in_scope_defect"
    assert "why debugger cannot fix" in followups["triage_policy"] or "debugger" in followups["triage_policy"]
    assert "missing_real_data" in followups["scope_classifications"]
