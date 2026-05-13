"""
Hilo People — RAG document admin router aggregator.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Aggregates all RAG document HTTP route handlers into a single
         rag_documents_router. Sub-routers:
           - router_upload.py  — POST /documents (upload)
           - router_list.py    — GET /documents (list with pagination)
           - router_index.py   — POST /documents/{id}/index (enqueue job)

         Mounted in backend/app/main.py (§D-RAGDOCS-MAIN) at:
           prefix="/api/v1/admin/rag", tags=["admin-rag"]

         Aggregator pattern identical to app/mcp/router.py and
         app/admin/providers/__init__.py.

Source refs:
  - task pack P02-S06-T001 §D-RAGDOCS-PKG, §D-RAGDOCS-MAIN
  - 01-non-negotiables.md §File size (aggregator per P-22 pattern)
"""

from __future__ import annotations

from fastapi import APIRouter

from app.rag.documents.router_index import _index_router
from app.rag.documents.router_list import _list_router
from app.rag.documents.router_upload import _upload_router

rag_documents_router = APIRouter()
rag_documents_router.include_router(_upload_router)
rag_documents_router.include_router(_list_router)
rag_documents_router.include_router(_index_router)

__all__ = ["rag_documents_router"]
