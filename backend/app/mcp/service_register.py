"""
Hilo People — MCP service: register_server use case.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Orchestrates the register_server use case: allowlist validation,
         encryption, atomic persist (server + credential), D-S2 audit.
         Extracted from service.py for file-size compliance.

Key deps:
  - app.mcp.repository (create_server, create_credential)
  - app.mcp.audit (audit_server_create)
  - app.security.encryption (encrypt_secret, EncryptionError)

Source refs:
  - task pack P02-S07-T001 §Front→Back→DB contract (register_server)
"""

from __future__ import annotations

import logging
import os
import uuid
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db.models.mcp import McpServer
from app.mcp.audit import audit_server_create
from app.mcp.repository import create_credential, create_server
from app.security.encryption import EncryptionError, encrypt_secret

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def _validate_endpoint_allowlist(endpoint: str) -> None:
    """Check endpoint URL against MCP_ALLOWLIST_DOMAINS env var.

    If MCP_ALLOWLIST_DOMAINS is empty — allow all (dev default).
    Otherwise reject hosts not in the allowlist.

    Raises:
        ValueError: If the host is not in the allowlist.
    """
    allowlist_raw = os.getenv("MCP_ALLOWLIST_DOMAINS", "").strip()
    if not allowlist_raw:
        return

    allowed_domains = {d.strip().lower() for d in allowlist_raw.split(",") if d.strip()}
    if not allowed_domains:
        return

    try:
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "").lower()
    except Exception:
        raise ValueError(f"Invalid endpoint URL: {endpoint}")

    if host not in allowed_domains:
        raise ValueError(
            f"Endpoint host '{host}' is not in the MCP allowlist. "
            f"Allowed: {sorted(allowed_domains)}"
        )


def register_server(
    session: Session,
    *,
    name: str,
    transport: str,
    endpoint: str,
    auth_type: str,
    secret_plain: str | None,
    refresh_token_plain: str | None,
    created_by: uuid.UUID,
    request_id: str,
    ip: str,
) -> McpServer:
    """Register a new MCP server (encrypt credentials, persist, audit).

    Validates endpoint allowlist, encrypts credentials, creates server + credential
    atomically, then audits (D-S2 independent session).

    Args:
        session:              Active SQLAlchemy Session.
        name:                 Human-readable server name.
        transport:            'http' or 'sse'.
        endpoint:             MCP server HTTP/SSE endpoint URL.
        auth_type:            Credential kind.
        secret_plain:         Raw secret (NEVER logged).
        refresh_token_plain:  Raw refresh token (NEVER logged).
        created_by:           Admin user UUID.
        request_id:           X-Request-ID for audit.
        ip:                   Client IP for audit.

    Returns:
        Persisted McpServer ORM instance.

    Raises:
        ValueError:      If endpoint host is not in allowlist.
        EncryptionError: If Fernet encryption fails.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.service.register_server.start name_len=%d transport=%s "
            "auth_type=%s request_id=%s",
            len(name), transport, auth_type, request_id,
        )  # BEFORE

    _validate_endpoint_allowlist(endpoint)

    try:
        encrypted_secret: str | None = None
        encrypted_refresh_token: str | None = None

        if auth_type != "none" and secret_plain:
            encrypted_secret = encrypt_secret(secret_plain)
        if refresh_token_plain:
            encrypted_refresh_token = encrypt_secret(refresh_token_plain)

        server = create_server(
            session, name=name, transport_type=transport,
            endpoint_url=endpoint, created_by=created_by,
        )
        if auth_type != "none":
            create_credential(
                session, server_id=server.id, auth_type=auth_type,
                encrypted_secret=encrypted_secret,
                encrypted_refresh_token=encrypted_refresh_token,
            )
        session.commit()

    except EncryptionError as exc:
        logger.error(
            "mcp.service.register_server.encryption_error request_id=%s error=%s",
            request_id, type(exc).__name__,
        )
        session.rollback()
        audit_server_create(
            actor_user_id=created_by, server_id=uuid.UUID(int=0),
            name=name, transport=transport, auth_type=auth_type,
            outcome="failure", request_id=request_id, ip=ip,
        )
        raise

    except Exception as exc:
        logger.error(
            "mcp.service.register_server.error request_id=%s error=%s",
            request_id, type(exc).__name__, exc_info=True,
        )
        session.rollback()
        audit_server_create(
            actor_user_id=created_by, server_id=uuid.UUID(int=0),
            name=name, transport=transport, auth_type=auth_type,
            outcome="failure", request_id=request_id, ip=ip,
        )
        raise

    audit_server_create(
        actor_user_id=created_by, server_id=server.id,
        name=server.name, transport=transport, auth_type=auth_type,
        outcome="success", request_id=request_id, ip=ip,
    )

    if _VERBOSE:
        logger.debug(
            "mcp.service.register_server.ok server_id=%s request_id=%s",
            str(server.id), request_id,
        )  # AFTER
    return server
