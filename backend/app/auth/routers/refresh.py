"""
Hilo People — POST /api/v1/auth/refresh router.

Slice:  P01-S02-T003 — POST /api/v1/auth/refresh
Phase:  P01 Auth + Data Foundation
Responsibility: Parse refresh cookie, rate-limit, dispatch to RefreshTokenUser,
                map domain errors to the envelope, set the new HttpOnly cookie,
                return 200 {data:{access_token,...}, meta, errors:[]}.

Decisions:
  - Cookie absent → 401 (same envelope as all other 401s — aggregate anti-enum).
  - No request body (no Pydantic schema needed).
  - Cookie set via shared _set_refresh_cookie (D-RP2 — byte-identical to sign-in).
  - Rate limit: REFRESH namespace, 30 req/min default (AUTH_REFRESH_RATE_PER_MINUTE).
  - All failure reasons return the same 401 AUTH_SESSION_EXPIRED body to prevent
    token-state enumeration. Reason is in audit_log only.

Source refs:
  - TECHNICAL_GUIDE §6.2 POST /api/v1/auth/refresh; §10.2 JWT claims.
  - task pack P01-S02-T003 §D.2, §D-RP1..D-RP7, §F.1..F.14.
  - 01-non-negotiables.md §API contract, §Security/Token storage (web).
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.errors import RefreshRateLimitedError, SessionExpiredError
from app.auth.rate_limit import check_rate_limit_refresh
from app.auth.routers._helpers import (
    _error_response,
    _get_client_ip,
    _get_request_id,
    _set_refresh_cookie,
)
from app.auth.services import RefreshTokenUser
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)

_ACCESS_TTL: int = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "1800"))

refresh_router = APIRouter(tags=["auth"])


@refresh_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Rotate a refresh token and issue a new access JWT",
    description=(
        "Accepts the HttpOnly refresh cookie; validates it against the DB; "
        "atomically revokes the old token and issues a new opaque refresh cookie "
        "(rotation). Returns a new short-lived JWT access token in the body. "
        "All 401 responses are byte-identical to prevent token-state enumeration. "
        "Requires no request body."
    ),
)
def refresh(
    request: Request,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/auth/refresh — rotate refresh token, issue new access JWT."""
    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    logger.debug(
        "auth.refresh.received request_id=%s ip=%s",
        request_id,
        client_ip,
    )  # BEFORE

    try:
        check_rate_limit_refresh(client_ip)
    except RefreshRateLimitedError as exc:
        logger.warning(
            "auth.refresh.rejected reason=RATE_LIMITED ip=%s request_id=%s",
            client_ip,
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            headers={"Retry-After": str(exc.retry_after)},
        )

    raw_cookie: str | None = request.cookies.get("refresh_token")

    try:
        result = RefreshTokenUser(session=session).execute(
            raw_cookie=raw_cookie,
            request_id=request_id,
            ip=client_ip,
            user_agent=user_agent,
        )
    except SessionExpiredError as exc:
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
        )
    except Exception:
        logger.error(
            "auth.refresh.error request_id=%s",
            request_id,
            exc_info=True,
        )
        return _error_response(
            request_id=request_id,
            code="AUTH_REFRESH_INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Success — set new refresh cookie + return new access token in body
    response_body = {
        "data": {
            "access_token": result.access_token,
            "token_type": "Bearer",
            "expires_in": result.expires_in,
        },
        "meta": {"request_id": request_id},
        "errors": [],
    }
    logger.debug(
        "auth.refresh.success user_id=%s old_token_id=%s new_token_id=%s request_id=%s",
        str(result.user_id),
        str(result.old_token_id),
        str(result.new_token_id),
        request_id,
    )  # AFTER — IDs (UUIDs) only, never raw tokens or JWT values

    json_resp = JSONResponse(
        content=response_body,
        status_code=status.HTTP_200_OK,
        headers={"X-Request-ID": request_id},
    )
    # D-RP2: byte-identical cookie attrs via shared helper.
    # NEVER log the new refresh token value — only the token_id above.
    _set_refresh_cookie(json_resp, result.new_refresh_token)
    return json_resp
