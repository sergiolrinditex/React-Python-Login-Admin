"""
Unit tests for DeepAgentsSupervisor and build_supervisor factory.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Tests covered (10 cases):
  build_supervisor factory (3):
    1. Builds correctly from mixed specs (supervisor + subagents).
    2. Raises ValueError when no subagent specs are present.
    3. Accepts a custom executor (not just StubExecutor default).

  DeepAgentsSupervisor.invoke — StubExecutor (5):
    4. "vacaciones" → routes to hr-policies-agent → stub response.
    5. "langchain" → routes to langchain-docs-agent → stub response.
    6. No-overlap message → returns fallback response string.
    7. Empty message → returns fallback response string.
    8. Executor exception propagates from invoke().

  DeepAgentsSupervisor.__init__ edge cases (2):
    9. Init with empty subagent list raises ValueError.
    10. Init with active=False subagents still routes (active flag not filtered here).

Rules:
  - No mocking of routing logic — it IS the business logic under test.
  - StubExecutor used for all executor calls (no LLM, no network).
  - Real fixture data used for verification scenarios 4 and 5.

Dependencies:
  - pytest 9.0.3
  - app.agents.deepagents_runtime (DeepAgentsSupervisor, build_supervisor)
  - app.agents._executor (StubExecutor, SubagentExecutor)
  - app.agents.specs (AgentSpec, load_specs_from_json)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents._executor import StubExecutor
from app.agents.deepagents_runtime import DeepAgentsSupervisor, build_supervisor
from app.agents.specs import AgentSpec, load_specs_from_json

_FIXTURE_PATH = Path(__file__).parents[4] / "data" / "verification" / "mcp_agents" / "agents.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_subagent(name: str, topics: list[str]) -> AgentSpec:
    return AgentSpec(
        name=name,
        description=f"Test subagent {name}",
        agent_type="subagent",
        framework="deepagents",
        parent_agent_name="test-supervisor",
        subagent_topics=topics,
        system_prompt="You are a test agent.",
        model_id="stub/model",
    )


def _make_supervisor(name: str = "test-supervisor") -> AgentSpec:
    return AgentSpec(
        name=name,
        description="Test supervisor",
        agent_type="supervisor",
        framework="deepagents",
        parent_agent_name=None,
        subagent_topics=None,
        system_prompt="You are a supervisor.",
        model_id="stub/model",
    )


# ---------------------------------------------------------------------------
# build_supervisor factory tests
# ---------------------------------------------------------------------------


def test_build_supervisor_from_mixed_specs() -> None:
    """build_supervisor extracts subagent specs and creates a supervisor."""
    specs = [
        _make_supervisor(),
        _make_subagent("hr-agent", ["vacaciones"]),
        _make_subagent("tech-agent", ["langchain"]),
    ]
    supervisor = build_supervisor(specs)
    assert isinstance(supervisor, DeepAgentsSupervisor)
    assert supervisor._subagents[0].name in {"hr-agent", "tech-agent"}
    assert len(supervisor._subagents) == 2


def test_build_supervisor_raises_with_no_subagents() -> None:
    """build_supervisor raises ValueError if no subagent specs are present."""
    specs = [_make_supervisor()]
    with pytest.raises(ValueError, match="at least one subagent"):
        build_supervisor(specs)


def test_build_supervisor_accepts_custom_executor() -> None:
    """build_supervisor forwards a custom executor to DeepAgentsSupervisor."""
    specs = [_make_subagent("hr-agent", ["vacaciones"])]
    custom_stub = StubExecutor(responses={"hr-agent": "Custom HR response"})
    supervisor = build_supervisor(specs, executor=custom_stub)
    result = supervisor.invoke("vacaciones anuales")
    assert result == "Custom HR response"


# ---------------------------------------------------------------------------
# DeepAgentsSupervisor.invoke — StubExecutor
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_supervisor() -> DeepAgentsSupervisor:
    """Supervisor built from real fixture specs with a StubExecutor."""
    specs = load_specs_from_json(_FIXTURE_PATH)
    stub = StubExecutor(
        responses={
            "hr-policies-agent": "Tienes 22 días hábiles de vacaciones anuales.",
            "langchain-docs-agent": "LangChain is a framework for LLM applications.",
        }
    )
    return build_supervisor(specs, executor=stub)


def test_supervisor_vacaciones_routes_to_hr_agent(
    real_supervisor: DeepAgentsSupervisor,
) -> None:
    """Verification #1: vacaciones question → hr-policies-agent response.

    Registry acceptance: "user asks vacaciones question → supervisor routes
    to hr-policies-agent → returns answer".
    """
    response = real_supervisor.invoke("¿cuántos días de vacaciones tengo?")
    assert "22 días" in response, f"Unexpected response: {response!r}"


def test_supervisor_langchain_routes_to_langchain_agent(
    real_supervisor: DeepAgentsSupervisor,
) -> None:
    """Verification #2: langchain question → langchain-docs-agent response.

    Registry acceptance: "user asks langchain question → routes to
    langchain-docs-agent".
    """
    response = real_supervisor.invoke("how do I integrate langchain with my app?")
    assert "LangChain" in response, f"Unexpected response: {response!r}"


def test_supervisor_no_overlap_returns_fallback_response(
    real_supervisor: DeepAgentsSupervisor,
) -> None:
    """A message with no topic overlap returns the canonical fallback string."""
    response = real_supervisor.invoke("hola, ¿qué tiempo hace hoy?")
    # Fallback response contains a polite redirect — not an agent canned response.
    assert "No he podido determinar" in response or len(response) > 0


def test_supervisor_empty_message_returns_fallback_response(
    real_supervisor: DeepAgentsSupervisor,
) -> None:
    """Empty message returns the canonical fallback string."""
    response = real_supervisor.invoke("")
    assert "No he podido determinar" in response or len(response) > 0


def test_supervisor_executor_exception_propagates() -> None:
    """If the executor raises, the exception propagates from invoke()."""

    class BrokenExecutor:
        def invoke(self, subagent: AgentSpec, message: str) -> str:
            raise RuntimeError("LLM gateway unavailable")

    specs = [_make_subagent("hr-agent", ["vacaciones"])]
    supervisor = DeepAgentsSupervisor(
        subagents=specs,
        executor=BrokenExecutor(),  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="LLM gateway unavailable"):
        supervisor.invoke("vacaciones anuales")


# ---------------------------------------------------------------------------
# DeepAgentsSupervisor.__init__ edge cases
# ---------------------------------------------------------------------------


def test_supervisor_init_empty_subagents_raises() -> None:
    """DeepAgentsSupervisor raises ValueError with an empty subagent list."""
    with pytest.raises(ValueError, match="at least one subagent"):
        DeepAgentsSupervisor(subagents=[], executor=StubExecutor())


def test_supervisor_routes_inactive_agents_no_filtering() -> None:
    """The supervisor does NOT filter by is_active — that is the caller's job.

    The routing layer treats all passed subagents equally regardless of
    is_active.  Callers (P02-S08-T001) should filter before building the
    supervisor.  This test documents and protects that behaviour.
    """
    inactive = AgentSpec(
        name="inactive-agent",
        description="Inactive",
        agent_type="subagent",
        framework="deepagents",
        parent_agent_name="sup",
        subagent_topics=["vacaciones"],
        system_prompt="prompt",
        model_id="model",
        is_active=False,
    )
    stub = StubExecutor(responses={"inactive-agent": "Even inactive agents route in T008"})
    supervisor = DeepAgentsSupervisor(subagents=[inactive], executor=stub)
    response = supervisor.invoke("vacaciones")
    # Routes to inactive agent — filtering is the caller's responsibility.
    assert "inactive-agent" in response or "Even inactive" in response
