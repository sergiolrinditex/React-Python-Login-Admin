"""
Hilo People — Admin feature package.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints
        P02-S07-T001 — MCP server and tool endpoints (added mcp_router, §D-MCPWIRE)
        P02-S08-T001 — Agents endpoints (added agents_admin_router, §D-AGWIRE-ADMIN)
Phase:  P02 Core Features
Purpose: Re-exports the admin_router for registration in app/main.py.
         This is the public surface of the admin feature module.

         WRITE_SET_DRIFT §D-AAP (P02-S05-T001): This file was not in the
         canonical write_set but is a required Python package marker for the
         backend/app/admin/ module. Declared in the P02-S05-T001 handoff.

         WRITE_SET_DRIFT §D-MCPWIRE (P02-S07-T001): mcp_router added to the
         aggregator so the 4 MCP endpoints (/mcp/servers, /mcp/servers/{id}/sync,
         /mcp/tools/{id}) are reachable under /api/v1/admin/ai/mcp/*.
         Justification: without registering the new mcp_router here, the 4
         endpoints are unreachable; reusing the existing admin_router pattern
         avoids touching main.py and keeps wiring DRY (same as providers + models).

         WRITE_SET_DRIFT §D-AGWIRE-ADMIN (P02-S08-T001): agents_admin_router
         added so GET /api/v1/admin/ai/agents and
         PATCH /api/v1/admin/ai/agents/{id}/tools are reachable under the
         /api/v1/admin/ai prefix. Identical pattern to §D-MCPWIRE above.

Exported:
  admin_router — Aggregated APIRouter for all /admin/ai/* endpoints.
                 Mounted under /api/v1/admin/ai by main.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.admin.providers import providers_router
from app.admin.model_catalog import models_router
from app.mcp import mcp_router

admin_router = APIRouter()
admin_router.include_router(providers_router)
admin_router.include_router(models_router)
admin_router.include_router(mcp_router)

# P02-S08-T001 WRITE_SET_DRIFT §D-AGWIRE-ADMIN
# Note: app.agents.audit uses a lazy proxy for write_admin_ai_audit to avoid
# the circular import chain:
#   app.agents.audit → app.admin._audit → app.admin.__init__ → app.agents
# With audit.py using a deferred import at call-time (not import-time),
# this direct module-level import is safe.
from app.agents.router import agents_admin_router  # P02-S08-T001 WRITE_SET_DRIFT §D-AGWIRE-ADMIN
admin_router.include_router(agents_admin_router)  # P02-S08-T001 WRITE_SET_DRIFT §D-AGWIRE-ADMIN

__all__ = ["admin_router"]
