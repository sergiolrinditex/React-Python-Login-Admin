"""
Hilo People — GET /api/v1/admin/rag/documents list router.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: FastAPI route handler for document listing with cursor pagination.
         - require_admin RBAC
         - Optional query filters: collection_id, status, cursor, limit
         - Returns {data:[Document], meta:{pagination:{cursor,limit}}} envelope
         - X-Request-ID in response header (I.9)
         - No PII in logs (A.2.5)

Key deps:
  - app.security.permissions.require_admin
  - app.rag.documents.service_list
  - app.rag.documents.schemas

Source refs:
  - task pack P02-S06-T001 §A.2, §B.2, §H
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.auth.routers._helpers import _error_response, _get_request_id
from app.db.session import get_db_session
from app.db.models.user import User
from app.rag.documents import service_list
from app.rag.documents.errors import DocumentInvalidError
from app.rag.documents.schemas import (
    DocumentListResponse,
    DocumentOut,
    PaginationMeta,
    ResponseMeta,
)
from app.security.permissions import require_admin
from sqlalchemy.orm import Session

logger = logging.getLogger("hilo.rag.documents.router_list")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_list_router = APIRouter()


@_list_router.get("/documents", status_code=200)
async def list_documents(
    request: Request,
    collection_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None, alias="status"),
    cursor: str | None = Query(None),
    limit: int = Query(default=50, ge=1, le=100),
    admin: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """List documents with optional filters and cursor pagination.

    Requires 'people_admin' or 'super_admin' role.

    Args:
        request:       FastAPI Request.
        collection_id: Filter by collection (optional).
        status:        Filter by status (optional; one of uploaded/processing/indexed/failed).
        cursor:        Opaque pagination cursor (optional; None = first page).
        limit:         Page size (1–100, default 50).
        admin:         Authenticated admin user or 401/403 response.
        session:       Database session.

    Returns:
        JSONResponse 200 with {data:[Document], meta:{pagination:{cursor,limit}}}.

    Error codes: 400 RAG_INVALID_PAYLOAD (bad cursor), 401, 403.
    """
    if isinstance(admin, JSONResponse):
        return admin

    request_id = _get_request_id(request)
    t_start = time.monotonic()

    if _VERBOSE:
        logger.debug(
            "rag.documents.list.request.start admin_id=%s "
            "collection_id=%s status=%s has_cursor=%s limit=%d request_id=%s",
            str(admin.id),
            str(collection_id) if collection_id else "none",
            status or "none",
            cursor is not None,
            limit,
            request_id,
        )  # BEFORE

    try:
        rows, next_cursor = service_list.list_documents(
            session=session,
            collection_id=collection_id,
            status_filter=status,
            cursor=cursor,
            limit=limit,
            request_id=request_id,
        )
    except DocumentInvalidError as exc:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning(
            "rag.documents.list.error error_type=DocumentInvalidError "
            "field=%s latency_ms=%s request_id=%s",
            exc.field,
            latency_ms,
            request_id,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_INVALID_PAYLOAD",
            message=exc.reason,
            http_status=400,
            field=exc.field,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except Exception:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.documents.list.error error_type=Unexpected "
            "latency_ms=%s request_id=%s",
            latency_ms,
            request_id,
            exc_info=True,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_INTERNAL_ERROR",
            message="An unexpected error occurred.",
            http_status=500,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp

    doc_list = [DocumentOut.model_validate(row) for row in rows]
    envelope = DocumentListResponse(
        data=doc_list,
        meta=ResponseMeta(
            pagination=PaginationMeta(cursor=next_cursor, limit=limit),
            request_id=request_id,
        ),
    )

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.documents.list.request.ok count=%d has_next=%s "
            "latency_ms=%s request_id=%s",
            len(doc_list),
            next_cursor is not None,
            latency_ms,
            request_id,
        )  # AFTER

    resp = JSONResponse(
        content=envelope.model_dump(mode="json"),
        status_code=200,
    )
    resp.headers["X-Request-ID"] = request_id
    return resp
