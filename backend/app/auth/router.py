"""
Hilo People — Auth APIRouter for POST /api/v1/auth/sign-up.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: FastAPI router for the sign-up endpoint. Handles request parsing,
         rate limiting, request-ID propagation, service dispatch, and error
         mapping to the standard {data, meta, errors} envelope.

Key deps:
  - fastapi: APIRouter, Request, Response, HTTPException
  - app.auth.service.SignUpUser — use case
  - app.auth.schemas — SignUpRequest, SignUpResponse, ErrorResponse
  - app.auth.errors — typed domain error → HTTP code mapping
  - app.auth.rate_limit.check_rate_limit — per-IP token bucket
  - app.db.session.get_db_session — SQLAlchemy Session dependency

Source refs:
  - TECHNICAL_GUIDE §6.2 endpoint contract
  - task pack §C.3 error code mapping
  - task pack §C.7 logging contract (email_domain only at INFO, no PII)
  - 01-non-negotiables.md §Security (X-Request-ID middleware, rate limit)
  - 01-non-negotiables.md §API contract (/api/v1/... prefix, {data,meta,errors})

Decisions:
  - D-RP1: Request ID sourced from X-Request-ID header; if absent, generated
    as a UUID v4 locally and returned in the response header. Full platform
    middleware (X-Request-ID injection for all routes) is a P02 concern.
  - D-RP2: Client IP sourced from X-Forwarded-For first value (proxy-aware),
    falling back to request.client.host. Single-instance V1 deployment.
  - D-RP3: DB session created per-request using a generator dependency backed
    by the same sync engine as the health router.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Generator

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth.errors import (
    EmailAlreadyExistsError,
    LegalNotAcceptedError,
    NonCorporateEmailError,
    PasswordPolicyError,
    RateLimitExceededError,
)
from app.auth.rate_limit import check_rate_limit
from app.auth.schemas import (
    ErrorItem,
    ErrorResponse,
    ResponseMeta,
    SignUpData,
    SignUpRequest,
    SignUpResponse,
)
from app.auth.service import SignUpUser

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
_LOG_LEVEL: int = logging.DEBUG if _VERBOSE else logging.WARNING
logger.setLevel(_LOG_LEVEL)

# ---------------------------------------------------------------------------
# DB session dependency — sync engine reused from health probe pattern
# ---------------------------------------------------------------------------
_DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev")
if _DB_URL.startswith("postgresql://") and not _DB_URL.startswith("postgresql+"):
    _DB_URL = _DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)

_engine = create_engine(_DB_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI generator dependency: yield a DB session, close on exit.

    Yields:
        A SQLAlchemy Session for the duration of one request.
    """
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_request_id(request: Request) -> str:
    """Extract or generate the X-Request-ID for this request.

    If the client provides X-Request-ID, use it (assumed UUID v4 from client
    or upstream proxy). Otherwise generate a new UUID v4.

    Args:
        request: FastAPI Request object.

    Returns:
        String request ID for logging and response header.
    """
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def _get_client_ip(request: Request) -> str:
    """Extract client IP address, respecting X-Forwarded-For proxy header.

    Returns the first IP in X-Forwarded-For (closest to the client).
    Falls back to request.client.host if no forwarding header present.

    Args:
        request: FastAPI Request object.

    Returns:
        IP address string (may be empty string in tests/CLI environments).
    """
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
    """Build a standard error envelope JSONResponse.

    Args:
        request_id: X-Request-ID for meta.
        code: Machine-readable error code.
        message: English debug message (NOT user-facing; frontend localises).
        http_status: HTTP status code.
        field: Optional request field name that caused the error.
        headers: Optional additional response headers (e.g. Retry-After).

    Returns:
        JSONResponse with the standard {data, meta, errors} envelope.
    """
    envelope = ErrorResponse(
        meta=ResponseMeta(request_id=request_id),
        errors=[ErrorItem(code=code, message=message, field=field)],
    )
    return JSONResponse(
        content=envelope.model_dump(),
        status_code=http_status,
        headers=headers or {},
    )


# ---------------------------------------------------------------------------
# Auth router
# ---------------------------------------------------------------------------
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post(
    "/sign-up",
    status_code=status.HTTP_201_CREATED,
    response_model=SignUpResponse,
    summary="Register a new employee account",
    description=(
        "Creates a new user account for a corporate employee. "
        "Validates corporate email domain, password policy and legal acceptance. "
        "No JWT is issued — the client must sign in after registration."
    ),
)
def sign_up(
    body: SignUpRequest,
    request: Request,
    response: Response,
) -> JSONResponse:
    """POST /api/v1/auth/sign-up — register a new employee account.

    Args:
        body: Validated SignUpRequest (email, password, full_name, legal_acceptance).
        request: FastAPI Request (for IP, User-Agent, X-Request-ID).
        response: FastAPI Response (unused; JSONResponse returned directly).

    Returns:
        201 JSONResponse with {data: {user_id, mfa_required: false}, meta, errors: []}.

    Raises (via JSONResponse error envelope):
        400: Non-corporate email, legal not accepted.
        409: Duplicate email (generic message — no user enumeration).
        422: Invalid payload (Pydantic validation failure).
        429: Rate limit exceeded (Retry-After header included).
        500: Unexpected server error.
    """
    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    email_domain = body.email.split("@")[-1] if "@" in body.email else "unknown"

    logger.info(
        "auth.sign_up.received email_domain=%s request_id=%s",
        email_domain,
        request_id,
    )  # BEFORE

    # ----------------------------------------------------------------
    # Rate limiting (D-RP2: per-IP check BEFORE any DB work)
    # ----------------------------------------------------------------
    try:
        check_rate_limit(client_ip)
    except RateLimitExceededError as exc:
        logger.warning(
            "auth.sign_up.rejected reason=RATE_LIMITED ip=%s request_id=%s",
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

    # ----------------------------------------------------------------
    # Sign-up use case — create a fresh session per request
    # ----------------------------------------------------------------
    from sqlalchemy.orm import Session as _Session  # local import to avoid circular

    session: _Session = _SessionLocal()
    try:
        use_case = SignUpUser(session=session)
        result = use_case.execute(
            email=body.email,
            password_plain=body.password,
            full_name=body.full_name,
            legal_acceptance=body.legal_acceptance,
            request_id=request_id,
            ip=client_ip,
            user_agent=user_agent,
        )
    except LegalNotAcceptedError as exc:
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            field="legal_acceptance",
        )
    except NonCorporateEmailError as exc:
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            field="email",
        )
    except PasswordPolicyError as exc:
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            field="password",
        )
    except EmailAlreadyExistsError as exc:
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
        )
    except Exception:
        logger.error(
            "auth.sign_up.error request_id=%s",
            request_id,
            exc_info=True,
        )
        return _error_response(
            request_id=request_id,
            code="AUTH_SIGNUP_INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        session.close()

    envelope = SignUpResponse(
        data=SignUpData(user_id=result.user_id, mfa_required=result.mfa_required),
        meta=ResponseMeta(request_id=request_id),
    )
    logger.info(
        "auth.sign_up.response_sent user_id=%s request_id=%s",
        str(result.user_id),
        request_id,
    )  # AFTER
    return JSONResponse(
        content=envelope.model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
        headers={"X-Request-ID": request_id},
    )
