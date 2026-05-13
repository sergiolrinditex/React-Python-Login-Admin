"""
Hilo People — Agents service: bind_tools use case.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Implements PATCH /api/v1/admin/ai/agents/{id}/tools.
         Validates tool approvals, performs set-replace binding, writes audit.

Business rules (instrucciones.md §3.1#mcp-agents + §C.8):
  - Tools must be approved (enabled=True in mcp_tools) to be bound.
  - Set-replace semantics: body is the new complete binding set.
  - Audit row written for every mutation (even no-op empty→empty is skipped
    but empty→[A] or [A,B]→[B] both produce audit rows).
  - Atomically committed — no partial writes on validation failure.

Key deps:
  - app.agents.repository_agents (validate_tool_ids_approved, bind_tools_to_agent,
                                   get_agent_by_id)
  - app.agents.audit (audit_agent_tools_update)

Source refs:
  - task pack P02-S08-T001 §E.2
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.audit import audit_agent_tools_update
from app.agents.repository_agents import (
    bind_tools_to_agent,
    get_agent_by_id,
    validate_tool_ids_approved,
)

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def bind_tools(
    session: Session,
    *,
    agent_id: uuid.UUID,
    tool_ids: list[uuid.UUID],
    actor_user_id: uuid.UUID,
    request_id: str = "",
    ip: str = "",
    user_agent: str = "",
) -> dict[str, Any]:
    """Bind a set of approved MCP tools to an agent (set-replace semantics).

    Args:
        session:       Active SQLAlchemy Session.
        agent_id:      UUID of the agent to update.
        tool_ids:      New complete set of MCP tool UUIDs.
        actor_user_id: Admin performing the operation (for audit).
        request_id:    X-Request-ID for correlation.
        ip:            Client IP for audit.
        user_agent:    User-Agent header for audit.

    Returns:
        Updated agent dict shaped for AgentOut serialisation.

    Raises:
        AgentNotFoundError:      Agent UUID does not exist.
        AgentToolNotFoundError:  One or more tool_ids not found in mcp_tools.
        AgentToolNotApprovedError: One or more tools exist but are disabled.
    """
    if _VERBOSE:
        logger.debug(
            "agents.service.bind_tools.start agent_id=%s tool_count=%d request_id=%s",
            str(agent_id), len(tool_ids), request_id,
        )  # BEFORE

    # 1. Validate agent exists (raises AgentNotFoundError if not)
    get_agent_by_id(session, agent_id)

    # 2. Validate all tool_ids exist + are approved
    if tool_ids:
        validate_tool_ids_approved(session, tool_ids)

    # 3. Set-replace bindings in one flush (transaction boundary at caller)
    added_ids, removed_ids = bind_tools_to_agent(
        session, agent_id=agent_id, tool_ids=tool_ids
    )
    session.commit()

    # 4. Write audit row (D-S2 — independent session via write_admin_ai_audit)
    audit_agent_tools_update(
        actor_user_id=actor_user_id,
        agent_id=agent_id,
        added=added_ids,
        removed=removed_ids,
        tool_ids=[str(t) for t in tool_ids],
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
    )

    # 5. Re-fetch agent with updated bindings
    updated = get_agent_by_id(session, agent_id)

    if _VERBOSE:
        logger.debug(
            "agents.service.bind_tools.ok agent_id=%s added=%d removed=%d request_id=%s",
            str(agent_id), len(added_ids), len(removed_ids), request_id,
        )  # AFTER

    return updated
