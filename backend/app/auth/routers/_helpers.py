"""
Hilo People — Auth router shared helpers.

Slice:  P01-S02-T002 (debugger cycle 1 — extracted per validator F1).
        P01-S02-T003 — added _set_refresh_cookie helper so sign-in, refresh
                       and future 2FA-verify (T006) share byte-identical cookie attrs.
        P01-S02-T011 — fixed cookie Path from /auth to /api/v1/auth (RFC 6265 §5.4).
                       Extracted _REFRESH_COOKIE_PATH constant (DRY); same constant
                       used in both _set_refresh_cookie and _clear_refresh_cookie.
Phase:  P01 Auth + Data Foundation
Purpose: Helpers reused by every endpoint in `app/auth/routers/*`:
           - _get_request_id: extract X-Request-ID or generate UUID v4.
           - _get_client_ip: respect X-Forwarded-For (proxy-aware).
           - _error_response: build the {data:null, meta, errors:[…]} envelope.
           - _set_refresh_cookie: set HttpOnly refresh cookie on a JSONResponse
             with byte-identical attrs across sign-in, refresh, 2FA-verify.
             Path=/api/v1/auth (matches real routing prefix per RFC 6265 §5.4).
           - _clear_refresh_cookie: clear cookie on logout (Max-Age=0, same Path).

These were on `router.py` before. Centralising them keeps each endpoint
file ≤300 LOC and ensures sign-up + sign-in + refresh emit byte-identical
envelopes and cookies.

Source refs:
  - TECHNICAL_GUIDE §6.2 envelope contract; §10.2 cookie Path contract (T011);
    §10.5 X-Request-ID propagation.
  - task pack P01-S02-T002 §E (envelope shape).
  - task pack P01-S02-T003 §D-RP2 (cookie attrs byte-identical to T002).
  - task pack P01-S02-T011 §front→back→DB contract (Path fix).
  - 01-non-negotiables.md §Security/Request correlation.
"""

from __future__ import annotations

import os
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.schemas import ErrorItem, ErrorResponse, ResponseMeta


# Cookie Path attribute — must match the real routing prefix so RFC 6265 §5.4
# path-matching causes the browser to send the cookie only to /api/v1/auth/* endpoints.
# Using /auth (the sub-prefix only) would prevent the browser from sending the cookie
# to /api/v1/auth/refresh and /api/v1/auth/logout (the actual URLs).
# See: TECHNICAL_GUIDE §10.2; task pack P01-S02-T011 §R2.
_REFRESH_COOKIE_PATH: str = "/api/v1/auth"


def _get_request_id(request: Request) -> str:
    """Extract X-Request-ID from headers, or generate a UUID v4 if missing."""
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def _get_client_ip(request: Request) -> str:
    """Return client IP — first hop of X-Forwarded-For, else `request.client.host`."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.client.host if request.client else "") or ""


def _error_response(
    request_id: str,
    code: str,
    message: str,
    http_status: int,
    field: str | None = None,
    headers: dict | None = None,
) -> JSONResponse:
    """Build the standard {data:null, meta, errors:[{code,message,field}]} envelope."""
    envelope = ErrorResponse(
        meta=ResponseMeta(request_id=request_id),
        errors=[ErrorItem(code=code, message=message, field=field)],
    )
    return JSONResponse(
        content=envelope.model_dump(),
        status_code=http_status,
        headers=headers or {},
    )


def _set_refresh_cookie(json_resp: JSONResponse, opaque_refresh: str) -> None:
    """Set the HttpOnly refresh token cookie on a JSONResponse (in-place).

    Cookie attributes are byte-identical across sign-in, refresh, and future
    2FA-verify (D-RP2). The TTL is read from AUTH_REFRESH_TTL_SECONDS env var
    (default 2592000 = 30 days).

    Args:
        json_resp: The JSONResponse to add the Set-Cookie header to (mutated).
        opaque_refresh: Raw opaque refresh token value (URL-safe base64 string).
                        NEVER log this value.

    Ref: TECHNICAL_GUIDE §10.2, task pack P01-S02-T003 §D-RP2.
    """
    refresh_ttl = int(os.getenv("AUTH_REFRESH_TTL_SECONDS", "2592000"))
    json_resp.set_cookie(
        key="refresh_token",
        value=opaque_refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=refresh_ttl,
    )


def _clear_refresh_cookie(response) -> None:
    """Clear the HttpOnly refresh token cookie on a Response (in-place).

    Uses byte-identical cookie attributes to _set_refresh_cookie with Max-Age=0
    so the browser actually removes the cookie (attributes must match for the
    browser to honor the deletion).

    Called on BOTH 204 success and every 401 failure path for POST /auth/logout
    (D1 — stale/invalid cookie must not linger in browser).

    Args:
        response: Any Starlette Response (JSONResponse or plain Response).
                  Mutated in-place.

    Ref: TECHNICAL_GUIDE §10.2, task pack P01-S02-T004 §D1, §D-LO1.
    """
    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        secure=True,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=0,
    )
