"""
Hilo People — MCP domain errors.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Typed exceptions for the MCP subsystem. Routers catch these and
         emit the appropriate HTTP error envelope.

Source refs:
  - task pack P02-S07-T001 §Error envelope + códigos
  - 01-non-negotiables.md §Error handling (typed domain errors, no generic catch)
"""

from __future__ import annotations


class McpError(Exception):
    """Base exception for all MCP domain errors."""


class McpServerNotFoundError(McpError):
    """Raised when a requested MCP server does not exist in the DB."""


class McpToolNotFoundError(McpError):
    """Raised when a requested MCP tool does not exist in the DB."""


class McpServerUnreachableError(McpError):
    """Raised when the remote MCP server cannot be reached or returns an error.

    Maps to 502 Bad Gateway with error code MCP_SERVER_UNREACHABLE.
    """
