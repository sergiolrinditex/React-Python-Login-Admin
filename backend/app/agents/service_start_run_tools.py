"""
Hilo People — Agents service: tool resolution helpers for start_agent_run.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Provides tool-enumeration helpers for the start_agent_run use case.
         Extracted from service_start_run.py to satisfy the ≤300 LoC rule.

         Responsibility: "What approved tools can this agent run use?"
           - _build_approved_tools_list — filters bound tools by approval policy
           - _resolve_server_secret     — decrypts MCP server credential
           - _get_server_auth_type      — looks up server auth type

Business rules:
  - Tools with requires_approval=True and no approved mcp_approvals row are
    EXCLUDED from the run (V1: log + exclude, don't fail per §E.3 step 5).
  - Credentials are decrypted at call-time and NEVER returned to the API layer.

Key deps:
  - app.db.models.mcp (McpTool, McpServer, McpCredential)
  - app.security.encryption (decrypt_secret)

Source refs:
  - task pack P02-S08-T001 §E.3
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def build_approved_tools_list(
    session: Session,
    agent_data: dict[str, Any],
    run_id: uuid.UUID,
    request_id: str,
) -> list[dict[str, Any]]:
    """Build the approved tool list for graph construction.

    Tools with requires_approval=True and no approved mcp_approvals row
    are EXCLUDED (V1 smoke: log + exclude, don't fail the run).

    Args:
        session:    Active Session.
        agent_data: Agent dict from repository (includes bound_tools).
        run_id:     Run UUID for log correlation.
        request_id: X-Request-ID for log correlation.

    Returns:
        List of tool dicts augmented with endpoint_url, auth_type, plaintext_secret.
    """
    from app.db.models.mcp import McpServer, McpTool

    approved_tools: list[dict[str, Any]] = []

    for bt in agent_data.get("bound_tools", []):
        tool_id = bt["id"]

        # Fetch tool + server details
        row = (
            session.query(McpTool, McpServer)
            .join(McpServer, McpTool.server_id == McpServer.id)
            .filter(McpTool.id == tool_id)
            .first()
        )
        if not row:
            logger.warning(
                "agents.service.start_run.tool_missing tool_id=%s run_id=%s",
                str(tool_id), str(run_id),
            )
            continue

        tool, server = row

        # V1: exclude tools that require approval and haven't been approved
        if tool.requires_approval:
            logger.info(
                "agents.service.start_run.tool_excluded_approval_required "
                "tool_id=%s tool_name=%s run_id=%s request_id=%s",
                str(tool_id), tool.name, str(run_id), request_id,
            )
            continue

        # Resolve plaintext credential for this server
        plaintext_secret = resolve_server_secret(session, server.id)

        approved_tools.append({
            "id": tool.id,
            "name": tool.name,
            "server_name": server.name,
            "enabled": bt.get("enabled", True),
            "requires_approval": tool.requires_approval,
            "risk_level": tool.risk_level,
            "endpoint_url": server.endpoint_url or "",
            "auth_type": get_server_auth_type(session, server.id),
            "plaintext_secret": plaintext_secret,
        })

    if _VERBOSE:
        logger.debug(
            "agents.service.start_run.approved_tools count=%d run_id=%s",
            len(approved_tools), str(run_id),
        )
    return approved_tools


def resolve_server_secret(session: Session, server_id: uuid.UUID) -> str | None:
    """Decrypt and return the plaintext secret for a server (if any).

    Args:
        session:   Active Session.
        server_id: McpServer UUID.

    Returns:
        Decrypted plaintext secret, or None for public servers.
    """
    from app.db.models.mcp import McpCredential
    from app.security.encryption import decrypt_secret

    cred = (
        session.query(McpCredential)
        .filter(McpCredential.server_id == server_id)
        .first()
    )
    if cred is None or not cred.encrypted_secret:
        return None

    try:
        return decrypt_secret(cred.encrypted_secret)
    except Exception as exc:
        logger.error(
            "agents.service.start_run.decrypt_error server_id=%s error=%s",
            str(server_id), type(exc).__name__,
        )
        return None


def get_server_auth_type(session: Session, server_id: uuid.UUID) -> str:
    """Return the auth_type for a server's credential row.

    Args:
        session:   Active Session.
        server_id: McpServer UUID.

    Returns:
        auth_type string, or 'none' if no credential row.
    """
    from app.db.models.mcp import McpCredential

    cred = (
        session.query(McpCredential)
        .filter(McpCredential.server_id == server_id)
        .first()
    )
    return cred.auth_type if cred else "none"
