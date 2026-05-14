"""
Hilo People — FastAPI router for RAG collection admin endpoints.

Slice:  P02-S06-T002 — RAG collection endpoints (§D-RAGCOLL-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Defines two admin-only endpoints:
           GET  /api/v1/admin/rag/collections       — list all collections
           PATCH /api/v1/admin/rag/collections/{id} — update collection fields
         Enforces RBAC (require_admin), propagates X-Request-ID, and returns
         the standard {data, meta, errors} envelope.

Key deps:
  - app.rag.collections.service
  - app.rag.collections.schemas
  - app.rag.collections.errors
  - app.security.permissions.require_admin
  - app.auth.routers._helpers._error_response, _get_request_id
  - app.db.session.get_db_session

Source refs:
  - task pack P02-S06-T002 §H (frozen endpoint contracts)
  - TECHNICAL_GUIDE §6.2#rag-collections
  - 01-non-negotiables.md §Logging, §API contract
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.routers._helpers import _error_response, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.rag.collections import service
from app.rag.collections.errors import CollectionInvalidError, CollectionNotFoundError
from app.rag.collections.schemas import (
    CollectionListResponse,
    CollectionOut,
    CollectionPatchIn,
    CollectionPatchResponse,
    ResponseMeta,
)
from app.security.permissions import require_admin

logger = logging.getLogger("hilo.rag.collections.router")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

rag_collections_router = APIRouter()


@rag_collections_router.get("/collections", status_code=200)
async def list_collections(
    request: Request,
    admin: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """List all RAG collections (admin-only).

    Returns all rag_collections rows ordered by name ASC. No pagination in V1
    (§H.1 decision — O(10) collections; cursor can be added in a future slice).

    Args:
        request: FastAPI Request (for X-Request-ID).
        admin:   Authenticated admin user or 401/403 JSONResponse.
        session: DB session.

    Returns:
        200 {data:[CollectionOut], meta:{request_id}}
        401 if no/invalid token.
        403 if employee or auditor role.
    """
    if isinstance(admin, JSONResponse):
        return admin

    request_id = _get_request_id(request)
    t_start = time.monotonic()

    if _VERBOSE:
        logger.debug(
            "rag.collections.router.list.start admin_id=%s request_id=%s",
            str(admin.id),
            request_id,
        )  # BEFORE

    try:
        rows = service.list_collections(session=session, request_id=request_id)
    except Exception:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.collections.router.list.error error_type=Unexpected "
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

    collection_list = [CollectionOut.model_validate(row) for row in rows]
    envelope = CollectionListResponse(
        data=collection_list,
        meta=ResponseMeta(request_id=request_id),
    )

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.collections.router.list.ok count=%d latency_ms=%s request_id=%s",
            len(collection_list),
            latency_ms,
            request_id,
        )  # AFTER

    resp = JSONResponse(content=envelope.model_dump(mode="json"), status_code=200)
    resp.headers["X-Request-ID"] = request_id
    return resp


@rag_collections_router.patch("/collections/{collection_id}", status_code=200)
async def update_collection(
    collection_id: uuid.UUID,
    patch: CollectionPatchIn,
    request: Request,
    admin: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Update a RAG collection's editable fields (admin-only).

    Allows partial updates to name, vertical, language, and/or enabled.
    Writes an audit_log row on success (action=admin.rag.collection.update).

    Args:
        collection_id: UUID path parameter — collection to update.
        patch:         Validated patch body (CollectionPatchIn).
        request:       FastAPI Request (for X-Request-ID, IP, User-Agent).
        admin:         Authenticated admin user or 401/403 JSONResponse.
        session:       DB session.

    Returns:
        200 {data:CollectionOut, meta:{request_id}} on success.
        400 RAG_INVALID_PAYLOAD on empty name/vertical after trim.
        401 if no/invalid token.
        403 if employee or auditor.
        404 RAG_COLLECTION_NOT_FOUND if UUID not in rag_collections.
        422 for malformed UUID path param or Pydantic body validation failure.
    """
    if isinstance(admin, JSONResponse):
        return admin

    request_id = _get_request_id(request)
    ip = request.headers.get("X-Forwarded-For", "") or (
        request.client.host if request.client else ""
    )
    user_agent = request.headers.get("User-Agent", "")
    t_start = time.monotonic()

    if _VERBOSE:
        changed = service._field_names(patch)
        logger.debug(
            "rag.collections.router.update.start admin_id=%s "
            "collection_id=%s fields=%s request_id=%s",
            str(admin.id),
            str(collection_id),
            changed,
            request_id,
        )  # BEFORE — field names only

    try:
        row = service.update_collection(
            session=session,
            collection_id=collection_id,
            patch=patch,
            admin_id=admin.id,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
    except CollectionInvalidError as exc:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning(
            "rag.collections.router.update.error error_type=CollectionInvalidError "
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
    except CollectionNotFoundError:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning(
            "rag.collections.router.update.error error_type=CollectionNotFoundError "
            "collection_id=%s latency_ms=%s request_id=%s",
            str(collection_id),
            latency_ms,
            request_id,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_COLLECTION_NOT_FOUND",
            message="Collection not found.",
            http_status=404,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except Exception:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.collections.router.update.error error_type=Unexpected "
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

    out = CollectionOut.model_validate(row)
    envelope = CollectionPatchResponse(
        data=out,
        meta=ResponseMeta(request_id=request_id),
    )

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.collections.router.update.ok admin_id=%s collection_id=%s "
            "latency_ms=%s request_id=%s",
            str(admin.id),
            str(collection_id),
            latency_ms,
            request_id,
        )  # AFTER

    resp = JSONResponse(content=envelope.model_dump(mode="json"), status_code=200)
    resp.headers["X-Request-ID"] = request_id
    return resp
