"""
Hilo People — POST /api/v1/admin/rag/documents upload router.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: FastAPI route handler for document upload.
         - require_admin RBAC (I.1)
         - RateLimiter 20/min burst=5 (A.1.10)
         - Content-Length precheck layer-1 (A.1.3)
         - Delegates to service_upload.upload_document
         - Returns 201 (new) or 200 (dedup) with DocumentCreateResponse envelope
         - Returns X-Request-ID in response header (§H, I.9)

Key deps:
  - app.security.permissions.require_admin
  - app.security.rate_limit.RateLimiter
  - app.rag.documents.service_upload
  - app.rag.documents.schemas

Source refs:
  - task pack P02-S06-T001 §A.1, §B.1, §H
  - 01-non-negotiables.md §API contract, §Logging, §Security
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import JSONResponse

from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.session import get_db_session
from app.db.models.user import User
from app.rag.documents import service_upload
from app.rag.documents.errors import (
    CollectionNotFoundError,
    DocumentInvalidError,
    DocumentTooLargeError,
    StoragePutError,
)
from app.rag.documents.schemas import (
    DocumentCreateResponse,
    DocumentOut,
    DocumentUploadForm,
)
from app.security.permissions import require_admin
from app.security.rate_limit import RateLimiter
from sqlalchemy.orm import Session

logger = logging.getLogger("hilo.rag.documents.router_upload")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_upload_limiter = RateLimiter(prefix="RAG_DOC_CREATE", per_minute=20, burst=5)

_upload_router = APIRouter()


@_upload_router.post("/documents", status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile,
    form: DocumentUploadForm = Depends(DocumentUploadForm),
    admin: User | JSONResponse = Depends(require_admin),
    _rl: None = Depends(_upload_limiter),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Upload a PDF or DOCX document to a RAG collection.

    Requires 'people_admin' or 'super_admin' role.
    Rate-limited to 20 req/min (burst=5) per IP.

    Args:
        request: FastAPI Request (for headers).
        file:    Uploaded binary (multipart/form-data).
        form:    Form fields (title, language, collection_id).
        admin:   Authenticated admin user (or 401/403 JSONResponse).
        _rl:     Rate limit check (or 429/503 JSONResponse).
        session: Database session.

    Returns:
        JSONResponse 201 (new document) or 200 (sha256 dedup hit).

    Error codes: 401 AUTH_SESSION_EXPIRED, 403 AUTH_PERMISSION_DENIED,
                 413 RAG_DOCUMENT_TOO_LARGE, 422 RAG_DOCUMENT_INVALID,
                 429 RAG_RATE_LIMITED (via rate limiter), 500 RAG_STORAGE_FAILED.
    """
    # Propagate 401/403 from RBAC dep.
    if isinstance(admin, JSONResponse):
        return admin
    # Propagate 429/503 from rate limiter.
    if isinstance(_rl, JSONResponse):
        return _rl

    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")[:512]
    t_start = time.monotonic()

    if _VERBOSE:
        logger.debug(
            "rag.documents.upload.request.start admin_id=%s "
            "content_type=%s request_id=%s",
            str(admin.id),
            file.content_type or "unknown",
            request_id,
        )  # BEFORE

    # Layer-1 size cap from Content-Length header
    content_length: int | None = None
    raw_cl = request.headers.get("content-length")
    if raw_cl:
        try:
            content_length = int(raw_cl)
        except ValueError:
            pass

    try:
        doc, http_status = await service_upload.upload_document(
            session=session,
            file=file,
            title=form.title,
            language=form.language,
            collection_id=form.collection_id,
            admin_user_id=admin.id,
            content_length_header=content_length,
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )
    except DocumentTooLargeError:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning(
            "rag.documents.upload.error error_type=DocumentTooLargeError "
            "latency_ms=%s request_id=%s",
            latency_ms,
            request_id,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_DOCUMENT_TOO_LARGE",
            message=f"File exceeds the {int(os.getenv('MAX_UPLOAD_MB','25'))} MiB upload limit.",
            http_status=413,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except DocumentInvalidError as exc:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning(
            "rag.documents.upload.error error_type=DocumentInvalidError "
            "field=%s latency_ms=%s request_id=%s",
            exc.field,
            latency_ms,
            request_id,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_DOCUMENT_INVALID",
            message=exc.reason,
            http_status=422,
            field=exc.field,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except CollectionNotFoundError as exc:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning(
            "rag.documents.upload.error error_type=CollectionNotFoundError "
            "latency_ms=%s request_id=%s",
            latency_ms,
            request_id,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_DOCUMENT_INVALID",
            message=f"Collection {exc.collection_id} does not exist.",
            http_status=422,
            field="collection_id",
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except StoragePutError:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.documents.upload.error error_type=StoragePutError "
            "latency_ms=%s request_id=%s",
            latency_ms,
            request_id,
            exc_info=True,
        )
        resp = _error_response(
            request_id=request_id,
            code="RAG_STORAGE_FAILED",
            message="Storage upload failed. Please retry.",
            http_status=500,
        )
        resp.headers["X-Request-ID"] = request_id
        return resp
    except Exception:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.documents.upload.error error_type=Unexpected "
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

    doc_out = DocumentOut.model_validate(doc)
    envelope = DocumentCreateResponse(data=doc_out)
    latency_ms = round((time.monotonic() - t_start) * 1000, 1)

    if _VERBOSE:
        logger.debug(
            "rag.documents.upload.request.ok document_id=%s status=%d "
            "latency_ms=%s request_id=%s",
            str(doc.id),
            http_status,
            latency_ms,
            request_id,
        )  # AFTER

    resp = JSONResponse(content=envelope.model_dump(mode="json"), status_code=http_status)
    resp.headers["X-Request-ID"] = request_id
    return resp
