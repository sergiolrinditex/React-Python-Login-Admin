"""
Hilo People — Auth router shared helpers.

Slice:  P01-S02-T002 (debugger cycle 1 — extracted per validator F1).
        P01-S02-T003 — added _set_refresh_cookie helper so sign-in, refresh
                       and future 2FA-verify (T006) share byte-identical cookie attrs.
Phase:  P01 Auth + Data Foundation
Purpose: Helpers reused by every endpoint in `app/auth/routers/*`:
           - _get_request_id: extract X-Request-ID or generate UUID v4.
           - _get_client_ip: respect X-Forwarded-For (proxy-aware).
           - _error_response: build the {data:null, meta, errors:[…]} envelope.
           - _set_refresh_cookie: set HttpOnly refresh cookie on a JSONResponse
             with byte-identical attrs across sign-in, refresh, 2FA-verify.

These were on `router.py` before. Centralising them keeps each endpoint
file ≤300 LOC and ensures sign-up + sign-in + refresh emit byte-identical
envelopes and cookies.

Source refs:
  - TECHNICAL_GUIDE §6.2 envelope contract; §10.5 X-Request-ID propagation.
  - task pack P01-S02-T002 §E (envelope shape).
  - task pack P01-S02-T003 §D-RP2 (cookie attrs byte-identical to T002).
  - 01-non-negotiables.md §Security/Request correlation.
"""

from __future__ import annotations

import os
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.schemas import ErrorItem, ErrorResponse, ResponseMeta


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
        path="/auth",
        max_age=refresh_ttl,
    )
