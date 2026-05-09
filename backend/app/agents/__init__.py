"""
Public API for the agents package.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Exports the stable surface that downstream code (P02-S08-T001 HTTP endpoints,
P04-S02-T005 AgentsPage via API) will import:

  - `AgentSpec`           — domain dataclass (no external deps)
  - `RoutingDecision`     — result of routing decision
  - `SubagentExecutor`    — Protocol for executor implementations
  - `StubExecutor`        — deterministic test stub (T008 default)
  - `load_specs_from_json`— Mode A loader from JSON fixture
  - `build_supervisor`    — factory: specs + executor → DeepAgentsSupervisor
  - `DeepAgentsSupervisor`— orchestrator class

Internal modules:
  - `routing.py`          — pure `select_subagent()` function
  - `specs.py`            — AgentSpec + JSON loader
  - `_executor.py`        — Protocol + StubExecutor
  - `deepagents_runtime.py` — DeepAgentsSupervisor + build_supervisor

NOTE: `select_subagent` is also re-exported for testing convenience.
"""

from __future__ import annotations

from app.agents._executor import StubExecutor, SubagentExecutor
from app.agents.deepagents_runtime import DeepAgentsSupervisor, build_supervisor
from app.agents.routing import RoutingDecision, select_subagent
from app.agents.specs import AgentSpec, load_specs_from_json

__all__ = [
    "AgentSpec",
    "DeepAgentsSupervisor",
    "RoutingDecision",
    "StubExecutor",
    "SubagentExecutor",
    "build_supervisor",
    "load_specs_from_json",
    "select_subagent",
]
