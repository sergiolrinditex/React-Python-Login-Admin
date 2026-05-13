"""
Hilo People — MCP client handshake helper (initialize lifecycle).

Slice:  P02-S07-T001 — MCP server and tool endpoints (debugger cycle 1)
Phase:  P02 Core Features
Purpose: Implement the MCP 2025-06-18 §6.1 initialization handshake. Per the
         MCP specification, a client MUST send `initialize` before any other
         JSON-RPC method (tools/list, resources/list, prompts/list). The
         server SHALL NOT respond to non-initialize requests prior to the
         initialization phase completing. After a successful initialize the
         client sends the `notifications/initialized` notification (no id,
         no response expected).

         This module is split out of client.py to keep both files within the
         300-line file-size cap declared in 01-non-negotiables.md.

         The handshake is invoked once per `discover()` call.

Key deps:
  - httpx (deferred import, same pattern as client.py)
  - app.mcp.errors.McpServerUnreachableError

Source refs:
  - MCP specification 2025-06-18 §6.1 Initialization
  - validator P02-S07-T001 CRITICAL-2 finding
  - debugger handoff P02-S07-T001 §Debugger fix — cycle 1
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from app.mcp.errors import McpServerUnreachableError

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_MCP_PROTOCOL_VERSION = "2025-06-18"
_CLIENT_INFO = {"name": "hilo-people-admin", "version": "0.1"}


def _http_post_json(
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
) -> Any:
    """POST a JSON body to ``endpoint`` and return the parsed JSON response.

    Centralised so initialize/notifications/initialized share the same
    error-mapping surface as the JSON-RPC calls in client.py.

    Args:
        endpoint: Full MCP server URL.
        payload:  JSON-RPC request or notification body.
        headers:  HTTP headers.
        timeout:  Request timeout in seconds.

    Returns:
        Parsed JSON body (dict) or None when the server returns an empty
        body (e.g. for notifications).

    Raises:
        McpServerUnreachableError: On any transport, non-2xx, or JSON error.
    """
    try:
        import httpx  # deferred import — same pattern as client.py
    except ImportError as exc:
        raise McpServerUnreachableError(
            f"httpx is not installed; cannot connect to MCP server: {exc}"
        ) from exc

    method = payload.get("method", "<unknown>")
    try:
        with httpx.Client(timeout=timeout) as http:
            response = http.post(endpoint, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        logger.error(
            "mcp.client.handshake.timeout method=%s error=%s",
            method,
            type(exc).__name__,
        )
        raise McpServerUnreachableError(
            f"MCP server timed out after {timeout}s on method {method}"
        ) from exc
    except (httpx.ConnectError, httpx.RequestError) as exc:
        logger.error(
            "mcp.client.handshake.connect_error method=%s error=%s",
            method,
            type(exc).__name__,
        )
        raise McpServerUnreachableError(
            f"Cannot connect to MCP server: {type(exc).__name__}"
        ) from exc
    except Exception as exc:  # last-resort safety net per non-negotiables boundary
        logger.error(
            "mcp.client.handshake.error method=%s error=%s",
            method,
            type(exc).__name__,
        )
        raise McpServerUnreachableError(
            f"Unexpected error connecting to MCP server: {type(exc).__name__}"
        ) from exc

    if not response.is_success:
        logger.error(
            "mcp.client.handshake.non2xx method=%s status=%d",
            method,
            response.status_code,
        )
        raise McpServerUnreachableError(
            f"MCP server returned HTTP {response.status_code} for method {method}"
        )

    if not response.content:
        return None

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise McpServerUnreachableError(
            f"MCP server returned invalid JSON for method {method}"
        ) from exc


def initialize_session(
    *,
    endpoint: str,
    headers: dict[str, str],
    timeout: int,
) -> None:
    """Perform the MCP initialize handshake before any discovery call.

    Per MCP 2025-06-18 §6.1 the client MUST:
      1. POST `initialize` with protocolVersion + capabilities + clientInfo
         and receive a JSON-RPC response containing a `result.protocolVersion`.
      2. POST `notifications/initialized` (a JSON-RPC notification, so no
         `id`, no response expected) to signal the server.

    Only after these two steps may the client invoke tools/list,
    resources/list, prompts/list.

    Args:
        endpoint: Full MCP server URL.
        headers:  HTTP headers (Accept/Content-Type + auth).
        timeout:  Per-request timeout in seconds.

    Raises:
        McpServerUnreachableError: If the handshake fails (network error,
            non-2xx, JSON error, missing JSON-RPC result, missing
            protocolVersion, or JSON-RPC error envelope).
    """
    if _VERBOSE:
        logger.debug(
            "mcp.client.initialize.start protocol_version=%s",
            _MCP_PROTOCOL_VERSION,
        )  # BEFORE

    init_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        },
    }
    body = _http_post_json(endpoint, init_payload, headers, timeout)

    if not isinstance(body, dict):
        raise McpServerUnreachableError(
            "MCP server returned non-object body for initialize"
        )

    if "error" in body:
        err = body["error"]
        logger.error(
            "mcp.client.initialize.rpc_error code=%s",
            err.get("code"),
        )
        raise McpServerUnreachableError(
            f"MCP server initialize RPC error {err.get('code')}: {err.get('message')}"
        )

    result = body.get("result")
    if not isinstance(result, dict) or not result.get("protocolVersion"):
        raise McpServerUnreachableError(
            "MCP server initialize response missing protocolVersion"
        )

    # Send the initialized notification (fire-and-forget; notifications have no `id`).
    initialized_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    _http_post_json(endpoint, initialized_payload, headers, timeout)

    if _VERBOSE:
        logger.debug(
            "mcp.client.initialize.ok protocol_version=%s",
            result.get("protocolVersion"),
        )  # AFTER
