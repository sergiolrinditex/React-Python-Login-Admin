"""
Hilo People — Agents repository: agent queries and tool-binding operations.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: DB read/write for agents and mcp_agent_bindings tables.
         Reuses existing ORM models (do NOT redeclare).

Operations:
  - list_agents_with_bindings  — SELECT agents + LEFT JOIN bindings + tools
  - get_agent_by_id            — SELECT agent by PK
  - validate_tool_ids_approved — check all tool_ids exist + enabled in mcp_tools
  - bind_tools_to_agent        — set-replace bindings in one transaction

Key deps:
  - app.db.models.agents  (Agent, McpAgentBinding)
  - app.db.models.mcp     (McpTool)
  - sqlalchemy==2.0.49

Source refs:
  - task pack P02-S08-T001 §D.4 (reuse map), §E.1–E.2 (endpoint contracts)
  - 01-non-negotiables.md §Database (parametrized queries, transactions)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.agents.errors import (
    AgentNotFoundError,
    AgentToolNotApprovedError,
    AgentToolNotFoundError,
)
from app.db.models.agents import Agent, McpAgentBinding
from app.db.models.mcp import McpTool

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def list_agents_with_bindings(session: Session) -> list[dict[str, Any]]:
    """Return all agents with their bound tool details.

    Executes a single SELECT over agents + LEFT JOIN to bindings + tools.
    Returns dicts shaped for AgentOut serialisation.

    Args:
        session: Active SQLAlchemy Session.

    Returns:
        List of dicts with agent fields + bound_tools list.
    """
    if _VERBOSE:
        logger.debug("agents.repository.list_agents.start")  # BEFORE

    agents = (
        session.query(Agent)
        .order_by(Agent.name)
        .all()
    )

    result: list[dict[str, Any]] = []
    for agent in agents:
        bound_tools = _load_bound_tools(session, agent.id)
        result.append({
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "enabled": agent.enabled,
            "config": agent.config or {},
            "bound_tools": bound_tools,
        })

    if _VERBOSE:
        logger.debug("agents.repository.list_agents.ok count=%d", len(result))  # AFTER
    return result


def get_agent_by_id(session: Session, agent_id: uuid.UUID) -> dict[str, Any]:
    """Fetch a single agent with its bound tools by PK.

    Args:
        session:  Active SQLAlchemy Session.
        agent_id: Agent UUID.

    Returns:
        Dict with agent fields + bound_tools.

    Raises:
        AgentNotFoundError: If no agent exists with agent_id.
    """
    if _VERBOSE:
        logger.debug("agents.repository.get_agent.start agent_id=%s", str(agent_id))  # BEFORE

    agent = session.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        logger.warning("agents.repository.get_agent.not_found agent_id=%s", str(agent_id))
        raise AgentNotFoundError(f"Agent not found: {agent_id}")

    bound_tools = _load_bound_tools(session, agent.id)
    result = {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "enabled": agent.enabled,
        "config": agent.config or {},
        "bound_tools": bound_tools,
    }
    if _VERBOSE:
        logger.debug(
            "agents.repository.get_agent.ok agent_id=%s bound_tools=%d",
            str(agent_id), len(bound_tools),
        )  # AFTER
    return result


def validate_tool_ids_approved(
    session: Session,
    tool_ids: list[uuid.UUID],
) -> None:
    """Check that every tool_id exists in mcp_tools and is approved (enabled=True).

    Args:
        session:  Active SQLAlchemy Session.
        tool_ids: List of tool UUIDs to validate.

    Raises:
        AgentToolNotFoundError:    If any tool_id does not exist in mcp_tools.
        AgentToolNotApprovedError: If any tool is found but has enabled=False.
    """
    if _VERBOSE:
        logger.debug(
            "agents.repository.validate_tools.start count=%d", len(tool_ids)
        )  # BEFORE

    for tid in tool_ids:
        tool = session.query(McpTool).filter(McpTool.id == tid).first()
        if tool is None:
            logger.warning(
                "agents.repository.validate_tools.not_found tool_id=%s", str(tid)
            )
            raise AgentToolNotFoundError(str(tid))
        if not tool.enabled:
            logger.warning(
                "agents.repository.validate_tools.not_approved tool_id=%s name=%s",
                str(tid), tool.name,
            )
            raise AgentToolNotApprovedError(str(tid))

    if _VERBOSE:
        logger.debug(
            "agents.repository.validate_tools.ok count=%d", len(tool_ids)
        )  # AFTER


def bind_tools_to_agent(
    session: Session,
    *,
    agent_id: uuid.UUID,
    tool_ids: list[uuid.UUID],
) -> tuple[list[str], list[str]]:
    """Set-replace the tool bindings for an agent (atomic transaction).

    Semantics: the body declares the new full binding set.
      - DELETE existing bindings not in tool_ids.
      - INSERT new bindings not in the existing set.
      - Leave overlapping bindings untouched.

    Args:
        session:  Active SQLAlchemy Session (caller commits/rollbacks).
        agent_id: UUID of the agent to update.
        tool_ids: New complete set of tool UUIDs to bind.

    Returns:
        Tuple (added_ids, removed_ids) — lists of UUID strings for audit log.

    Raises:
        AgentNotFoundError: If the agent does not exist.
    """
    if _VERBOSE:
        logger.debug(
            "agents.repository.bind_tools.start agent_id=%s tool_count=%d",
            str(agent_id), len(tool_ids),
        )  # BEFORE

    agent = session.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        raise AgentNotFoundError(f"Agent not found: {agent_id}")

    new_set = set(tool_ids)

    # Fetch existing bindings
    existing_bindings = (
        session.query(McpAgentBinding)
        .filter(McpAgentBinding.agent_id == agent_id)
        .all()
    )
    existing_set = {b.tool_id for b in existing_bindings}

    to_remove = existing_set - new_set
    to_add = new_set - existing_set

    # DELETE bindings no longer in the set
    if to_remove:
        session.execute(
            sa.delete(McpAgentBinding).where(
                McpAgentBinding.agent_id == agent_id,
                McpAgentBinding.tool_id.in_(to_remove),
            )
        )

    # INSERT new bindings
    for tid in to_add:
        session.add(McpAgentBinding(agent_id=agent_id, tool_id=tid, enabled=True))

    session.flush()

    added_ids = [str(t) for t in to_add]
    removed_ids = [str(t) for t in to_remove]

    if _VERBOSE:
        logger.debug(
            "agents.repository.bind_tools.ok agent_id=%s added=%d removed=%d",
            str(agent_id), len(added_ids), len(removed_ids),
        )  # AFTER

    return added_ids, removed_ids


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_bound_tools(
    session: Session,
    agent_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Load tool details for all bindings of an agent.

    Args:
        session:  Active Session.
        agent_id: Agent UUID.

    Returns:
        List of dicts matching BoundToolOut schema fields.
    """
    from app.db.models.mcp import McpServer  # local import to avoid circular

    rows = (
        session.query(McpAgentBinding, McpTool, McpServer)
        .join(McpTool, McpAgentBinding.tool_id == McpTool.id)
        .join(McpServer, McpTool.server_id == McpServer.id)
        .filter(McpAgentBinding.agent_id == agent_id)
        .all()
    )

    return [
        {
            "id": binding.tool_id,
            "name": tool.name,
            "server_name": server.name,
            "enabled": binding.enabled,
            "requires_approval": tool.requires_approval,
            "risk_level": tool.risk_level,
        }
        for binding, tool, server in rows
    ]
