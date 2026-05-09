"""
deepagents Supervisor entry point — acceptance criterion #1 filename.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Responsibility:
  Provides `DeepAgentsSupervisor`, the top-level orchestrator that:
    1. Accepts a user message.
    2. Delegates to `select_subagent()` (pure routing, no LLM).
    3. Invokes the selected subagent via the injected `SubagentExecutor`.
    4. Returns the subagent's response or a fallback string.

  Also provides `build_supervisor(specs, executor)` — a factory function
  that constructs a ready-to-use supervisor from a list of `AgentSpec` objects
  and an optional executor.

Integration status (T008):
  The `SubagentExecutor` in T008 is `StubExecutor` (no LLM, no DB).
  The real deepagents integration (`create_deep_agent` from deepagents 0.5.7)
  is implemented by P02-S08-T001 as `RealSubagentExecutor`.  This file's
  `DeepAgentsSupervisor` class will remain unchanged when P02-S08-T001
  injects the real executor at construction time.

  See TECHNICAL_GUIDE §10.4 "Deep Agents" + §15 ADR-002.

Logging contract:
  - BEFORE/AFTER/ERROR on `invoke()` and `build_supervisor()`.
  - `message` raw is NEVER logged (PII risk in production).
  - `message_hash` (sha256 truncated to 12 chars) is logged for traceability.
  - `system_prompt` is NOT logged.

Dependencies:
  - app.agents.routing (select_subagent + RoutingDecision)
  - app.agents.specs (AgentSpec)
  - app.agents._executor (SubagentExecutor protocol + StubExecutor)
  - app.core.logging (structlog)
"""

from __future__ import annotations

import hashlib
import time

from app.agents._executor import StubExecutor, SubagentExecutor
from app.agents.routing import RoutingDecision, select_subagent
from app.agents.specs import AgentSpec
from app.core.logging import get_logger

_logger = get_logger("app.agents.deepagents_runtime")

_FALLBACK_RESPONSE = (
    "No he podido determinar el área especializada de tu consulta. "
    "Por favor, reformula la pregunta mencionando el tema principal "
    "(p. ej. vacaciones, nóminas, LangChain, RAG)."
)


class DeepAgentsSupervisor:
    """Orchestrator that routes user messages to the appropriate subagent.

    Accepts a user message, selects the best-fit subagent via keyword overlap
    (`select_subagent`), and delegates execution to a `SubagentExecutor`.

    In T008 the executor is `StubExecutor` (no LLM).  P02-S08-T001 replaces
    it with `RealSubagentExecutor` (deepagents + LiteLLM).

    Attributes:
      _subagents  — list of subagent AgentSpec (agent_type == 'subagent').
      _executor   — implementation of SubagentExecutor Protocol.

    Params (init):
      subagents — list of AgentSpec with agent_type='subagent'.
      executor  — object satisfying SubagentExecutor Protocol.

    Errors (init):
      ValueError — if subagents list is empty (degenerate config).
    """

    def __init__(
        self,
        subagents: list[AgentSpec],
        executor: SubagentExecutor,
    ) -> None:
        """Initialise the supervisor with subagent specs and an executor.

        Params:
          subagents — list of AgentSpec (only subagent-type entries).
          executor  — SubagentExecutor Protocol implementation.
        Returns: None.
        Errors:
          ValueError — if subagents is empty (a supervisor needs ≥1 subagent).
        """
        if not subagents:
            raise ValueError(
                "DeepAgentsSupervisor requires at least one subagent. "
                "Got an empty list — check the fixture or DB loader."
            )
        self._subagents = subagents
        self._executor = executor
        _logger.debug(
            "agents.supervisor.init",
            subagent_count=len(subagents),
            subagent_names=[s.name for s in subagents],
            executor_class=type(executor).__name__,
        )

    def invoke(self, message: str) -> str:
        """Route the user message to the best subagent and return its response.

        Steps:
          1. Log BEFORE with message_hash (never raw message).
          2. Call `select_subagent()` to get a RoutingDecision.
          3. If no subagent matched → return _FALLBACK_RESPONSE.
          4. Find the AgentSpec for the selected name.
          5. Delegate to executor.invoke(subagent, message).
          6. Log AFTER with latency and output length.
          7. Return the executor's response.

        Params:
          message — user message string (may be empty).
        Returns: response string from the subagent or fallback string.
        Errors:
          Any exception from the executor propagates upward; it is logged
          at ERROR level before re-raising.
        """
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:12]
        start_ns = time.monotonic_ns()
        _logger.debug(
            "agents.supervisor.invoke.before",
            message_hash=message_hash,
            subagent_count=len(self._subagents),
        )

        decision: RoutingDecision = select_subagent(message, self._subagents)

        if decision.fallback_used or decision.selected_subagent is None:
            latency_ms = (time.monotonic_ns() - start_ns) / 1_000_000
            _logger.debug(
                "agents.supervisor.invoke.after",
                message_hash=message_hash,
                selected_subagent=None,
                fallback_used=True,
                latency_ms=round(latency_ms, 2),
            )
            return _FALLBACK_RESPONSE

        # Locate the AgentSpec for the selected subagent name.
        spec: AgentSpec | None = next(
            (s for s in self._subagents if s.name == decision.selected_subagent),
            None,
        )
        if spec is None:
            # Guard: should never happen — decision came from the same list.
            _logger.warning(
                "agents.supervisor.invoke.warning",
                message_hash=message_hash,
                selected_subagent=decision.selected_subagent,
                detail="selected_subagent not found in subagent list; falling back",
            )
            return _FALLBACK_RESPONSE

        try:
            response = self._executor.invoke(spec, message)
        except Exception as exc:
            latency_ms = (time.monotonic_ns() - start_ns) / 1_000_000
            _logger.error(
                "agents.supervisor.invoke.error",
                message_hash=message_hash,
                selected_subagent=decision.selected_subagent,
                error_class=type(exc).__name__,
                error_message_truncated=str(exc)[:200],
                latency_ms=round(latency_ms, 2),
            )
            raise

        latency_ms = (time.monotonic_ns() - start_ns) / 1_000_000
        _logger.debug(
            "agents.supervisor.invoke.after",
            message_hash=message_hash,
            selected_subagent=decision.selected_subagent,
            score=decision.score,
            matched_topics_count=len(decision.matched_topics),
            fallback_used=False,
            output_length=len(response),
            latency_ms=round(latency_ms, 2),
        )
        return response


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def build_supervisor(
    specs: list[AgentSpec],
    executor: SubagentExecutor | None = None,
) -> DeepAgentsSupervisor:
    """Build and return a DeepAgentsSupervisor from a list of AgentSpec.

    Filters `specs` to extract only subagent-type entries.
    Defaults to `StubExecutor` when no executor is provided.

    Params:
      specs    — all AgentSpec objects (supervisor + subagents mixed).
      executor — optional SubagentExecutor; defaults to StubExecutor.
    Returns: initialised DeepAgentsSupervisor.
    Errors:
      ValueError — if no subagent-type specs are found in `specs`.
    """
    _logger.debug(
        "agents.supervisor.build.before",
        total_specs=len(specs),
        executor_class=type(executor).__name__ if executor else "StubExecutor",
    )

    subagents = [s for s in specs if s.agent_type == "subagent"]
    if executor is None:
        executor = StubExecutor()

    supervisor = DeepAgentsSupervisor(subagents=subagents, executor=executor)

    _logger.debug(
        "agents.supervisor.build.after",
        subagent_count=len(subagents),
        executor_class=type(executor).__name__,
    )
    return supervisor
