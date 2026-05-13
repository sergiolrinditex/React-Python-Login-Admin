"""
Hilo People — MCP repository: server and credential operations.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: DB read/write for mcp_servers and mcp_credentials tables.
         Extracted from repository.py for file-size compliance (one
         responsibility per file — 01-non-negotiables.md §File size).

Key deps:
  - app.db.models.mcp (McpServer, McpCredential)
  - sqlalchemy==2.0.49

Source refs:
  - task pack P02-S07-T001 §Front→Back→DB contract
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.mcp import McpCredential, McpServer

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def list_servers(session: Session) -> list[dict[str, Any]]:
    """Return all McpServer rows with credential metadata (no secrets).

    Returns:
        List of dicts with server fields + has_credential + auth_type.
    """
    if _VERBOSE:
        logger.debug("mcp.repository.list_servers.start")  # BEFORE

    rows = session.query(McpServer).order_by(McpServer.name).all()
    result = []
    for srv in rows:
        cred = (
            session.query(McpCredential)
            .filter(McpCredential.server_id == srv.id)
            .first()
        )
        result.append({
            "id": srv.id,
            "name": srv.name,
            "transport": srv.transport_type,
            "endpoint": srv.endpoint_url,
            "status": srv.status,
            "last_sync_at": srv.last_sync_at,
            "created_by": srv.created_by,
            "has_credential": cred is not None,
            "auth_type": cred.auth_type if cred else None,
        })

    if _VERBOSE:
        logger.debug("mcp.repository.list_servers.ok count=%d", len(result))  # AFTER
    return result


def create_server(
    session: Session,
    *,
    name: str,
    transport_type: str,
    endpoint_url: str,
    created_by: uuid.UUID,
) -> McpServer:
    """Insert a new McpServer row (draft status). Caller commits.

    Args:
        session:        Active SQLAlchemy Session (flush only — caller commits).
        name:           Human-readable server name.
        transport_type: 'http' or 'sse'.
        endpoint_url:   HTTP/SSE endpoint URL.
        created_by:     Admin user UUID.

    Returns:
        Flushed McpServer instance with id populated.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.repository.create_server.start name_len=%d transport=%s",
            len(name), transport_type,
        )  # BEFORE

    server = McpServer(
        name=name, transport_type=transport_type,
        endpoint_url=endpoint_url, created_by=created_by, status="draft",
    )
    session.add(server)
    session.flush()

    if _VERBOSE:
        logger.debug("mcp.repository.create_server.ok server_id=%s", str(server.id))  # AFTER
    return server


def get_server_by_id(session: Session, server_id: uuid.UUID) -> McpServer | None:
    """Fetch McpServer by PK with FOR UPDATE lock (used in sync).

    Args:
        session:   Active Session.
        server_id: Server UUID.

    Returns:
        McpServer or None.
    """
    return (
        session.query(McpServer)
        .filter(McpServer.id == server_id)
        .with_for_update()
        .first()
    )


def get_credential_for_server(
    session: Session, server_id: uuid.UUID
) -> McpCredential | None:
    """Fetch the credential for a server.

    Args:
        session:   Active Session.
        server_id: Server UUID.

    Returns:
        McpCredential or None.
    """
    return (
        session.query(McpCredential)
        .filter(McpCredential.server_id == server_id)
        .first()
    )


def create_credential(
    session: Session,
    *,
    server_id: uuid.UUID,
    auth_type: str,
    encrypted_secret: str | None,
    encrypted_refresh_token: str | None,
) -> McpCredential:
    """Insert a McpCredential row. Caller commits.

    Args:
        session:                 Active Session.
        server_id:               FK to mcp_servers.
        auth_type:               Credential kind.
        encrypted_secret:        Fernet-encrypted secret.
        encrypted_refresh_token: Fernet-encrypted refresh token.

    Returns:
        Flushed McpCredential instance.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.repository.create_credential.start server_id=%s auth_type=%s",
            str(server_id), auth_type,
        )  # BEFORE

    cred = McpCredential(
        server_id=server_id, auth_type=auth_type,
        encrypted_secret=encrypted_secret,
        encrypted_refresh_token=encrypted_refresh_token,
    )
    session.add(cred)
    session.flush()

    if _VERBOSE:
        logger.debug("mcp.repository.create_credential.ok server_id=%s", str(server_id))  # AFTER
    return cred


def update_server_sync_at(session: Session, *, server: McpServer) -> None:
    """Update last_sync_at and status='active' after successful sync.

    Args:
        session: Active Session.
        server:  McpServer ORM instance (mutated in-place).
    """
    from sqlalchemy import func  # noqa: PLC0415
    server.last_sync_at = func.now()
    server.status = "active"
    session.flush()
