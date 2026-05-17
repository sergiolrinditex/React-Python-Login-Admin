"""
Hilo People — Admin audit feature package.

Slice:  P04-S03-T003 — GET /api/v1/admin/audit endpoint
Phase:  P04 Complete Features
Purpose: Python package marker + public surface for the admin/audit feature.
         Re-exports audit_router so main.py can mount it without knowledge
         of the internal module layout.

         WRITE_SET_DRIFT §D-AUDIT-INIT (P04-S03-T003): __init__.py is required
         for Python package resolution. The Coverage Registry write_set listed
         {router, service, repository, schemas, audit}.py explicitly; __init__.py
         is implicit (same precedent as D-AAP in P02-S05-T001 for
         backend/app/admin/__init__.py). Declared in handoff.

Exported:
  audit_router — FastAPI APIRouter for GET /audit.
                 Mounted under /api/v1/admin by main.py
                 (WRITE_SET_DRIFT §D-AUDIT-MAIN) so the route resolves
                 as GET /api/v1/admin/audit.
"""

from __future__ import annotations

from app.admin.audit.router import audit_router

__all__ = ["audit_router"]
