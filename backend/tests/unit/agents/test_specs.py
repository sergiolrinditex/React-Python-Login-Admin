"""
Unit tests for AgentSpec and the JSON fixture loader.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Tests covered (8 cases):
  AgentSpec construction (3):
    1. Supervisor spec: agent_type='supervisor', topics=None.
    2. Subagent spec: agent_type='subagent', topics populated.
    3. Frozen dataclass: mutation raises FrozenInstanceError.

  load_specs_from_json — real fixture (4):
    4. Fixture loads without error; returns 3 AgentSpec objects.
    5. Exactly 1 supervisor (people-supervisor) in the fixture.
    6. Exactly 2 subagents (hr-policies-agent + langchain-docs-agent).
    7. hr-policies-agent has 'vacaciones' in subagent_topics.
    8. langchain-docs-agent has 'langchain' in subagent_topics.

  load_specs_from_json — error paths (2):
    9.  FileNotFoundError when path does not exist.
    10. ValueError when JSON has wrong shape (no 'agents' key).

Rules:
  - No mocking of AgentSeed validation — it is real.
  - No DB access.
  - Fixture data read from real data/verification/mcp_agents/agents.json.

Dependencies:
  - pytest 9.0.3
  - app.agents.specs (AgentSpec, load_specs_from_json)
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.agents.specs import AgentSpec, load_specs_from_json

_FIXTURE_PATH = Path(__file__).parents[4] / "data" / "verification" / "mcp_agents" / "agents.json"


# ---------------------------------------------------------------------------
# AgentSpec construction tests
# ---------------------------------------------------------------------------


def test_supervisor_spec_has_no_topics() -> None:
    """A supervisor AgentSpec can be constructed with subagent_topics=None."""
    spec = AgentSpec(
        name="people-supervisor",
        description="Test supervisor",
        agent_type="supervisor",
        framework="deepagents",
        parent_agent_name=None,
        subagent_topics=None,
        system_prompt="You are a supervisor.",
        model_id="stub/model",
    )
    assert spec.agent_type == "supervisor"
    assert spec.subagent_topics is None
    assert spec.parent_agent_name is None


def test_subagent_spec_has_topics() -> None:
    """A subagent AgentSpec carries a non-null subagent_topics list."""
    spec = AgentSpec(
        name="hr-agent",
        description="HR policies agent",
        agent_type="subagent",
        framework="deepagents",
        parent_agent_name="people-supervisor",
        subagent_topics=["vacaciones", "nominas"],
        system_prompt="You are an HR expert.",
        model_id="stub/model",
    )
    assert spec.agent_type == "subagent"
    assert spec.subagent_topics is not None
    assert "vacaciones" in spec.subagent_topics
    assert spec.parent_agent_name == "people-supervisor"


def test_agent_spec_is_frozen() -> None:
    """AgentSpec is a frozen dataclass — mutation raises FrozenInstanceError."""
    spec = AgentSpec(
        name="test",
        description="Test",
        agent_type="subagent",
        framework="deepagents",
        parent_agent_name="parent",
        subagent_topics=["topic1"],
        system_prompt="prompt",
        model_id="model",
    )
    with pytest.raises(FrozenInstanceError):
        spec.name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# load_specs_from_json — real fixture
# ---------------------------------------------------------------------------


def test_load_specs_from_json_returns_three_specs() -> None:
    """The real fixture loads 3 agent specs (1 supervisor + 2 subagents)."""
    specs = load_specs_from_json(_FIXTURE_PATH)
    assert len(specs) == 3


def test_load_specs_from_json_one_supervisor() -> None:
    """Exactly one supervisor is in the real fixture."""
    specs = load_specs_from_json(_FIXTURE_PATH)
    supervisors = [s for s in specs if s.agent_type == "supervisor"]
    assert len(supervisors) == 1
    assert supervisors[0].name == "people-supervisor"


def test_load_specs_from_json_two_subagents() -> None:
    """Exactly two subagents are in the real fixture."""
    specs = load_specs_from_json(_FIXTURE_PATH)
    subagents = [s for s in specs if s.agent_type == "subagent"]
    assert len(subagents) == 2
    names = {s.name for s in subagents}
    assert names == {"hr-policies-agent", "langchain-docs-agent"}


def test_hr_agent_topics_contain_vacaciones() -> None:
    """hr-policies-agent subagent_topics includes 'vacaciones'."""
    specs = load_specs_from_json(_FIXTURE_PATH)
    hr = next((s for s in specs if s.name == "hr-policies-agent"), None)
    assert hr is not None, "hr-policies-agent not found in fixture"
    assert hr.subagent_topics is not None
    assert "vacaciones" in hr.subagent_topics


def test_langchain_agent_topics_contain_langchain() -> None:
    """langchain-docs-agent subagent_topics includes 'langchain'."""
    specs = load_specs_from_json(_FIXTURE_PATH)
    lc = next((s for s in specs if s.name == "langchain-docs-agent"), None)
    assert lc is not None, "langchain-docs-agent not found in fixture"
    assert lc.subagent_topics is not None
    assert "langchain" in lc.subagent_topics


# ---------------------------------------------------------------------------
# load_specs_from_json — error paths
# ---------------------------------------------------------------------------


def test_load_specs_file_not_found_raises() -> None:
    """FileNotFoundError is raised when the fixture path does not exist."""
    with pytest.raises(FileNotFoundError):
        load_specs_from_json("/nonexistent/path/agents.json")


def test_load_specs_wrong_json_shape_raises() -> None:
    """ValueError is raised when the JSON lacks the 'agents' top-level key."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump({"wrong_key": []}, tf)
        tf_path = tf.name

    with pytest.raises(ValueError, match="must have top-level key 'agents'"):
        load_specs_from_json(tf_path)
