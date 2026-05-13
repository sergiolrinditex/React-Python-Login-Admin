from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_promote_followup_command_exists_and_is_safe() -> None:
    path = ROOT / ".claude/commands/promote-followup.md"
    text = path.read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert "# /promote-followup" in text
    assert "main-orchestrator" in text
    assert "claude --agent main-orchestrator --permission-mode bypassPermissions \"/promote-followup <FOLLOWUP_ID>\"" in text
    assert "PROMOTE <FOLLOWUP_ID>" in text
    assert "./scripts/register-followup-task.sh promote <FOLLOWUP_ID>" in text
    assert "./scripts/check-task-dag.sh --strict" in text
    assert "./scripts/check-journey-matrix.sh --strict" in text
    assert "./scripts/check-wiring-contract.sh --strict --require-new-template-columns" in text
    assert "closer` nunca ejecuta promote automáticamente" in text or "El `closer` nunca ejecuta promote automáticamente" in text
    # El bloque ampliado a 4 unsets: validamos cada línea por separado.
    assert "unset CLAUDE_ACTIVE_TASK_ID" in text
    assert "unset CLAUDE_TASK_PACK" in text
    assert "unset CLAUDE_WORKTREE_ROOT" in text
    assert "unset CLAUDE_ORCHESTRATOR_ROOT" in text


def test_followup_contract_points_to_safe_promote_command() -> None:
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    followups = contract["followup_tasks"]
    assert followups["promotion_command"] == 'claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"'
    assert followups["promotion_script"] == "./scripts/register-followup-task.sh promote <FOLLOWUP_ID>"
    assert "must not be called by closer automatically" in followups["promotion_policy"]


def test_followup_gates_recommend_promote_followup_command() -> None:
    paths = [
        ROOT / ".claude/commands/next-slice.md",
        ROOT / ".claude/commands/next-wave.md",
        ROOT / ".claude/agents/main-orchestrator.md",
        ROOT / ".claude/agents/planner.md",
        ROOT / ".claude/agents/closer.md",
        ROOT / "README.md",
        ROOT / "CHEATSHEET.md",
        ROOT / "docs/guides/CHEATSHEET.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "/promote-followup" in text, str(path)


def test_next_wave_blocking_followups_prints_main_orchestrator_command() -> None:
    text = (ROOT / ".claude/bin/next_wave.py").read_text(encoding="utf-8")
    assert 'claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"' in text
