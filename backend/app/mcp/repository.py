"""
Hilo People — MCP repository: public re-export shim.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Single import surface for all MCP repository functions.
         Split into two modules for file-size compliance:
           - repository_servers.py — McpServer + McpCredential CRUD
           - repository_tools.py  — upsert + McpTool CRUD

         This shim re-exports everything from both modules so callers
         can use a single import path. No logic lives here.

Source refs:
  - 01-non-negotiables.md §File size (one responsibility per file,
    target ~200 lines, cap ~300)
"""

from __future__ import annotations

from app.mcp.repository_servers import (
    create_credential,
    create_server,
    get_credential_for_server,
    get_server_by_id,
    list_servers,
    update_server_sync_at,
)
from app.mcp.repository_tools import (
    get_tool_by_id,
    update_tool,
    upsert_prompts,
    upsert_resources,
    upsert_tools,
)

__all__ = [
    # Server ops
    "list_servers",
    "create_server",
    "get_server_by_id",
    "get_credential_for_server",
    "create_credential",
    "update_server_sync_at",
    # Tool ops
    "upsert_tools",
    "upsert_resources",
    "upsert_prompts",
    "get_tool_by_id",
    "update_tool",
]
