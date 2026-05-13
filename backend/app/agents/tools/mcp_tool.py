"""
Hilo People — Agent MCP tool: wraps MCP tool calls as a LangChain BaseTool.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Provides a LangChain BaseTool subclass that delegates invocations
         to the existing app.mcp.client JSON-RPC layer (D-CLIENT-OFFICIAL).

         Decision R-3 (task pack §J): no canonical LangChain-MCP adapter was
         available at pin time, so we implement a thin custom BaseTool
         subclass that calls app.mcp.client. This keeps the mock boundary
         (app.mcp.client HTTP layer) consistent with TC16 (MCP unreachable).

         Each McpToolWrapper is bound to ONE tool_id + ONE agent_run_id at
         construction time so audit rows can be written per-invocation without
         requiring the tool to own a DB session.

         Audit responsibility: the run executor (service_start_run) writes
         mcp_tool_invocations rows after each _run() call using the returned
         InvocationResult.

Key deps:
  - langchain_core.tools.BaseTool
  - app.mcp.client (call_tool — JSON-RPC over httpx)

Source refs:
  - task pack P02-S08-T001 §D.2 (tools/mcp_tool.py), §J R-3
  - instrucciones.md §3.1#mcp-agents (toda invocación auditada)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.agents.errors import McpUnreachableError
from app.mcp.errors import McpServerUnreachableError

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


@dataclass
class InvocationResult:
    """Container for an MCP tool invocation outcome.

    Attributes:
        tool_id:        UUID of the mcp_tools row.
        arguments_json: Arguments sent to the tool.
        result_json:    Response dict (None on error).
        status:         'success' | 'error'.
        latency_ms:     Execution time in milliseconds.
        error:          Error message (None on success).
    """

    tool_id: uuid.UUID
    arguments_json: dict[str, Any]
    result_json: dict[str, Any] | None
    status: str
    latency_ms: int | None
    error: str | None = None


def _call_mcp_tool(
    *,
    endpoint: str,
    auth_type: str,
    secret: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    timeout: int = 10,
) -> Any:
    """Execute a tools/call JSON-RPC 2.0 request against an MCP server.

    This is the mock boundary for TC16 (MCP unreachable test):
    monkeypatch `app.agents.tools.mcp_tool._call_mcp_tool` in tests.

    Args:
        endpoint:   Full MCP server URL.
        auth_type:  Credential type.
        secret:     Plaintext secret (NEVER logged).
        tool_name:  MCP tool name to invoke.
        arguments:  Arguments dict for the tool.
        timeout:    Request timeout in seconds.

    Returns:
        The result from the JSON-RPC response.

    Raises:
        McpServerUnreachableError: On transport or server error.
    """
    try:
        import httpx  # deferred — not available at module-level in all envs
    except ImportError as exc:
        raise McpServerUnreachableError(
            f"httpx not installed: {exc}"
        ) from exc

    headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth_type not in ("none", "") and secret:
        headers["Authorization"] = f"Bearer {secret}"
        if auth_type == "api_key":
            headers["X-API-Key"] = secret  # some servers use X-API-Key

    import uuid as _uuid
    payload = {
        "jsonrpc": "2.0",
        "id": str(_uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    if _VERBOSE:
        logger.debug(
            "agents.tools.mcp_tool._call.start tool_name=%s auth_type=%s",
            tool_name, auth_type,
        )  # BEFORE

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise McpServerUnreachableError(f"MCP tool call timed out: {exc}") from exc
    except (httpx.ConnectError, httpx.RequestError) as exc:
        raise McpServerUnreachableError(f"Cannot connect to MCP server: {exc}") from exc

    if not response.is_success:
        raise McpServerUnreachableError(
            f"MCP server returned HTTP {response.status_code} for tools/call"
        )

    import json as _json
    try:
        body = response.json()
    except _json.JSONDecodeError as exc:
        raise McpServerUnreachableError("MCP server returned invalid JSON") from exc

    if "error" in body:
        err = body["error"]
        raise McpServerUnreachableError(
            f"MCP RPC error {err.get('code')}: {err.get('message')}"
        )

    if _VERBOSE:
        logger.debug("agents.tools.mcp_tool._call.ok tool_name=%s", tool_name)  # AFTER

    return body.get("result", {})


class _McpInput(BaseModel):
    """Input schema for the MCP tool wrapper (generic arguments dict)."""

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the MCP tool.",
    )


class McpToolWrapper(BaseTool):
    """LangChain BaseTool that delegates to a specific MCP tool via JSON-RPC.

    Each instance wraps one MCP tool and records invocation metadata for the
    audit trail. The run executor collects results via `last_result`.
    """

    name: str
    description: str
    args_schema: type[BaseModel] = _McpInput
    return_direct: bool = False

    # Non-schema fields — injected at construction time
    tool_id: uuid.UUID = Field(exclude=True)
    tool_name_mcp: str = Field(exclude=True)  # the actual MCP tool name
    endpoint_url: str = Field(exclude=True)
    auth_type: str = Field(exclude=True)
    plaintext_secret: str | None = Field(default=None, exclude=True)
    last_result: InvocationResult | None = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _run(self, arguments: dict[str, Any] | None = None) -> str:
        """Invoke the MCP tool via JSON-RPC HTTP call.

        Args:
            arguments: Dict of arguments to pass to the tool.

        Returns:
            String representation of the tool result.

        Side effects:
            Sets self.last_result with invocation metadata for audit writing.

        Raises:
            McpUnreachableError: If the MCP server cannot be reached.
        """
        args = arguments or {}
        start_ms = int(time.time() * 1000)

        if _VERBOSE:
            logger.debug(
                "agents.tools.mcp_tool.run.start tool_id=%s tool_name=%s",
                str(self.tool_id), self.tool_name_mcp,
            )  # BEFORE

        try:
            raw_result = _call_mcp_tool(
                endpoint=self.endpoint_url,
                auth_type=self.auth_type,
                secret=self.plaintext_secret,
                tool_name=self.tool_name_mcp,
                arguments=args,
            )
            latency_ms = int(time.time() * 1000) - start_ms

            result_json: dict[str, Any] = {"output": raw_result} if isinstance(raw_result, str) else (raw_result or {})
            output_str = str(raw_result)[:2000]  # truncate for LLM context

            self.last_result = InvocationResult(
                tool_id=self.tool_id,
                arguments_json=args,
                result_json=result_json,
                status="success",
                latency_ms=latency_ms,
            )

            if _VERBOSE:
                logger.debug(
                    "agents.tools.mcp_tool.run.ok tool_id=%s latency_ms=%d",
                    str(self.tool_id), latency_ms,
                )  # AFTER
            return output_str

        except McpUnreachableError:
            raise
        except Exception as exc:
            latency_ms = int(time.time() * 1000) - start_ms
            err_msg = f"{type(exc).__name__}: {str(exc)[:200]}"
            logger.error(
                "agents.tools.mcp_tool.run.error tool_id=%s error=%s",
                str(self.tool_id), type(exc).__name__, exc_info=True,
            )
            self.last_result = InvocationResult(
                tool_id=self.tool_id,
                arguments_json=args,
                result_json=None,
                status="error",
                latency_ms=latency_ms,
                error=err_msg,
            )
            return f"Tool invocation failed: {err_msg}"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """Async variant — delegates to synchronous _run."""
        return self._run(*args, **kwargs)


def build_mcp_tool_wrapper(
    *,
    tool_id: uuid.UUID,
    tool_name: str,
    tool_description: str,
    endpoint_url: str,
    auth_type: str,
    plaintext_secret: str | None,
) -> McpToolWrapper:
    """Factory for a single MCP tool wrapper instance.

    Args:
        tool_id:          UUID of the mcp_tools row.
        tool_name:        Human-readable tool name (used as BaseTool.name).
        tool_description: Tool description for the LLM.
        endpoint_url:     MCP server HTTP endpoint.
        auth_type:        Credential type.
        plaintext_secret: Decrypted secret (None for public servers).

    Returns:
        McpToolWrapper configured for this tool.
    """
    return McpToolWrapper(
        name=tool_name,
        description=tool_description,
        tool_id=tool_id,
        tool_name_mcp=tool_name,
        endpoint_url=endpoint_url,
        auth_type=auth_type,
        plaintext_secret=plaintext_secret,
    )
