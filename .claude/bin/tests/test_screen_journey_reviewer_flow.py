from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_screen_journey_reviewer_agent_is_info_only_contract_role() -> None:
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    role = contract["trailer_schema"]["roles"]["screen-journey-reviewer"]
    assert role["required_keys"] == ["TASK_ID", "OUTCOME"]
    assert role["outcome_values"] == ["approved", "changes_requested", "blocked"]
    assert role["next_status_values"] == []
    assert role["info_only"] is True
    assert role["mutates_registry_lifecycle"] is False
    assert role["info_only"] is True
    assert "outcome" + "_enums" not in contract
    assert "next_status" + "_enums" not in contract


def test_screen_journey_reviewer_prompt_has_visual_contract_and_no_lifecycle_status() -> None:
    text = (ROOT / ".claude/agents/screen-journey-reviewer.md").read_text(encoding="utf-8")
    assert "name: screen-journey-reviewer" in text
    assert "No implementas, no ejecutas cierre, no promocionas follow-ups" in text
    assert "HTML preview/docs visuales son referencia/evidencia, no source-of-truth" in text
    assert "VISUAL_CONTRACT_CHECK" in text
    assert "real_data_or_backend_used" in text
    assert "in_scope_defect" in text
    assert "why_not_debugger" in text
    assert "NEXT_STATUS:" not in "\n".join(
        line for line in text.splitlines() if line.strip().startswith("NEXT_STATUS:")
    )


def test_verify_slice_invokes_reviewer_only_for_screen_journey_context_before_closer() -> None:
    text = (ROOT / ".claude/commands/verify-slice.md").read_text(encoding="utf-8")
    assert "## Paso 5.2 — Screen/Journey review condicional antes de closer" in text
    assert "screen-journey-reviewer" in text
    assert "VISUAL_CONTRACT_CHECK" in text
    assert "HTML preview/docs visuales son referencia/evidencia, no source-of-truth" in text
    assert "--require-screen-journey-review" in text
    assert "OUTCOME: changes_requested" in text
    assert "debugger" in text
    assert "followup_candidate=yes" in text
    assert text.index("## Paso 5.2 — Screen/Journey review") < text.index("## Paso 5.bis — Journey-closing")
    assert text.index("## Paso 5.2 — Screen/Journey review") < text.index("## Paso 6 — Orquestación de cierre")


def test_closer_requires_screen_journey_review_when_applicable() -> None:
    text = (ROOT / ".claude/agents/closer.md").read_text(encoding="utf-8")
    assert "--require-screen-journey-review" in text
    assert "screen-journey-reviewer" in text
    assert "frontend/ux/journey/gate" in text
    assert "VISUAL_CONTRACT_CHECK" in text


def test_check_handoff_contract_requires_screen_journey_review(tmp_path: Path) -> None:
    handoff_dir = tmp_path / "orchestrator-state/tasks/handoffs"
    handoff_dir.mkdir(parents=True)
    (handoff_dir / "P00-S01-T001.md").write_text(
        "# Handoff\n\n"
        "## Validator review\n"
        "- TASK_ID: P00-S01-T001\n"
        "- OUTCOME: approved\n\n"
        "## Tester run\n"
        "- TASK_ID: P00-S01-T001\n"
        "- OUTCOME: pass\n\n"
        "## verify-slice\n"
        "- TASK_ID: P00-S01-T001\n"
        "- AGENT: slice-verifier\n"
        "- MODE: pre-closer\n"
        "- MCP_BROWSER: chrome-devtools\n"
        "- VERIFY_OUTCOME: verified\n"
        "- DATA_CONTRACT_ROWS: VDC-001\n"
        "- DATA_SETUP: sandbox-user-1 + seeded record A\n"
        "- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active\n"
        "- FLOWS_TESTED: login happy path\n"
        "- EVIDENCE: orchestrator-state/tasks/evidence/P00-S01-T001/verify-*\n\n"
        "## Screen/Journey review\n"
        "- TASK_ID: P00-S01-T001\n"
        "- OUTCOME: approved\n"
        "- visual_contract_checked: yes\n"
        "- required_states_covered: yes\n"
        "- real_data_or_backend_used: yes\n"
        "- visual_evidence_present: yes\n",
        encoding="utf-8",
    )
    script = ROOT / ".claude/bin/check_handoff_contract.py"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(script),
            "P00-S01-T001",
            "--require-ready-for-close",
            "--require-verify-slice",
            "--require-screen-journey-review",
        ],
        cwd=tmp_path,
        env={"CLAUDE_ORCHESTRATOR_ROOT": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout

    text = (handoff_dir / "P00-S01-T001.md").read_text(encoding="utf-8")
    (handoff_dir / "P00-S01-T001.md").write_text(text.replace("- OUTCOME: approved\n- visual_contract_checked", "- OUTCOME: changes_requested\n- visual_contract_checked"), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(script),
            "P00-S01-T001",
            "--require-ready-for-close",
            "--require-verify-slice",
            "--require-screen-journey-review",
        ],
        cwd=tmp_path,
        env={"CLAUDE_ORCHESTRATOR_ROOT": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "screen/journey reviewer did not approve" in proc.stderr
