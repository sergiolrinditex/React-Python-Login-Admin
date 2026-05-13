"""
Hilo People — Agents feature package.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Re-exports routers for registration in app/admin/__init__.py
         and app/main.py.

         WRITE_SET_DRIFT §D-AGWIRE-ADMIN (app/admin/__init__.py +3 lines):
           agents_admin_router is included in the admin aggregator so
           GET /api/v1/admin/ai/agents and PATCH /api/v1/admin/ai/agents/{id}/tools
           are reachable under /api/v1/admin/ai/agents*.

         WRITE_SET_DRIFT §D-AGWIRE-MAIN (app/main.py +2 lines):
           agents_runs_router mounted at /api/v1 so
           POST /api/v1/agents/runs is reachable outside the admin prefix.

Exported:
  agents_admin_router — APIRouter for admin-scoped agent management endpoints.
  agents_runs_router  — APIRouter for POST /agents/runs (admin-scoped invoke).
"""

from __future__ import annotations

from app.agents.router import agents_admin_router, agents_runs_router

__all__ = ["agents_admin_router", "agents_runs_router"]
