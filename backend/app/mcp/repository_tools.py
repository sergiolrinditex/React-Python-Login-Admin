"""
Hilo People — MCP repository: tool, resource, prompt upsert and tool ops.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Upsert (D-SYNC1 idempotent) and direct CRUD for mcp_tools,
         mcp_resources, mcp_prompts. Extracted from repository.py for
         file-size compliance (one responsibility per file).

Key deps:
  - app.db.models.mcp (McpTool, McpResource, McpPrompt)
  - sqlalchemy==2.0.49

Source refs:
  - task pack P02-S07-T001 §D-SYNC1 (no-destructive upsert)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.mcp import McpPrompt, McpResource, McpTool

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def upsert_tools(
    session: Session,
    *,
    server_id: uuid.UUID,
    tools: list[dict[str, Any]],
) -> int:
    """Upsert discovered tools for a server (D-SYNC1 idempotent, no-destructive).

    For existing (server_id, name): update description + schemas only.
    Preserve enabled, requires_approval, risk_level (admin-curated).
    For new tools: INSERT with DB defaults.

    Args:
        session:   Active Session.
        server_id: Server UUID.
        tools:     List of tool discovery dicts.

    Returns:
        Count of tools processed.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.repository.upsert_tools.start server_id=%s count=%d",
            str(server_id), len(tools),
        )  # BEFORE

    count = 0
    for t in tools:
        existing = (
            session.query(McpTool)
            .filter(McpTool.server_id == server_id, McpTool.name == t["name"])
            .first()
        )
        if existing:
            existing.description = t.get("description")
            existing.input_schema = t.get("input_schema") or {}
            existing.output_schema = t.get("output_schema") or {}
        else:
            session.add(McpTool(
                server_id=server_id, name=t["name"],
                description=t.get("description"),
                input_schema=t.get("input_schema") or {},
                output_schema=t.get("output_schema") or {},
            ))
        count += 1

    session.flush()
    if _VERBOSE:
        logger.debug(
            "mcp.repository.upsert_tools.ok server_id=%s count=%d",
            str(server_id), count,
        )  # AFTER
    return count


def upsert_resources(
    session: Session,
    *,
    server_id: uuid.UUID,
    resources: list[dict[str, Any]],
) -> int:
    """Upsert discovered resources for a server (D-SYNC1).

    Args:
        session:   Active Session.
        server_id: Server UUID.
        resources: List of resource dicts with keys: uri, name, mime_type, description.

    Returns:
        Count of resources processed.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.repository.upsert_resources.start server_id=%s count=%d",
            str(server_id), len(resources),
        )  # BEFORE

    count = 0
    for r in resources:
        existing = (
            session.query(McpResource)
            .filter(McpResource.server_id == server_id, McpResource.uri == r["uri"])
            .first()
        )
        if existing:
            existing.name = r.get("name")
            existing.mime_type = r.get("mime_type")
            existing.description = r.get("description")
        else:
            session.add(McpResource(
                server_id=server_id, uri=r["uri"],
                name=r.get("name"), mime_type=r.get("mime_type"),
                description=r.get("description"),
            ))
        count += 1

    session.flush()
    if _VERBOSE:
        logger.debug(
            "mcp.repository.upsert_resources.ok server_id=%s count=%d",
            str(server_id), count,
        )  # AFTER
    return count


def upsert_prompts(
    session: Session,
    *,
    server_id: uuid.UUID,
    prompts: list[dict[str, Any]],
) -> int:
    """Upsert discovered prompts for a server (D-SYNC1).

    Args:
        session:   Active Session.
        server_id: Server UUID.
        prompts:   List of prompt dicts with keys: name, description, arguments_schema.

    Returns:
        Count of prompts processed.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.repository.upsert_prompts.start server_id=%s count=%d",
            str(server_id), len(prompts),
        )  # BEFORE

    count = 0
    for p in prompts:
        existing = (
            session.query(McpPrompt)
            .filter(McpPrompt.server_id == server_id, McpPrompt.name == p["name"])
            .first()
        )
        if existing:
            existing.description = p.get("description")
            existing.arguments_schema = p.get("arguments_schema") or {}
        else:
            session.add(McpPrompt(
                server_id=server_id, name=p["name"],
                description=p.get("description"),
                arguments_schema=p.get("arguments_schema") or {},
            ))
        count += 1

    session.flush()
    if _VERBOSE:
        logger.debug(
            "mcp.repository.upsert_prompts.ok server_id=%s count=%d",
            str(server_id), count,
        )  # AFTER
    return count


def get_tool_by_id(session: Session, tool_id: uuid.UUID) -> McpTool | None:
    """Fetch McpTool by PK.

    Args:
        session: Active Session.
        tool_id: Tool UUID.

    Returns:
        McpTool or None.
    """
    return session.query(McpTool).filter(McpTool.id == tool_id).first()


def update_tool(
    session: Session,
    *,
    tool: McpTool,
    enabled: bool | None,
    requires_approval: bool | None,
    risk_level: str | None,
) -> McpTool:
    """Apply PATCH semantics to a McpTool row.

    Only provided (non-None) fields are updated (PATCH semantics).

    Args:
        session:           Active Session.
        tool:              McpTool ORM instance.
        enabled:           New value or None (no-op).
        requires_approval: New value or None.
        risk_level:        New value or None.

    Returns:
        Updated McpTool instance.
    """
    if _VERBOSE:
        logger.debug("mcp.repository.update_tool.start tool_id=%s", str(tool.id))  # BEFORE

    if enabled is not None:
        tool.enabled = enabled
    if requires_approval is not None:
        tool.requires_approval = requires_approval
    if risk_level is not None:
        tool.risk_level = risk_level

    session.flush()

    if _VERBOSE:
        logger.debug(
            "mcp.repository.update_tool.ok tool_id=%s enabled=%s risk=%s",
            str(tool.id), tool.enabled, tool.risk_level,
        )  # AFTER
    return tool
