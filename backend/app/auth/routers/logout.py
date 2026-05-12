"""
Hilo People — POST /api/v1/auth/logout router.

Slice:  P01-S02-T004 — POST /api/v1/auth/logout
Phase:  P01 Auth + Data Foundation
Responsibility: Extract Bearer from Authorization header, read refresh cookie,
                dispatch to LogoutUser use case, map domain errors to envelope,
                clear the HttpOnly cookie via _clear_refresh_cookie, return 204
                No Content on success or 401 on any failure.

Decisions:
  - D1: 401 on every failure path, including already-revoked cookie (idempotency
    is at HTTP level; the frontend treats both 204 and 401 as "logged out").
  - D2: BOTH Bearer AND refresh cookie required (D2 in task pack).
  - Cookie cleared on BOTH 204 and every 401 (defensive — stale/invalid cookie
    must not linger in browser).
  - No request body (pure REST; no Pydantic schema).
  - No rate-limit bucket for logout in V1 (rationale in task pack §Rate limiting
    decision).

Source refs:
  - TECHNICAL_GUIDE §6.2 POST /api/v1/auth/logout; §10.2 cookie attrs.
  - task pack P01-S02-T004 §D1, §D2, §D3, §Endpoint specification.
  - 01-non-negotiables.md §API contract, §Security/Token storage (web).
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.errors import SessionExpiredError
from app.auth.routers._helpers import (
    _clear_refresh_cookie,
    _error_response,
    _get_client_ip,
    _get_request_id,
)
from app.auth.services.logout import LogoutUser
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)

logout_router = APIRouter(tags=["auth"])


@logout_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke current session and clear the refresh cookie",
    description=(
        "Requires both a valid Bearer access token (Authorization header) and "
        "the HttpOnly refresh cookie. Revokes the matching refresh_tokens row "
        "and clears the cookie. Returns 204 No Content on success. "
        "All 401 responses are byte-identical (aggregate anti-enumeration). "
        "Cookie is cleared on BOTH 204 and 401 paths."
    ),
)
def logout(
    request: Request,
    session: Session = Depends(get_db_session),
) -> Response:
    """POST /api/v1/auth/logout — revoke refresh token, clear cookie, return 204."""
    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    logger.debug(
        "auth.logout.received request_id=%s ip=%s",
        request_id,
        client_ip,
    )  # BEFORE

    # Extract Bearer token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    access_bearer: str | None = None
    if auth_header.startswith("Bearer "):
        access_bearer = auth_header[7:].strip() or None

    raw_cookie: str | None = request.cookies.get("refresh_token")

    try:
        LogoutUser(session=session).execute(
            access_bearer=access_bearer,
            raw_cookie=raw_cookie,
            request_id=request_id,
            ip=client_ip,
            user_agent=user_agent,
        )
    except SessionExpiredError as exc:
        logger.warning(
            "auth.logout.rejected reason=session_invalid request_id=%s",
            request_id,
        )
        err_resp = _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            headers={"X-Request-ID": request_id},
        )
        # D1: clear cookie on 401 too — stale/invalid cookie must not linger
        _clear_refresh_cookie(err_resp)
        return err_resp
    except Exception:
        logger.error(
            "auth.logout.error request_id=%s",
            request_id,
            exc_info=True,
        )
        err_resp = _error_response(
            request_id=request_id,
            code="AUTH_LOGOUT_INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"X-Request-ID": request_id},
        )
        _clear_refresh_cookie(err_resp)
        return err_resp

    logger.debug(
        "auth.logout.success request_id=%s",
        request_id,
    )  # AFTER

    # 204 No Content — no body, clear cookie, echo X-Request-ID
    resp = Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"X-Request-ID": request_id},
    )
    _clear_refresh_cookie(resp)
    return resp
