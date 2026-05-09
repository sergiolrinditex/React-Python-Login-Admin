"""
Unit tests for the keyword-overlap routing algorithm.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Tests covered (10 cases):
  1.  Single-token exact match → correct subagent selected.
  2.  Multi-token match → higher-scoring subagent selected.
  3.  No overlap → fallback (selected_subagent=None, fallback_used=True).
  4.  Empty message → fallback.
  5.  Empty subagent list → fallback.
  6.  Tie-break: equal score, prefer larger topic list.
  7.  Tie-break: equal score AND equal topic length → prefer alphabetically first name.
  8.  Score > 0 but one subagent has empty topics → skipped correctly.
  9.  Real fixture: "vacaciones" → hr-policies-agent (verification command #1).
  10. Real fixture: "langchain" → langchain-docs-agent (verification command #2).

Rules:
  - No mocking. Pure stdlib + dataclasses.
  - AgentSpec constructed directly (no DB, no JSON I/O).
  - Fixture-based tests load real data from data/verification/mcp_agents/agents.json.

Dependencies:
  - pytest 9.0.3
  - app.agents.routing (select_subagent, RoutingDecision)
  - app.agents.specs (AgentSpec, load_specs_from_json)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.routing import select_subagent
from app.agents.specs import AgentSpec, load_specs_from_json

# ---------------------------------------------------------------------------
# Helpers — minimal AgentSpec construction
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parents[4] / "data" / "verification" / "mcp_agents" / "agents.json"


def _make_spec(name: str, topics: list[str] | None) -> AgentSpec:
    """Build a minimal AgentSpec for testing."""
    return AgentSpec(
        name=name,
        description=f"Test agent {name}",
        agent_type="subagent",
        framework="deepagents",
        parent_agent_name="test-supervisor",
        subagent_topics=topics,
        system_prompt="You are a test agent.",
        model_id="stub/model",
    )


# ---------------------------------------------------------------------------
# Basic routing tests
# ---------------------------------------------------------------------------


def test_single_token_match_selects_correct_agent() -> None:
    """A message containing one topic keyword routes to the matching agent."""
    agents = [
        _make_spec("hr-agent", ["vacaciones", "nominas"]),
        _make_spec("tech-agent", ["langchain", "python"]),
    ]
    decision = select_subagent("¿Cuántos días de vacaciones tengo?", agents)
    assert decision.selected_subagent == "hr-agent"
    assert decision.score == 1
    assert "vacaciones" in decision.matched_topics
    assert not decision.fallback_used


def test_multi_token_match_selects_higher_score() -> None:
    """The agent with more matching tokens wins."""
    agents = [
        _make_spec("hr-agent", ["vacaciones", "nominas"]),
        _make_spec("tech-agent", ["langchain", "langgraph", "python"]),
    ]
    decision = select_subagent("langchain langgraph tutorial for beginners", agents)
    assert decision.selected_subagent == "tech-agent"
    assert decision.score == 2
    assert not decision.fallback_used


def test_no_overlap_returns_fallback() -> None:
    """A message with no overlap with any topic returns fallback decision."""
    agents = [
        _make_spec("hr-agent", ["vacaciones", "nominas"]),
        _make_spec("tech-agent", ["langchain", "python"]),
    ]
    decision = select_subagent("hola, ¿qué tiempo hace hoy?", agents)
    assert decision.selected_subagent is None
    assert decision.score == 0
    assert decision.matched_topics == []
    assert decision.fallback_used


def test_empty_message_returns_fallback() -> None:
    """An empty message string always returns fallback."""
    agents = [_make_spec("hr-agent", ["vacaciones"])]
    decision = select_subagent("", agents)
    assert decision.fallback_used
    assert decision.selected_subagent is None
    assert decision.score == 0


def test_empty_subagent_list_returns_fallback() -> None:
    """An empty subagent list always returns fallback."""
    decision = select_subagent("vacaciones y nominas", [])
    assert decision.fallback_used
    assert decision.selected_subagent is None


def test_tiebreak_prefers_larger_topic_list() -> None:
    """When two agents tie on score, the one with more topics wins.

    Tie-break rule: prefer larger len(subagent_topics) (broader coverage).
    """
    agents = [
        _make_spec("narrow-agent", ["langchain"]),  # 1 topic
        _make_spec("broad-agent", ["langchain", "python", "rag"]),  # 3 topics
    ]
    # Both match "langchain" → score=1, tie-break on topic count.
    decision = select_subagent("how does langchain work?", agents)
    assert decision.selected_subagent == "broad-agent"
    assert decision.score == 1


def test_tiebreak_same_topic_count_prefers_alphabetical_first() -> None:
    """When score and topic count are equal, alphabetical name wins."""
    agents = [
        _make_spec("zebra-agent", ["langchain"]),
        _make_spec("alpha-agent", ["langchain"]),
    ]
    decision = select_subagent("langchain question", agents)
    assert decision.selected_subagent == "alpha-agent"


def test_subagent_with_empty_topics_is_skipped() -> None:
    """An agent with None or empty subagent_topics is never selected."""
    agents = [
        _make_spec("empty-agent", None),  # no topics → always skipped
        _make_spec("hr-agent", ["vacaciones"]),
    ]
    decision = select_subagent("vacaciones anuales", agents)
    assert decision.selected_subagent == "hr-agent"
    assert not decision.fallback_used


# ---------------------------------------------------------------------------
# Real-fixture verification tests (verification commands from registry)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_subagents() -> list[AgentSpec]:
    """Load subagent specs from the real productive fixture."""
    specs = load_specs_from_json(_FIXTURE_PATH)
    return [s for s in specs if s.agent_type == "subagent"]


def test_vacaciones_routes_to_hr_policies_agent(real_subagents: list[AgentSpec]) -> None:
    """Verification command #1: 'vacaciones' routes to hr-policies-agent.

    Registry acceptance: "user asks vacaciones question → supervisor routes
    to hr-policies-agent → returns answer".
    """
    decision = select_subagent("¿cuántos días de vacaciones tengo?", real_subagents)
    assert decision.selected_subagent == "hr-policies-agent", (
        f"Expected 'hr-policies-agent', got {decision.selected_subagent!r}. "
        f"Score={decision.score}, matched={decision.matched_topics}"
    )
    assert not decision.fallback_used
    assert "vacaciones" in decision.matched_topics


def test_langchain_routes_to_langchain_docs_agent(real_subagents: list[AgentSpec]) -> None:
    """Verification command #2: 'langchain' routes to langchain-docs-agent.

    Registry acceptance: "user asks langchain question → routes to
    langchain-docs-agent".
    """
    decision = select_subagent("how do I use langchain for my project?", real_subagents)
    assert decision.selected_subagent == "langchain-docs-agent", (
        f"Expected 'langchain-docs-agent', got {decision.selected_subagent!r}. "
        f"Score={decision.score}, matched={decision.matched_topics}"
    )
    assert not decision.fallback_used
    assert "langchain" in decision.matched_topics
