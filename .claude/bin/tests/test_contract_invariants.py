from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_trailer_schema_matches_outcome_enums_mirror():
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    schema_outcomes = {
        role: set(spec.get("outcome_values", []))
        for role, spec in contract["trailer_schema"]["roles"].items()
    }
    mirror_outcomes = {
        role: set(values)
        for role, values in contract["outcome_enums"].items()
    }
    assert schema_outcomes == mirror_outcomes, (
        f"trailer_schema y outcome_enums divergen: "
        f"schema={schema_outcomes} mirror={mirror_outcomes}"
    )


def test_trailer_schema_matches_next_status_enums_mirror():
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    schema_statuses = {
        role: set(spec.get("next_status_values", []))
        for role, spec in contract["trailer_schema"]["roles"].items()
    }
    mirror_statuses = {
        role: set(values)
        for role, values in contract["next_status_enums"].items()
    }
    assert schema_statuses == mirror_statuses, (
        f"trailer_schema y next_status_enums divergen: "
        f"schema={schema_statuses} mirror={mirror_statuses}"
    )


def test_agent_prompts_reference_existing_schema_roles():
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    valid_roles = set(contract["trailer_schema"]["roles"].keys())
    for agent_path in (ROOT / ".claude/agents").glob("*.md"):
        text = agent_path.read_text(encoding="utf-8")
        for m in re.finditer(r"trailer_schema\.roles\.([\w-]+)", text):
            assert m.group(1) in valid_roles, f"{agent_path.name} cita rol inexistente: {m.group(1)}"


def test_claude_md_agent_count_matches_filesystem():
    claude_md = (ROOT / ".claude/CLAUDE.md").read_text(encoding="utf-8")
    declared = int(re.search(r"Total:\s*(\d+)\s*agents", claude_md).group(1))
    actual = len(list((ROOT / ".claude/agents").glob("*.md")))
    assert declared == actual, f"CLAUDE.md dice {declared} agentes, hay {actual} ficheros"
