"""
Hilo People — MCP audit adapter.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Thin adapter over app.admin._audit.write_admin_ai_audit for the
         three MCP audit actions:
           - admin.ai.mcp.server.create
           - admin.ai.mcp.server.sync  (+ admin.ai.mcp.server.sync.failed)
           - admin.ai.mcp.tool.update

         All calls use D-S2 (independent session via write_admin_ai_audit).
         No credential values are ever passed into metadata.

Key deps:
  - app.admin._audit.write_admin_ai_audit — D-S2 independent session helper

Source refs:
  - task pack P02-S07-T001 §Audit actions
  - 01-non-negotiables.md §Security (audit log, no PII/credentials in metadata)
"""

from __future__ import annotations

import uuid
from typing import Any

from app.admin._audit import write_admin_ai_audit


def audit_server_create(
    *,
    actor_user_id: uuid.UUID,
    server_id: uuid.UUID,
    name: str,
    transport: str,
    auth_type: str,
    outcome: str = "success",
    request_id: str = "",
    ip: str = "",
) -> None:
    """Write audit row for MCP server creation.

    Args:
        actor_user_id: Admin who performed the action.
        server_id:     UUID of the created server (UUID(int=0) on failure).
        name:          Server name (safe to log — not a secret).
        transport:     Transport type.
        auth_type:     Credential type (not the secret value).
        outcome:       'success' or 'failure'.
        request_id:    X-Request-ID for correlation.
        ip:            Client IP.
    """
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.ai.mcp.server.create" if outcome == "success"
               else "admin.ai.mcp.server.create.failed",
        entity_type="mcp_server",
        entity_id=server_id,
        metadata={
            "server_name": name,
            "transport": transport,
            "auth_type": auth_type,
            "outcome": outcome,
            "request_id": request_id,
            "ip": ip,
        },
    )


def audit_server_sync(
    *,
    actor_user_id: uuid.UUID,
    server_id: uuid.UUID,
    tools_count: int = 0,
    resources_count: int = 0,
    prompts_count: int = 0,
    outcome: str = "success",
    request_id: str = "",
) -> None:
    """Write audit row for MCP server sync.

    Args:
        actor_user_id:   Admin who triggered the sync.
        server_id:       UUID of the synced server.
        tools_count:     Number of tools discovered.
        resources_count: Number of resources discovered.
        prompts_count:   Number of prompts discovered.
        outcome:         'success' or 'failure'.
        request_id:      X-Request-ID.
    """
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.ai.mcp.server.sync" if outcome == "success"
               else "admin.ai.mcp.server.sync.failed",
        entity_type="mcp_server",
        entity_id=server_id,
        metadata={
            "tools_count": tools_count,
            "resources_count": resources_count,
            "prompts_count": prompts_count,
            "outcome": outcome,
            "request_id": request_id,
        },
    )


def audit_tool_update(
    *,
    actor_user_id: uuid.UUID,
    tool_id: uuid.UUID,
    server_id: uuid.UUID,
    before: dict[str, Any],
    after: dict[str, Any],
    request_id: str = "",
) -> None:
    """Write audit row for MCP tool update.

    before/after contain only {enabled, requires_approval, risk_level} —
    never any credential or secret values.

    Args:
        actor_user_id: Admin who performed the update.
        tool_id:       UUID of the updated tool.
        server_id:     UUID of the tool's server.
        before:        Dict of {enabled, requires_approval, risk_level} before update.
        after:         Dict of same fields after update.
        request_id:    X-Request-ID.
    """
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.ai.mcp.tool.update",
        entity_type="mcp_tool",
        entity_id=tool_id,
        metadata={
            "server_id": str(server_id),
            "before": before,
            "after": after,
            "request_id": request_id,
        },
    )
