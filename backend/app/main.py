"""
Hilo People — FastAPI application entry point.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up (WRITE_SET_DRIFT: main.py)
Phase:  P01 Auth + Data Foundation
Purpose: Creates the FastAPI application instance and mounts routers:
         - api_router: /health, /live, /ready probes (root-level).
         - auth_router: /api/v1/auth/* — sign-up and future auth endpoints.
         - users_router: /api/v1/users/* — P01-S02-T007 user profile endpoints.

WRITE_SET_DRIFT from P01-S02-T001 (auth router), P01-S02-T005
(forgot/reset Pydantic-422 → 400 envelope normalization), and P01-S02-T007
(users router + /api/v1/users/me/language added to _AUTH_INVALID_PAYLOAD_PATHS):
  - T001 added auth_router mounting (2 lines).
  - T005 cycle-2: path-scoped RequestValidationError handler for forgot-password
    and reset-password endpoints. Pinned by task pack §H-forgot-2 / §H-reset-5
    ("NO 422" alignment). Scope is path-filtered so T001 sign-up / T002 sign-in
    422 tests (test_signup_missing_full_name_422, test_signin_missing_field_returns_422)
    keep their default FastAPI 422 response.
  - T007: mounted users_router under /api/v1; added /api/v1/users/me/language to
    the 422→400 path set (G.7 — PATCH body validation returns 400 AUTH_INVALID_PAYLOAD
    with field='language' per task pack §F.2).

Key deps:
  - fastapi: ASGI web framework (uvicorn transport, port 8000 per STACK_PROFILE).
  - logging: stdlib; level driven by ENABLE_VERBOSE_LOGGING env var.
  - app.api.router: api_router with /health, /live, /ready.
  - app.auth: auth_router with /api/v1/auth/sign-up and other auth endpoints.
  - app.users: users_router with /api/v1/users/me and /api/v1/users/me/language.

Source refs:
  - TECHNICAL_GUIDE §6.2 health endpoints contract.
  - STACK_PROFILE.yaml backend.dev_cmd (uvicorn port 8000).
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR pattern, no PII/secrets).
  - task pack P01-S02-T007 §G.7 (PATCH /me/language 422→400 mapping).
  - task pack P01-S02-T007 §G.14 (router mounting, WRITE_SET_DRIFT).
"""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.admin import admin_router  # P02-S05-T001 WRITE_SET_DRIFT §D-AAM
from app.agents import agents_runs_router  # P02-S08-T001 WRITE_SET_DRIFT §D-AGWIRE-MAIN
from app.api.router import api_router
from app.auth import auth_router
from app.auth.schemas import ErrorItem, ErrorResponse, ResponseMeta
from app.chat.routers import router as chat_router  # P02-S03-T001 WRITE_SET_DRIFT
from app.rag.documents import rag_documents_router  # P02-S06-T001 WRITE_SET_DRIFT §D-RAGDOCS-MAIN
from app.users import users_router  # P01-S02-T007 WRITE_SET_DRIFT §G.14

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
# users_router: /api/v1/users/* (feature routes — P01-S02-T007)
# ---------------------------------------------------------------------------
app.include_router(api_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")  # P01-S02-T007 WRITE_SET_DRIFT §G.14
app.include_router(chat_router, prefix="/api/v1")  # P02-S03-T001 WRITE_SET_DRIFT
app.include_router(admin_router, prefix="/api/v1/admin/ai", tags=["admin-ai"])  # P02-S05-T001 WRITE_SET_DRIFT §D-AAM
app.include_router(agents_runs_router, prefix="/api/v1", tags=["agents"])  # P02-S08-T001 WRITE_SET_DRIFT §D-AGWIRE-MAIN
app.include_router(rag_documents_router, prefix="/api/v1/admin/rag", tags=["admin-rag"])  # P02-S06-T001 WRITE_SET_DRIFT §D-RAGDOCS-MAIN


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
# P01-S02-T007: /api/v1/users/me/language added per G.7 — PATCH body
# validation errors (invalid language, extra fields, null, empty) must
# return 400 AUTH_INVALID_PAYLOAD with field='language' so AccountPage
# form validation can highlight the field (errors[0].field == "language").
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
    "/api/v1/auth/2fa/verify",          # P01-S02-T006: 422 → 400 AUTH_INVALID_PAYLOAD
    "/api/v1/users/me/language",        # P01-S02-T007: PATCH body 422 → 400 (G.7)
})

# P02-S03-T001 debugger cycle 1 (F-1): chat endpoints normalize Pydantic 422 to
# 400 with the feature-scoped code CHAT_INVALID_PAYLOAD per task pack §J.3.
# Set-membership only (no startswith/regex) — keeps dispatch deterministic and
# avoids accidental contract drift across feature modules.
_CHAT_INVALID_PAYLOAD_PATHS: frozenset[str] = frozenset({
    "/api/v1/chat/conversations",
})

# Union used by the path filter inside the global handler so the body stays
# unique (DRY/KISS — single handler, single body, per-path error code).
_INVALID_PAYLOAD_PATHS: frozenset[str] = (
    _AUTH_INVALID_PAYLOAD_PATHS | _CHAT_INVALID_PAYLOAD_PATHS
)


def _invalid_payload_code_for_path(path: str) -> str:
    """Return the feature-scoped error code for the given path.

    Set-membership only: chat paths → ``CHAT_INVALID_PAYLOAD``; everything else
    in ``_INVALID_PAYLOAD_PATHS`` keeps emitting ``AUTH_INVALID_PAYLOAD`` so the
    existing auth/users contracts (and their tests) remain byte-for-byte stable.
    """
    if path in _CHAT_INVALID_PAYLOAD_PATHS:
        return "CHAT_INVALID_PAYLOAD"
    return "AUTH_INVALID_PAYLOAD"


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
    """Normalize Pydantic 422 to 400 AUTH_INVALID_PAYLOAD for specific endpoints only.

    For every other route (sign-up, sign-in, refresh, logout, health, etc.) we
    delegate to FastAPI's default 422 RequestValidationError envelope.
    """
    path = request.url.path
    if path not in _INVALID_PAYLOAD_PATHS:
        # Re-emit FastAPI's default 422 envelope: this matches the framework's
        # documented default behaviour for unchanged consumers (T001 / T002 tests).
        logger.debug(
            "main.validation_error.passthrough path=%s", path
        )  # BEFORE
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    # P02-S03-T001 F-1: derive the feature-scoped error code ONCE per request
    # so every ErrorItem in the envelope carries the same code (no per-error
    # branching, no string interpolation surprises).
    error_code = _invalid_payload_code_for_path(path)
    request_id = _resolve_request_id(request)
    error_items: list[ErrorItem] = []
    for raw in exc.errors():
        loc = raw.get("loc", ())
        field_name: str | None = None
        # Skip the leading "body" sentinel produced by FastAPI body validation
        # so the field reported in the envelope is the actual schema attribute
        # (e.g. "email", "token", "password", "language").
        if isinstance(loc, (list, tuple)) and loc:
            tail = [str(part) for part in loc if part != "body"]
            field_name = tail[-1] if tail else None
        error_items.append(
            ErrorItem(
                code=error_code,
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
