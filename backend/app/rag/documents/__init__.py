"""
Hilo People — RAG document admin subpackage.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Public API re-export for the rag.documents subpackage.
         Exposes rag_documents_router for mounting in app/main.py.

         Internal modules:
           - router.py          — APIRouter aggregator
           - router_upload.py   — POST /documents
           - router_list.py     — GET /documents
           - router_index.py    — POST /documents/{id}/index
           - service_upload.py  — UploadDocument use case
           - service_list.py    — ListDocuments use case
           - service_index.py   — IndexDocument use case
           - repository.py      — DB operations
           - schemas.py         — Pydantic v2 schemas
           - errors.py          — Typed domain errors
           - storage.py         — MinIO put_object wrapper
           - audit.py           — audit_log thin wrappers
           - cursor.py          — Cursor-based pagination

         WRITE_SET_DRIFT §D-RAGDOCS-PKG: single-file documents.py split into
         this subpackage per task pack §D.1 predeclaration.

Source refs:
  - task pack P02-S06-T001 §D-RAGDOCS-PKG, §D-RAGDOCS-MAIN
"""

from app.rag.documents.router import rag_documents_router

__all__ = ["rag_documents_router"]
