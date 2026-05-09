"""
SubagentExecutor Protocol and StubExecutor for testing.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Responsibility:
  Defines the `SubagentExecutor` Protocol — the interface that the supervisor
  uses to invoke a selected subagent.  In T008 only `StubExecutor` is provided.
  The real deepagents executor (calling `create_deep_agent` from deepagents 0.5.7
  + a LiteLLM-backed model) will be implemented in P02-S08-T001 when the DB table,
  HTTP endpoint, and LiteLLMRouter are available.

Why a Protocol?
  - Allows the supervisor to be fully tested without a live LLM.
  - Keeps the domain (routing + supervisor) decoupled from the data layer
    (deepagents runtime, LiteLLM, DB).
  - P02-S08-T001 provides `RealSubagentExecutor` that satisfies this Protocol.

Security:
  - `invoke` does NOT log `message` raw (may contain PII).
  - `invoke` does NOT log `system_prompt` (may contain sensitive instructions).
  - See logging contract in TECHNICAL_GUIDE §10.4 + task pack §"Logging contract".

NOTE about deepagents import:
  `import deepagents` is intentionally NOT done here in T008.  This file only
  defines the Protocol and the Stub.  The real implementation will import
  `create_deep_agent` in P02-S08-T001 via a separate `_real_executor.py`.
  Keeping the import conditional avoids hard-failing if deepagents is
  installed but misconfigured (no model credentials) in T008 test runs.

Dependencies:
  - typing.Protocol (stdlib)
  - Python 3.13 (no external deps)
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from app.agents.specs import AgentSpec
from app.core.logging import get_logger

_logger = get_logger("app.agents.executor")


# ---------------------------------------------------------------------------
# Protocol (interface contract)
# ---------------------------------------------------------------------------


@runtime_checkable
class SubagentExecutor(Protocol):
    """Protocol for executing a subagent invocation.

    Implementations:
      StubExecutor      — deterministic stub for unit tests (T008).
      RealSubagentExecutor — deepagents + LiteLLM integration (P02-S08-T001).

    Purpose: decouple the supervisor orchestration from the LLM execution.

    Params (invoke):
      subagent — the AgentSpec selected by the routing algorithm.
      message  — the raw user message to forward (NOT logged).
    Returns: response string from the (stub or real) subagent.
    Errors: any exception from the underlying executor propagates upward.
    """

    def invoke(self, subagent: AgentSpec, message: str) -> str:
        """Invoke the subagent with the user message and return a response."""
        ...


# ---------------------------------------------------------------------------
# Stub implementation (T008 — for tests and verify-slice demo)
# ---------------------------------------------------------------------------


class StubExecutor:
    """Deterministic test stub for SubagentExecutor.

    Returns a fixed canned response per subagent name.  Used in unit tests
    and in the verify-slice demo script.  Does NOT call any LLM or network.

    Purpose: validate the routing + supervisor wiring without requiring
    LiteLLM credentials, a live LiteLLM gateway, or DB rows.

    Attributes:
      _responses — mapping from subagent name to canned response string.

    Params (init):
      responses — optional dict of {agent_name: response_string}.
                  Defaults to a generic template per agent name.
    """

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        """Initialise the StubExecutor with optional canned responses.

        Params:
          responses — optional {agent_name: response} mapping.
        Returns: None.
        Errors: none.
        """
        self._responses: dict[str, str] = responses or {}

    def invoke(self, subagent: AgentSpec, message: str) -> str:
        """Return a deterministic stub response for the given subagent.

        Params:
          subagent — AgentSpec of the selected agent (name is the routing key).
          message  — user message (NOT logged; hash used for traceability).
        Returns: canned response string (from init overrides or generic template).
        Errors: none.
        """
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:12]
        _logger.debug(
            "agents.supervisor.invoke.before",
            selected_subagent=subagent.name,
            executor="stub",
            message_hash=message_hash,
        )

        response = self._responses.get(
            subagent.name,
            f"[StubExecutor] Subagent '{subagent.name}' received your request.",
        )

        _logger.debug(
            "agents.supervisor.invoke.after",
            selected_subagent=subagent.name,
            executor="stub",
            output_length=len(response),
        )
        return response
