"""
Hilo People — Admin audit HTTP router.

Slice:  P04-S03-T003 — GET /api/v1/admin/audit endpoint
Phase:  P04 Complete Features
Purpose: FastAPI APIRouter exposing GET /audit (mounted under /api/v1/admin
         by main.py → resolves as GET /api/v1/admin/audit). RBAC via
         Depends(require_auditor): accepts `people_auditor` or `super_admin`.

Key deps:
  - app.admin.audit.service.AuditService
  - app.admin.audit.schemas.get_list_audit_query, ListAuditQuery
  - app.security.permissions.require_auditor
  - app.auth.routers._helpers (_error_response, _get_request_id)
  - app.db.session.get_db_session

Source refs:
  - task pack P04-S03-T003 §Front→Back→DB contract
  - TECHNICAL_GUIDE §6.2 (GET /api/v1/admin/audit), §6.4 (envelope),
    §10.2 (Auth guards — require_auditor)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR), §Security (RBAC),
    §API contract (envelope)

Decisions:
  - D-ROUTER-RBAC: Depends(require_auditor). Returns 401 (no JWT) or
    403 (JWT but not auditor/super_admin). Pattern mirrors usage.py and
    providers/router.py.
  - D-ROUTER-READONLY: No audit row written for this GET (D-AUDIT-READONLY).
  - D-ROUTER-NO-RATE-LIMIT: read-only admin GET, same precedent as
    usage.py and admin/providers/router.py::list_providers.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.admin.audit.schemas import ListAuditQuery, get_list_audit_query
from app.admin.audit.service import AuditService
from app.auth.routers._helpers import _error_response, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.security.permissions import require_auditor

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

audit_router = APIRouter(tags=["admin-audit"])

_service = AuditService()


@audit_router.get("/audit", status_code=200)
async def get_audit(
    request: Request,
    query: ListAuditQuery = Depends(get_list_audit_query),
    user_or_response: User | JSONResponse = Depends(require_auditor),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """GET /api/v1/admin/audit — list audit events (auditor/super_admin only).

    Returns paginated audit_logs rows filtered by the provided query params.
    Auth: requires `people_auditor` or `super_admin` role (D-ROUTER-RBAC).
    No audit row is written for this read-only GET (D-AUDIT-READONLY).

    Args:
        request:          FastAPI Request (for X-Request-ID).
        query:            Validated query parameters (from_dt, to_dt, actor,
                          action, cursor, limit).
        user_or_response: Authenticated User or 401/403 JSONResponse.
        session:          SQLAlchemy DB session.

    Returns:
        JSONResponse 200  — {data: [AuditLogOut], meta: {request_id, ...}}
        JSONResponse 401  — AUTH_SESSION_EXPIRED (missing/expired JWT)
        JSONResponse 403  — AUTH_PERMISSION_DENIED (insufficient role)
        JSONResponse 422  — validation error (bad dates, window too wide)
        JSONResponse 500  — INTERNAL_ERROR (unexpected DB failure)
    """
    # Propagate 401/403 from require_auditor dependency.
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "admin.audit.router.get_audit.start "
            "user_id_hash=%s request_id=%s",
            _short_hash(str(user.id)),
            request_id,
        )  # BEFORE

    result = _service.list_events(
        session=session,
        query=query,
        actor_user_id=user.id,
        request_id=request_id,
    )

    if "error" in result:
        err = result["error"]
        if _VERBOSE:
            logger.debug(
                "admin.audit.router.get_audit.validation_error "
                "code=%s request_id=%s",
                err["code"],
                request_id,
            )  # AFTER (error path)
        return _error_response(
            request_id=request_id,
            code=err["code"],
            message=err["message"],
            http_status=err["http_status"],
        )

    if _VERBOSE:
        logger.debug(
            "admin.audit.router.get_audit.ok "
            "user_id_hash=%s count=%d request_id=%s",
            _short_hash(str(user.id)),
            result["meta"]["count"],
            request_id,
        )  # AFTER (success path)
    else:
        logger.info(
            "admin.audit.router.get_audit.ok count=%d",
            result["meta"]["count"],
        )

    return JSONResponse(
        content={
            "data": result["data"],
            "meta": result["meta"],
            "errors": [],
        },
        status_code=200,
    )


def _short_hash(value: str) -> str:
    """Return 8-char SHA-256 prefix for safe opaque logging (no PII).

    Args:
        value: String to hash.

    Returns:
        First 8 hex characters of SHA-256 digest.
    """
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()[:8]


__all__ = ["audit_router"]
