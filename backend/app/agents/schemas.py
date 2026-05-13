"""
Hilo People — Agents Pydantic v2 schemas.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Request/response schemas for 3 agent admin endpoints:
           - AgentOut / BoundToolOut  (GET /admin/ai/agents)
           - PatchAgentToolsRequest   (PATCH /admin/ai/agents/{id}/tools)
           - CreateAgentRunRequest    (POST /agents/runs)
           - AgentRunCreatedOut       (POST /agents/runs response)

Run lifecycle vocabulary per §C.4 of the task pack:
  'pending' | 'running' | 'done' | 'failed' | 'cancelled'

Key deps:
  - pydantic v2 (BaseModel, ConfigDict, Field)

Source refs:
  - task pack P02-S08-T001 §E.1–E.3 (endpoint contracts + response shapes)
  - instrucciones.md §3.1#mcp-agents (entities, lifecycle vocabulary)
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# BoundToolOut — one MCP tool bound to an agent
# ---------------------------------------------------------------------------

class BoundToolOut(BaseModel):
    """Response shape for one tool in an agent's bound_tools list.

    Carries the approval/risk metadata needed by the AgentsPage UI states
    (error_validation, success) per UX_CONTRACT §6.1 line 242.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    name: str
    server_name: str
    enabled: bool
    requires_approval: bool
    risk_level: str


# ---------------------------------------------------------------------------
# AgentOut — full agent detail (with bound_tools)
# ---------------------------------------------------------------------------

class AgentOut(BaseModel):
    """Response shape for one Agent row with its tool bindings.

    Returned by:
      - GET  /api/v1/admin/ai/agents     (list item)
      - PATCH /api/v1/admin/ai/agents/{id}/tools (single item in data)
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)
    bound_tools: list[BoundToolOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# PATCH /admin/ai/agents/{id}/tools — request
# ---------------------------------------------------------------------------

class PatchAgentToolsRequest(BaseModel):
    """Request body for PATCH /api/v1/admin/ai/agents/{agent_id}/tools.

    tool_ids is the new complete binding set (set-replace semantics).
    Empty list is valid — means 'unbind all tools from this agent'.

    Args:
        tool_ids: List of MCP tool UUIDs to bind. Empty = unbind all.
    """

    model_config = ConfigDict(extra="forbid")

    tool_ids: list[uuid.UUID] = Field(
        description=(
            "New full tool binding set for this agent (set-replace). "
            "Empty list unbinds all tools. All tool IDs must be approved "
            "(enabled=True) MCP tools."
        )
    )


# ---------------------------------------------------------------------------
# POST /agents/runs — request
# ---------------------------------------------------------------------------

class CreateAgentRunRequest(BaseModel):
    """Request body for POST /api/v1/agents/runs.

    Triggers a single blocking smoke step for the specified agent.

    Args:
        agent_id: UUID of the agent to run.
        input:    User task description (1–4000 chars, non-empty).
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: uuid.UUID = Field(
        description="UUID of the agent to invoke."
    )
    input: str = Field(
        min_length=1,
        max_length=4000,
        description="User task input (non-empty, max 4000 chars).",
    )


# ---------------------------------------------------------------------------
# POST /agents/runs — response
# ---------------------------------------------------------------------------

# Vocabulary contract per §C.4: pending | running | done | failed | cancelled
AgentRunStatus = Literal["pending", "running", "done", "failed", "cancelled"]


class AgentRunCreatedOut(BaseModel):
    """Response shape for a completed (or failed) agent run.

    run_id is the UUID of the created agent_runs row.
    status reflects the terminal state after the smoke step completes.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    status: AgentRunStatus
