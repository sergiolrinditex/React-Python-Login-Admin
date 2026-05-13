"""
Hilo People — Admin feature package.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints
Phase:  P02 Core Features
Purpose: Re-exports the admin_router for registration in app/main.py.
         This is the public surface of the admin feature module.

         WRITE_SET_DRIFT §D-AAP: This file (backend/app/admin/__init__.py) was
         not in the canonical write_set but is a required Python package marker
         for the new backend/app/admin/ module. Declared explicitly in the
         P02-S05-T001 handoff. Justification: without __init__.py the module
         is not importable; creating it costs 1 file with no business logic.

Exported:
  admin_router — Aggregated APIRouter for all /admin/ai/* endpoints.
                 Mounted under /api/v1/admin/ai by main.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.admin.providers import providers_router
from app.admin.model_catalog import models_router

admin_router = APIRouter()
admin_router.include_router(providers_router)
admin_router.include_router(models_router)

__all__ = ["admin_router"]
