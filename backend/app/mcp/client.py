"""
Hilo People — MCP discovery client (JSON-RPC over HTTP/SSE).

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Thin HTTP client that calls tools/list, resources/list, and
         prompts/list on a remote MCP server and returns parsed discovery
         results. Wraps transport errors as McpServerUnreachableError.

         Decision D-CLIENT-OFFICIAL: The researcher confirmed that the
         `mcp` PyPI package (modelcontextprotocol.io) provides an async
         client. For this slice, which is synchronous (D-1: sync inline),
         we use httpx (already in deps) as a direct JSON-RPC-over-HTTP
         client. This avoids the asyncio event-loop boundary and keeps the
         service layer synchronous. The MCP spec's HTTP transport is a simple
         POST with JSON-RPC 2.0 bodies — no spec-breaking behaviour.

         Auth injection: the credential dict (auth_type, plaintext_secret)
         is injected into the httpx.Client as a Bearer/API-key header. The
         plaintext secret is used only in-memory during the sync call and
         is never persisted or logged.

         Timeout: configurable via MCP_DISCOVERY_TIMEOUT_SECONDS env var
         (default 10s). On timeout or connection error → McpServerUnreachableError.

Key deps:
  - httpx (already in pyproject.toml via litellm transitive / installed)
  - app.mcp.errors.McpServerUnreachableError

Source refs:
  - task pack P02-S07-T001 §MCP client, §D-CLIENT-OFFICIAL
  - MCP specification HTTP transport §2.3 (JSON-RPC 2.0 POST)
  - 01-non-negotiables.md §Error handling (typed errors, no generic catch)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from app.mcp.client_handshake import initialize_session
from app.mcp.errors import McpServerUnreachableError

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_DEFAULT_TIMEOUT = int(os.getenv("MCP_DISCOVERY_TIMEOUT_SECONDS", "10"))


def _build_headers(auth_type: str, secret: str | None) -> dict[str, str]:
    """Build HTTP headers for the outbound MCP request.

    Args:
        auth_type: 'api_key', 'bearer', 'oauth2', or 'none'.
        secret:    Plaintext secret (never logged).

    Returns:
        Dict of HTTP headers to include in the request.
    """
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if auth_type == "none" or not secret:
        return headers
    if auth_type in ("bearer", "oauth2"):
        headers["Authorization"] = f"Bearer {secret}"
    elif auth_type == "api_key":
        headers["Authorization"] = f"Bearer {secret}"
        # Some MCP servers accept X-API-Key; use Bearer as primary.
        headers["X-API-Key"] = secret
    return headers


def _json_rpc_call(
    endpoint: str,
    method: str,
    headers: dict[str, str],
    timeout: int,
) -> Any:
    """Execute a single JSON-RPC 2.0 POST request.

    Args:
        endpoint: Full MCP server URL (e.g. https://mcp.example.com/mcp).
        method:   JSON-RPC method name (e.g. 'tools/list').
        headers:  HTTP headers including auth.
        timeout:  Request timeout in seconds.

    Returns:
        The 'result' field from the JSON-RPC response.

    Raises:
        McpServerUnreachableError: On connection error, timeout, or non-2xx.
    """
    try:
        import httpx  # deferred import — not available at module level in test env
    except ImportError as exc:
        raise McpServerUnreachableError(
            f"httpx is not installed; cannot connect to MCP server: {exc}"
        ) from exc

    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {},
    }

    if _VERBOSE:
        logger.debug(
            "mcp.client.json_rpc.start method=%s endpoint_len=%d",
            method,
            len(endpoint),
        )  # BEFORE — no endpoint URL logged (could contain secrets in query string)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        logger.error(
            "mcp.client.json_rpc.timeout method=%s error=%s",
            method,
            type(exc).__name__,
        )
        raise McpServerUnreachableError(
            f"MCP server timed out after {timeout}s on method {method}"
        ) from exc
    except (httpx.ConnectError, httpx.RequestError) as exc:
        logger.error(
            "mcp.client.json_rpc.connect_error method=%s error=%s",
            method,
            type(exc).__name__,
        )
        raise McpServerUnreachableError(
            f"Cannot connect to MCP server: {type(exc).__name__}"
        ) from exc
    except Exception as exc:
        logger.error(
            "mcp.client.json_rpc.error method=%s error=%s",
            method,
            type(exc).__name__,
        )
        raise McpServerUnreachableError(
            f"Unexpected error connecting to MCP server: {type(exc).__name__}"
        ) from exc

    if not response.is_success:
        logger.error(
            "mcp.client.json_rpc.non2xx method=%s status=%d",
            method,
            response.status_code,
        )
        raise McpServerUnreachableError(
            f"MCP server returned HTTP {response.status_code} for method {method}"
        )

    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise McpServerUnreachableError(
            f"MCP server returned invalid JSON for method {method}"
        ) from exc

    if "error" in body:
        err = body["error"]
        logger.error(
            "mcp.client.json_rpc.rpc_error method=%s code=%s",
            method,
            err.get("code"),
        )
        raise McpServerUnreachableError(
            f"MCP server RPC error {err.get('code')}: {err.get('message')}"
        )

    if _VERBOSE:
        logger.debug(
            "mcp.client.json_rpc.ok method=%s", method
        )  # AFTER

    return body.get("result", {})


def discover(
    *,
    endpoint: str,
    auth_type: str,
    secret: str | None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Discover tools, resources, and prompts from a remote MCP server.

    This function is the public interface of the MCP client. It calls three
    JSON-RPC methods and normalises the results into flat Python dicts.

    Args:
        endpoint:  Full URL of the MCP server endpoint.
        auth_type: Credential type ('none', 'api_key', 'bearer', 'oauth2').
        secret:    Plaintext secret (never logged — only used for auth headers).
        timeout:   Per-request timeout in seconds.

    Returns:
        Tuple of (tools, resources, prompts) — each a list of dicts ready
        for upsert_tools/upsert_resources/upsert_prompts.

    Raises:
        McpServerUnreachableError: On any transport or server error.
    """
    if _VERBOSE:
        logger.debug(
            "mcp.client.discover.start auth_type=%s timeout=%ds",
            auth_type,
            timeout,
        )  # BEFORE — endpoint not logged (may contain query params with tokens)

    headers = _build_headers(auth_type, secret)

    # MCP §6.1 lifecycle: initialize + notifications/initialized BEFORE any
    # tools/list, resources/list, prompts/list call. Spec-compliant servers
    # reject discovery calls prior to the handshake. (Debugger cycle 1 fix
    # for validator CRITICAL-2 / P02-S07-T001.)
    initialize_session(endpoint=endpoint, headers=headers, timeout=timeout)

    # Discover tools
    tools_result = _json_rpc_call(endpoint, "tools/list", headers, timeout)
    raw_tools = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
    tools = [
        {
            "name": t.get("name", ""),
            "description": t.get("description"),
            "input_schema": t.get("inputSchema") or t.get("input_schema") or {},
            "output_schema": t.get("outputSchema") or t.get("output_schema") or {},
        }
        for t in raw_tools
        if t.get("name")
    ]

    # Discover resources
    resources_result = _json_rpc_call(endpoint, "resources/list", headers, timeout)
    raw_resources = (
        resources_result.get("resources", [])
        if isinstance(resources_result, dict)
        else []
    )
    resources = [
        {
            "uri": r.get("uri", ""),
            "name": r.get("name"),
            "mime_type": r.get("mimeType") or r.get("mime_type"),
            "description": r.get("description"),
        }
        for r in raw_resources
        if r.get("uri")
    ]

    # Discover prompts
    prompts_result = _json_rpc_call(endpoint, "prompts/list", headers, timeout)
    raw_prompts = (
        prompts_result.get("prompts", [])
        if isinstance(prompts_result, dict)
        else []
    )
    prompts = [
        {
            "name": p.get("name", ""),
            "description": p.get("description"),
            "arguments_schema": p.get("arguments") or {},
        }
        for p in raw_prompts
        if p.get("name")
    ]

    if _VERBOSE:
        logger.debug(
            "mcp.client.discover.ok tools=%d resources=%d prompts=%d",
            len(tools),
            len(resources),
            len(prompts),
        )  # AFTER
    return tools, resources, prompts
