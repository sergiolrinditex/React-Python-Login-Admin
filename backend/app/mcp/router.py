"""
Hilo People — MCP router aggregator.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Aggregates all MCP HTTP route handlers into a single mcp_router.
         Handlers live in:
           - router_servers.py (GET /servers, POST /servers, POST /servers/{id}/sync)
           - router_tools.py   (PATCH /tools/{id})

         This module builds the top-level mcp_router with prefix /mcp so that
         admin/__init__.py can include it cleanly under /api/v1/admin/ai.

Source refs:
  - task pack P02-S07-T001 §WRITE_SET_DRIFT §D-MCPWIRE
  - 01-non-negotiables.md §File size
"""

from __future__ import annotations

from fastapi import APIRouter

from app.mcp.router_servers import _servers_router
from app.mcp.router_tools import _tools_router

mcp_router = APIRouter(prefix="/mcp", tags=["admin-ai"])
mcp_router.include_router(_servers_router)
mcp_router.include_router(_tools_router)

__all__ = ["mcp_router"]
