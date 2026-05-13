"""
Hilo People — MCP service: update_mcp_tool use case.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Orchestrates the PATCH tool use case: load tool, apply updates,
         commit, audit. Extracted from service.py for file-size compliance.

Key deps:
  - app.mcp.repository (get_tool_by_id, update_tool)
  - app.mcp.audit (audit_tool_update)
  - app.mcp.errors (McpToolNotFoundError)

Source refs:
  - task pack P02-S07-T001 §Front→Back→DB contract (update_tool)
"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy.orm import Session

from app.db.models.mcp import McpTool
from app.mcp.audit import audit_tool_update
from app.mcp.errors import McpToolNotFoundError
from app.mcp.repository import get_tool_by_id, update_tool

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def update_mcp_tool(
    session: Session,
    *,
    tool_id: uuid.UUID,
    enabled: bool | None,
    requires_approval: bool | None,
    risk_level: str | None,
    actor_user_id: uuid.UUID,
    request_id: str,
) -> McpTool:
    """PATCH a MCP tool's admin-curated fields and audit the change.

    Args:
        session:           Active SQLAlchemy Session.
        tool_id:           UUID of the tool to update.
        enabled:           New enabled value (None = no change).
        requires_approval: New requires_approval value (None = no change).
        risk_level:        New risk_level (None = no change).
        actor_user_id:     Admin user UUID.
        request_id:        X-Request-ID for audit.

    Returns:
        Updated McpTool ORM instance.

    Raises:
        McpToolNotFoundError: If tool_id not found.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.service.update_tool.start tool_id=%s request_id=%s",
            str(tool_id), request_id,
        )  # BEFORE

    tool = get_tool_by_id(session, tool_id)
    if tool is None:
        raise McpToolNotFoundError(f"MCP tool {tool_id} not found")

    before = {
        "enabled": tool.enabled,
        "requires_approval": tool.requires_approval,
        "risk_level": tool.risk_level,
    }

    tool = update_tool(
        session, tool=tool, enabled=enabled,
        requires_approval=requires_approval, risk_level=risk_level,
    )

    try:
        session.commit()
    except Exception as exc:
        logger.error(
            "mcp.service.update_tool.commit_error tool_id=%s error=%s",
            str(tool_id), type(exc).__name__, exc_info=True,
        )
        session.rollback()
        raise

    after = {
        "enabled": tool.enabled,
        "requires_approval": tool.requires_approval,
        "risk_level": tool.risk_level,
    }

    audit_tool_update(
        actor_user_id=actor_user_id, tool_id=tool_id,
        server_id=tool.server_id, before=before, after=after,
        request_id=request_id,
    )

    if _VERBOSE:
        logger.debug(
            "mcp.service.update_tool.ok tool_id=%s request_id=%s",
            str(tool_id), request_id,
        )  # AFTER
    return tool
