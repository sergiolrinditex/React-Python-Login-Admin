"""
Hilo People — Agents domain errors.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Typed exceptions for the Agents subsystem. Routers catch these and
         emit the appropriate HTTP error envelope.

Source refs:
  - task pack P02-S08-T001 §E (endpoint contracts, error codes)
  - 01-non-negotiables.md §Error handling (typed domain errors, no generic catch)
"""

from __future__ import annotations


class AgentError(Exception):
    """Base exception for all Agent domain errors."""


class AgentNotFoundError(AgentError):
    """Raised when a requested agent does not exist in the DB.

    Maps to HTTP 404 with code AGENT_NOT_FOUND.
    """


class AgentDisabledError(AgentError):
    """Raised when an agent exists but is disabled (enabled=False).

    Maps to HTTP 409 with code AGENT_DISABLED.
    Admin-visible because callers are always admins in V1.
    """


class AgentToolNotFoundError(AgentError):
    """Raised when a requested tool_id is not found in mcp_tools.

    Maps to HTTP 400 with code AGENT_TOOL_NOT_FOUND.
    Carries offending_id for field-level error envelope.
    """

    def __init__(self, offending_id: str) -> None:
        """Initialize with the offending tool UUID string."""
        self.offending_id = offending_id
        super().__init__(f"Tool not found: {offending_id}")


class AgentToolNotApprovedError(AgentError):
    """Raised when a tool_id exists but is not approved (enabled=False).

    Maps to HTTP 400 with code AGENT_TOOL_NOT_APPROVED.
    Carries offending_id for field-level error envelope.
    """

    def __init__(self, offending_id: str) -> None:
        """Initialize with the offending tool UUID string."""
        self.offending_id = offending_id
        super().__init__(f"Tool not approved: {offending_id}")


class AgentRunNotFoundError(AgentError):
    """Raised when a requested agent run does not exist in the DB."""


class AgentRunFailedError(AgentError):
    """Raised when the agent execution fails (DeepAgents or MCP error).

    Maps to HTTP 502 with code AGENT_RUN_FAILED.
    """


class McpUnreachableError(AgentError):
    """Raised when the remote MCP server cannot be reached during a run.

    Maps to HTTP 502 with code MCP_SERVER_UNREACHABLE.
    """
