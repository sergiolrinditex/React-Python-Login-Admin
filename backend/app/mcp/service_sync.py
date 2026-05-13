"""
Hilo People — MCP service: sync_server use case.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Orchestrates the sync_server use case: load server, decrypt creds,
         call client.discover, upsert tools/resources/prompts, commit, audit.
         Extracted from service.py for file-size compliance.

Key deps:
  - app.mcp.repository (get_server_by_id, get_credential_for_server, upsert_*)
  - app.mcp.audit (audit_server_sync)
  - app.mcp.errors (McpServerNotFoundError, McpServerUnreachableError)
  - app.security.encryption (decrypt_secret)

Source refs:
  - task pack P02-S07-T001 §D-SYNC1 (idempotent, no-destructive)
"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy.orm import Session

from app.mcp.audit import audit_server_sync
from app.mcp.errors import McpServerNotFoundError, McpServerUnreachableError
from app.mcp.repository import (
    get_credential_for_server,
    get_server_by_id,
    update_server_sync_at,
    upsert_prompts,
    upsert_resources,
    upsert_tools,
)
from app.security.encryption import decrypt_secret

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def sync_server(
    session: Session,
    *,
    server_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str,
) -> dict:
    """Discover tools/resources/prompts from a remote MCP server and upsert.

    Steps:
      1. Load McpServer (FOR UPDATE) → 404 if not found.
      2. Load credential; decrypt secret if present.
      3. Call mcp.client.discover.
      4. Upsert tools/resources/prompts (D-SYNC1 idempotent).
      5. Update last_sync_at + status='active'.
      6. Commit + audit success.

    Args:
        session:        Active SQLAlchemy Session.
        server_id:      UUID of the server to sync.
        actor_user_id:  Admin user UUID.
        request_id:     X-Request-ID.

    Returns:
        Dict with tools_count, resources_count, prompts_count, status.

    Raises:
        McpServerNotFoundError:    If server_id not in DB.
        McpServerUnreachableError: If remote server is unreachable.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.service.sync_server.start server_id=%s request_id=%s",
            str(server_id), request_id,
        )  # BEFORE

    server = get_server_by_id(session, server_id)
    if server is None:
        raise McpServerNotFoundError(f"MCP server {server_id} not found")

    cred = get_credential_for_server(session, server_id)
    secret_plain: str | None = None
    auth_type = "none"

    if cred:
        auth_type = cred.auth_type
        if cred.encrypted_secret and auth_type != "none":
            try:
                secret_plain = decrypt_secret(cred.encrypted_secret)
            except Exception as exc:
                logger.error(
                    "mcp.service.sync_server.decrypt_error server_id=%s error=%s",
                    str(server_id), type(exc).__name__,
                )
                raise McpServerUnreachableError("Cannot decrypt server credentials") from exc

    from app.mcp import client as _mcp_client  # deferred to allow test mocking  # noqa: PLC0415

    try:
        tools, resources, prompts = _mcp_client.discover(
            endpoint=server.endpoint_url or "",
            auth_type=auth_type,
            secret=secret_plain,
        )
    except McpServerUnreachableError as exc:
        logger.error(
            "mcp.service.sync_server.unreachable server_id=%s error=%s",
            str(server_id), str(exc),
        )
        session.rollback()
        audit_server_sync(
            actor_user_id=actor_user_id, server_id=server_id,
            outcome="failure", request_id=request_id,
        )
        raise

    try:
        tools_count = upsert_tools(session, server_id=server_id, tools=tools)
        resources_count = upsert_resources(session, server_id=server_id, resources=resources)
        prompts_count = upsert_prompts(session, server_id=server_id, prompts=prompts)
        update_server_sync_at(session, server=server)
        session.commit()
    except Exception as exc:
        logger.error(
            "mcp.service.sync_server.persist_error server_id=%s error=%s",
            str(server_id), type(exc).__name__, exc_info=True,
        )
        session.rollback()
        audit_server_sync(
            actor_user_id=actor_user_id, server_id=server_id,
            outcome="failure", request_id=request_id,
        )
        raise

    audit_server_sync(
        actor_user_id=actor_user_id, server_id=server_id,
        tools_count=tools_count, resources_count=resources_count,
        prompts_count=prompts_count, outcome="success", request_id=request_id,
    )

    if _VERBOSE:
        logger.debug(
            "mcp.service.sync_server.ok server_id=%s tools=%d request_id=%s",
            str(server_id), tools_count, request_id,
        )  # AFTER
    return {
        "tools_count": tools_count,
        "resources_count": resources_count,
        "prompts_count": prompts_count,
        "status": "active",
    }
