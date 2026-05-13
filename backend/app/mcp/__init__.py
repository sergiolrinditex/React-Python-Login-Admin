"""
Hilo People — MCP feature package.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Re-exports the mcp_router for registration in app/admin/__init__.py.
         This is the public surface of the MCP feature module.

         WRITE_SET_DRIFT §D-MCPWIRE: The admin aggregator
         (backend/app/admin/__init__.py) was extended to include mcp_router.
         This is required to make the 4 MCP endpoints reachable under
         /api/v1/admin/ai/mcp/*. Declared explicitly in the P02-S07-T001
         handoff. Justification: without this, the endpoints are unreachable;
         reusing the admin_router aggregator avoids touching main.py and keeps
         wiring DRY (same pattern as providers + model_catalog).

Exported:
  mcp_router — APIRouter for all /admin/ai/mcp/* endpoints.
               Included in admin_router aggregator by app/admin/__init__.py.
"""

from __future__ import annotations

from app.mcp.router import mcp_router

__all__ = ["mcp_router"]
