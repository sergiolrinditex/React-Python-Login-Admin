"""
Hilo People — POST /api/v1/admin/rag/documents/{id}/index router.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: FastAPI route handler for enqueuing a vectorization job.
         - require_admin RBAC (I.1)
         - RateLimiter 30/min burst=10 (A.3.8)
         - Returns 202 Accepted with {data:{job_id, status:'pending'}} (A.3.6)
         - Returns 409 if job is already in-flight (A.3.3)
         - Returns 500 on Redis/Celery failure with job rollback (F.8)
         - X-Request-ID in response header (I.9)

Key deps:
  - app.security.permissions.require_admin
  - app.security.rate_limit.RateLimiter
  - app.rag.documents.service_index
  - app.rag.documents.schemas

Source refs:
  - task pack P02-S06-T001 §A.3, §B.3, §F, §H
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.session import get_db_session
from app.db.models.user import User
from app.rag.documents import service_index
from app.rag.documents.errors import (
    DocumentInvalidError,
    IndexDispatchError,
    IndexInProgressError,
)
from app.rag.documents.schemas import IndexJobOut, IndexJobResponse
from app.security.permissions import require_admin
from app.security.rate_limit import RateLimiter
from sqlalchemy.orm import Session

logger = logging.getLogger("hilo.rag.documents.router_index")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_index_limiter = RateLimiter(prefix="RAG_DOC_INDEX", per_minute=30, burst=10)

_index_router = APIRouter()


@_index_router.post("/documents/{document_id}/index", status_code=202)
async def index_document(
    document_id: uuid.UUID,
    request: Request,
    admin: User | JSONResponse = Depends(require_admin),
    _rl: None = Depends(_index_limiter),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Enqueue a vectorization job for an existing document.

    Requires 'people_admin' or 'super_admin' role.
    Rate-limited to 30 req/min (burst=10) per IP.

    Args:
        document_id: UUID of the document to index (path param).
        request:     FastAPI Request.
        admin:       Authenticated admin user or 401/403 response.
        _rl:         Rate limit check or 429/503 response.
        session:     Database session.

    Returns:
        JSONResponse 202 with {data:{job_id, status:'pending'}}.

    Error codes:
        401 AUTH_SESSION_EXPIRED, 403 AUTH_PERMISSION_DENIED,
        404 RAG_DOCUMENT_INVALID (not found),
        409 RAG_INDEX_IN_PROGRESS (in-flight job),
        422 RAG_DOCUMENT_INVALID (no collection_id),
        429 RAG_RATE_LIMITED (via rate limiter),
        500 RAG_INDEX_FAILED (Redis/broker down).
    """
    if isinstance(admin, JSONResponse):
        return admin
    if isinstance(_rl, JSONResponse):
        return _rl

    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    t_start = time.monotonic()

    if _VERBOSE:
        logger.debug(
            "rag.documents.index.request.start document_id=%s admin_id=%s request_id=%s",
            str(document_id),
            str(admin.id),
            request_id,
        )  # BEFORE

    try:
        job = service_index.index_document(
            session=session,
            document_id=document_id,
            admin_user_id=admin.id,
            request_id=request_id,
            client_ip=client_ip,
        )
    except DocumentInvalidError as exc:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        # field='id' means 404; anything else is 422
        http_status = 404 if exc.field == "id" else 422
        code = "RAG_DOCUMENT_INVALID"
        logger.warning(
            "rag.documents.index.error error_type=DocumentInvalidError "
            "field=%s status=%d latency_ms=%s request_id=%s",
            exc.field,
            http_status,
            latency_ms,
            request_id,
        )
        resp = _error_response(
            request_id=request_id,
            code=code,
            message=exc.reason,
            http_status=http_status,
            field=exc.field,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except IndexInProgressError as exc:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning(
            "rag.documents.index.error error_type=IndexInProgressError "
            "job_id=%s status=%s latency_ms=%s request_id=%s",
            exc.job_id,
            exc.status,
            latency_ms,
            request_id,
        )
        envelope = {
            "errors": [
                {
                    "code": "RAG_INDEX_IN_PROGRESS",
                    "message": f"A vectorization job is already {exc.status}.",
                }
            ],
            "data": {"job_id": exc.job_id, "status": exc.status},
        }
        resp = JSONResponse(content=envelope, status_code=409)
        resp.headers["X-Request-ID"] = request_id
        return resp
    except IndexDispatchError:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.documents.index.error error_type=IndexDispatchError "
            "latency_ms=%s request_id=%s",
            latency_ms,
            request_id,
            exc_info=True,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_INDEX_FAILED",
            message="Failed to dispatch indexing job. Please retry.",
            http_status=500,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except Exception:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.documents.index.error error_type=Unexpected "
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

    job_out = IndexJobOut(job_id=job.id, status=job.status)
    envelope = IndexJobResponse(data=job_out)
    latency_ms = round((time.monotonic() - t_start) * 1000, 1)

    if _VERBOSE:
        logger.debug(
            "rag.documents.index.request.ok job_id=%s document_id=%s "
            "latency_ms=%s request_id=%s",
            str(job.id),
            str(document_id),
            latency_ms,
            request_id,
        )  # AFTER

    resp = JSONResponse(
        content=envelope.model_dump(mode="json"),
        status_code=202,
    )
    resp.headers["X-Request-ID"] = request_id
    return resp
