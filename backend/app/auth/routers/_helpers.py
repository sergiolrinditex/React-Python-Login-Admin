"""
Hilo People — Auth router shared helpers.

Slice:  P01-S02-T002 (debugger cycle 1 — extracted per validator F1).
Phase:  P01 Auth + Data Foundation
Purpose: Helpers reused by every endpoint in `app/auth/routers/*`:
           - _get_request_id: extract X-Request-ID or generate UUID v4.
           - _get_client_ip: respect X-Forwarded-For (proxy-aware).
           - _error_response: build the {data:null, meta, errors:[…]} envelope.

These were on `router.py` before. Centralising them keeps each endpoint
file ≤300 LOC and ensures sign-up + sign-in emit byte-identical envelopes.

Source refs:
  - TECHNICAL_GUIDE §6.2 envelope contract; §10.5 X-Request-ID propagation.
  - task pack P01-S02-T002 §E (envelope shape).
  - 01-non-negotiables.md §Security/Request correlation.
"""

from __future__ import annotations

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
