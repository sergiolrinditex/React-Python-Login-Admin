"""
Hilo People — POST /api/v1/auth/forgot-password and /reset-password routers.

Slice:  P01-S02-T005 — forgot + reset password endpoints
Phase:  P01 Auth + Data Foundation
Responsibility: Parse schemas, apply rate limits, dispatch to use cases,
                map domain errors to the envelope with correct HTTP codes.

Anti-enumeration (forgot):
  - HTTP 200 always (even if email not found, rate-limited silently, etc.)
  - EXCEPT payload validation (400) which pre-processes before business logic.
    A malformed email address cannot produce a reset token regardless — 400 is
    safe here (TECHNICAL_GUIDE §6.2 says 400 is the stated error for forgot).

HTTP codes (reset):
  - 200 on success.
  - 400 on invalid payload (bad token format, password policy fail).
  - 410 on expired or invalid/used token (AUTH_RESET_TOKEN_EXPIRED /
    AUTH_RESET_TOKEN_INVALID — same body from client perspective).
  - 429 on rate limit exceeded.

Source refs:
  - TECHNICAL_GUIDE §6.2 fila 259-260 (forgot/reset endpoint contract)
  - task pack §H (acceptance), §I-9 (router)
  - 01-non-negotiables.md §API contract, §Security (OWASP A07 anti-enum)
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.errors import (
    ForgotPasswordRateLimitedError,
    InvalidPayloadError,
    ResetPasswordRateLimitedError,
    ResetTokenExpiredError,
    ResetTokenInvalidError,
)
from app.auth.rate_limit import check_rate_limit_forgot, check_rate_limit_reset
from app.auth.routers._helpers import (
    _error_response,
    _get_client_ip,
    _get_request_id,
)
from app.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ResponseMeta,
)
from app.auth.services.password_reset_consume import ResetPassword
from app.auth.services.password_reset_request import RequestPasswordReset
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)

forgot_reset_router = APIRouter()

# Anti-enum: always the same 200 body for forgot regardless of outcome
_FORGOT_SUCCESS_DATA = {"sent": True}
_RESET_SUCCESS_DATA = {"reset": True}


@forgot_reset_router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request a password reset email",
    description=(
        "Sends a reset link to the email if it exists (always returns 200 "
        "to prevent user enumeration). Rate-limited per IP."
    ),
)
def forgot_password_endpoint(
    request: Request,
    body: ForgotPasswordRequest,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Handle POST /api/v1/auth/forgot-password.

    Always returns 200 {data:{sent:true}} unless:
      - Pydantic validation fails (400) — email syntax error.
      - Rate limit exceeded (429).

    Args:
        request: FastAPI Request (for IP and X-Request-ID).
        body: ForgotPasswordRequest schema.
        session: SQLAlchemy Session (from DI).

    Returns:
        JSONResponse with {data:{sent:true}, meta:{request_id}}.
    """
    request_id = _get_request_id(request)
    ip = _get_client_ip(request)

    logger.debug(
        "auth.forgot.endpoint.start ip_prefix=%s request_id=%s",
        ip[:8] if ip else "unknown",
        request_id,
    )  # BEFORE

    # Rate limit check BEFORE business logic
    try:
        check_rate_limit_forgot(ip)
    except ForgotPasswordRateLimitedError as exc:
        logger.warning(
            "auth.forgot.endpoint.rate_limited retry_after=%ds request_id=%s",
            exc.retry_after,
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            headers={"Retry-After": str(exc.retry_after)},
        )

    use_case = RequestPasswordReset()
    try:
        use_case.execute(
            session=session,
            email=str(body.email),
            ip=ip,
            user_agent=request.headers.get("User-Agent", ""),
            request_id=request_id,
        )
    except Exception:
        # Best-effort: any unexpected error still returns 200 (anti-enum)
        logger.error(
            "auth.forgot.endpoint.unexpected_error request_id=%s",
            request_id,
            exc_info=True,
        )

    response_body = ForgotPasswordResponse(
        data=_FORGOT_SUCCESS_DATA,
        meta=ResponseMeta(request_id=request_id),
    )
    resp = JSONResponse(
        content=response_body.model_dump(),
        status_code=status.HTTP_200_OK,
    )

    logger.debug(
        "auth.forgot.endpoint.done request_id=%s",
        request_id,
    )  # AFTER
    return resp


@forgot_reset_router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password using a one-time token",
    description=(
        "Validates the token, updates the password, and revokes all sessions. "
        "Token is one-use; concurrent requests serialise via DB FOR UPDATE."
    ),
)
def reset_password_endpoint(
    request: Request,
    body: ResetPasswordRequest,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Handle POST /api/v1/auth/reset-password.

    Returns:
      - 200 {data:{reset:true}} on success.
      - 400 on payload validation failure.
      - 410 on invalid/expired/used token.
      - 429 on rate limit.

    Args:
        request: FastAPI Request (for IP and X-Request-ID).
        body: ResetPasswordRequest schema.
        session: SQLAlchemy Session (from DI).

    Returns:
        JSONResponse with appropriate status and envelope.
    """
    request_id = _get_request_id(request)
    ip = _get_client_ip(request)

    logger.debug(
        "auth.reset.endpoint.start ip_prefix=%s request_id=%s",
        ip[:8] if ip else "unknown",
        request_id,
    )  # BEFORE

    # Rate limit check first
    try:
        check_rate_limit_reset(ip)
    except ResetPasswordRateLimitedError as exc:
        logger.warning(
            "auth.reset.endpoint.rate_limited retry_after=%ds request_id=%s",
            exc.retry_after,
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            headers={"Retry-After": str(exc.retry_after)},
        )

    use_case = ResetPassword()
    try:
        use_case.execute(
            session=session,
            raw_token=body.token,
            new_password=body.password,
            ip=ip,
            user_agent=request.headers.get("User-Agent", ""),
            request_id=request_id,
        )
    except InvalidPayloadError as exc:
        logger.warning(
            "auth.reset.endpoint.invalid_payload field=%s request_id=%s",
            exc.field,
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            field=exc.field,
        )
    except ResetTokenExpiredError as exc:
        logger.warning(
            "auth.reset.endpoint.token_expired request_id=%s",
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
        )
    except ResetTokenInvalidError as exc:
        logger.warning(
            "auth.reset.endpoint.token_invalid request_id=%s",
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
        )

    response_body = ResetPasswordResponse(
        data=_RESET_SUCCESS_DATA,
        meta=ResponseMeta(request_id=request_id),
    )
    resp = JSONResponse(
        content=response_body.model_dump(),
        status_code=status.HTTP_200_OK,
    )

    logger.debug(
        "auth.reset.endpoint.done request_id=%s",
        request_id,
    )  # AFTER
    return resp
