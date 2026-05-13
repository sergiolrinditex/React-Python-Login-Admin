"""
Hilo People — Agents repository: public re-export shim.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Single import surface for all agent repository functions, split across:
           - repository_agents.py — agent queries, tool validation, binding ops
           - repository_runs.py   — run + invocation persistence

Source refs:
  - task pack P02-S08-T001 §D.2 (module skeleton)
  - 01-non-negotiables.md §File size (one responsibility per file)
"""

from __future__ import annotations

from app.agents.repository_agents import (
    bind_tools_to_agent,
    get_agent_by_id,
    list_agents_with_bindings,
    validate_tool_ids_approved,
)
from app.agents.repository_runs import (
    create_agent_run,
    record_tool_invocation,
    update_agent_run_status,
)

__all__ = [
    "list_agents_with_bindings",
    "get_agent_by_id",
    "validate_tool_ids_approved",
    "bind_tools_to_agent",
    "create_agent_run",
    "update_agent_run_status",
    "record_tool_invocation",
]
