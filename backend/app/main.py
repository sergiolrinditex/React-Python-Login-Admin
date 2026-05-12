"""
Hilo People — FastAPI application entry point.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up (WRITE_SET_DRIFT: main.py)
Phase:  P01 Auth + Data Foundation
Purpose: Creates the FastAPI application instance and mounts routers:
         - api_router: /health, /live, /ready probes (root-level).
         - auth_router: /api/v1/auth/* — sign-up and future auth endpoints.

WRITE_SET_DRIFT from P01-S02-T001 (auth router) and P01-S02-T005
(forgot/reset Pydantic-422 → 400 envelope normalization — cycle 2 debugger):
  - T001 added auth_router mounting (2 lines).
  - T005 cycle-2: path-scoped RequestValidationError handler for forgot-password
    and reset-password endpoints. Pinned by task pack §H-forgot-2 / §H-reset-5
    ("NO 422" alignment). Scope is path-filtered so T001 sign-up / T002 sign-in
    422 tests (test_signup_missing_full_name_422, test_signin_missing_field_returns_422)
    keep their default FastAPI 422 response.

Key deps:
  - fastapi: ASGI web framework (uvicorn transport, port 8000 per STACK_PROFILE).
  - logging: stdlib; level driven by ENABLE_VERBOSE_LOGGING env var.
  - app.api.router: api_router with /health, /live, /ready.
  - app.auth: auth_router with /api/v1/auth/sign-up.

Source refs:
  - TECHNICAL_GUIDE §6.2 health endpoints contract.
  - STACK_PROFILE.yaml backend.dev_cmd (uvicorn port 8000).
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR pattern, no PII/secrets).
"""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.auth import auth_router
from app.auth.schemas import ErrorItem, ErrorResponse, ResponseMeta

# ---------------------------------------------------------------------------
# Logging configuration
# ENABLE_VERBOSE_LOGGING drives level only; code never conditionally wraps
# log calls. Per 01-non-negotiables.md §Logging.
# ---------------------------------------------------------------------------
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
_LOG_LEVEL: int = logging.DEBUG if _VERBOSE else logging.WARNING
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Hilo People API",
    version="0.1.0",
    description="Internal HR platform — Hilo People",
)

# ---------------------------------------------------------------------------
# Mount routers
# api_router: /health, /live, /ready (root-level — no prefix)
# auth_router: /api/v1/auth/* (feature routes)
# ---------------------------------------------------------------------------
app.include_router(api_router)
app.include_router(auth_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Path-scoped Pydantic RequestValidationError handler — P01-S02-T005 cycle 2.
#
# The forgot-password and reset-password endpoints (task pack §H-forgot-2,
# §H-reset-5) MUST return HTTP 400 with the project envelope
#   {data:null, meta:{request_id}, errors:[{code:"AUTH_INVALID_PAYLOAD",
#    field:<loc>, message:<msg>, details:null}]}
# on payload validation errors, NOT the FastAPI default
#   {detail:[{loc,type,msg,...}]} HTTP 422.
#
# The handler is registered globally but filters by request.url.path so that
# sign-up / sign-in / refresh / logout retain their default FastAPI 422 response
# (test_signup_missing_full_name_422, test_signin_missing_field_returns_422, etc.).
#
# Ref: 01-non-negotiables.md §API contract (envelope), task pack §H-forgot-2 + §H-reset-5.
# ---------------------------------------------------------------------------
_AUTH_INVALID_PAYLOAD_PATHS: frozenset[str] = frozenset({
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
})


def _resolve_request_id(request: Request) -> str:
    """Reuse the request id from the inbound header or generate a deterministic placeholder.

    Mirrors `_get_request_id` semantics in `app.auth.routers._helpers` but does
    not depend on uuid here (handler runs before any router code); we just echo
    the header when present and fall back to an empty string so the response
    envelope still ships the field unchanged.
    """
    return request.headers.get("X-Request-ID", "") or ""


@app.exception_handler(RequestValidationError)
async def _forgot_reset_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Normalize Pydantic 422 to 400 AUTH_INVALID_PAYLOAD for forgot/reset endpoints only.

    For every other route (sign-up, sign-in, refresh, logout, health, etc.) we
    delegate to FastAPI's default 422 RequestValidationError envelope.
    """
    path = request.url.path
    if path not in _AUTH_INVALID_PAYLOAD_PATHS:
        # Re-emit FastAPI's default 422 envelope: this matches the framework's
        # documented default behaviour for unchanged consumers (T001 / T002 tests).
        logger.debug(
            "main.validation_error.passthrough path=%s", path
        )  # BEFORE
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    request_id = _resolve_request_id(request)
    error_items: list[ErrorItem] = []
    for raw in exc.errors():
        loc = raw.get("loc", ())
        field_name: str | None = None
        # Skip the leading "body" sentinel produced by FastAPI body validation
        # so the field reported in the envelope is the actual schema attribute
        # (e.g. "email", "token", "password").
        if isinstance(loc, (list, tuple)) and loc:
            tail = [str(part) for part in loc if part != "body"]
            field_name = tail[-1] if tail else None
        error_items.append(
            ErrorItem(
                code="AUTH_INVALID_PAYLOAD",
                message=str(raw.get("msg", "Invalid payload")),
                field=field_name,
                details=None,
            )
        )

    envelope = ErrorResponse(
        meta=ResponseMeta(request_id=request_id),
        errors=error_items,
    )

    logger.warning(
        "main.validation_error.normalized path=%s field_count=%d request_id=%s",
        path,
        len(error_items),
        request_id,
    )  # AFTER

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=envelope.model_dump(),
    )
