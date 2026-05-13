"""
Hilo People — Agents router aggregator.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Assembles the two agents APIRouters from sub-modules:
           - router_agents.py: GET /agents + PATCH /agents/{id}/tools
             (admin-scoped, mounted under /api/v1/admin/ai via admin/__init__.py)
           - router_runs.py:   POST /agents/runs
             (admin-scoped, mounted under /api/v1 directly via main.py)

         Exports:
           agents_admin_router — includes /agents prefix, for admin aggregator.
           agents_runs_router  — includes /agents/runs at root /api/v1 prefix.

Source refs:
  - task pack P02-S08-T001 §D.3 (admin router wiring, WRITE_SET_DRIFT proposals)
  - 01-non-negotiables.md §File size
"""

from __future__ import annotations

from fastapi import APIRouter

from app.agents.router_agents import _agents_router
from app.agents.router_runs import _runs_router

# Admin-scoped router — mounted under /api/v1/admin/ai by admin/__init__.py
# Results in: GET /api/v1/admin/ai/agents
#             PATCH /api/v1/admin/ai/agents/{id}/tools
# No prefix here: _agents_router paths already start with /agents
agents_admin_router = APIRouter(tags=["admin-ai"])
agents_admin_router.include_router(_agents_router)

# Runs router — mounted under /api/v1 by main.py
# Results in: POST /api/v1/agents/runs
agents_runs_router = APIRouter(tags=["agents"])
agents_runs_router.include_router(_runs_router)

__all__ = ["agents_admin_router", "agents_runs_router"]
