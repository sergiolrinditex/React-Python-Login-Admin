"""
Hilo People — Agents service: list_agents use case.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Implements the list_agents use case for GET /api/v1/admin/ai/agents.
         Returns all agents with their bound tool details.
         Admin-only — enforce at router level via require_admin.

Key deps:
  - app.agents.repository_agents.list_agents_with_bindings

Source refs:
  - task pack P02-S08-T001 §E.1
  - instrucciones.md §3.1#mcp-agents
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.agents.repository_agents import list_agents_with_bindings

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def list_agents(session: Session, *, request_id: str = "") -> list[dict[str, Any]]:
    """Return all agents with bound tool details (admin-only use case).

    Business rule: any admin may view all agents regardless of enabled state.
    Empty list is a valid result (FE empty state per §E.1).

    Args:
        session:    Active SQLAlchemy Session.
        request_id: X-Request-ID for log correlation.

    Returns:
        List of agent dicts shaped for AgentOut serialisation.
    """
    if _VERBOSE:
        logger.debug(
            "agents.service.list_agents.start request_id=%s", request_id
        )  # BEFORE

    agents = list_agents_with_bindings(session)

    if _VERBOSE:
        logger.debug(
            "agents.service.list_agents.ok count=%d request_id=%s",
            len(agents), request_id,
        )  # AFTER
    return agents
