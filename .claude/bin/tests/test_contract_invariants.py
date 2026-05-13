from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_trailer_schema_is_single_enum_source():
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    roles = contract["trailer_schema"]["roles"]
    assert roles, "trailer_schema.roles must exist"
    assert "outcome" + "_enums" not in contract
    assert "next_status" + "_enums" not in contract
    assert "outcome" + "_enums_source" not in contract
    assert "next_status" + "_enums_source" not in contract
    for role, spec in roles.items():
        assert isinstance(spec.get("outcome_values"), list), f"{role} missing outcome_values list"
        assert isinstance(spec.get("next_status_values"), list), f"{role} missing next_status_values list"


def test_trailer_agent_classes_are_derived_from_schema_only():
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    trailers = contract.get("trailers", {})
    assert "lifecycle_agents" not in trailers
    assert "info_only_agents" not in trailers
    roles = contract["trailer_schema"]["roles"]
    lifecycle = {role for role, spec in roles.items() if spec.get("mutates_registry_lifecycle")}
    info_only = {role for role, spec in roles.items() if spec.get("info_only")}
    assert "developer" in lifecycle
    assert "tester" in lifecycle
    assert "closer" in lifecycle
    assert "validator" in info_only
    assert "screen-journey-reviewer" in info_only


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
