"""
FastAPI router for MFA enrollment — POST /api/v1/auth/2fa/enroll.

Slice: P01-S02-T009 — POST /api/v1/auth/2fa/enroll
Phase: P01 — Auth + Base Capabilities

This module defines a sub-router mounted at '/2fa' within the auth_router
(prefix '/api/v1/auth'), producing the final path:
  POST /api/v1/auth/2fa/enroll

Wiring: this router is imported and included in app/features/auth/routes.py
(see the include_router call there). main.py is NOT modified (task-pack §6.1).

Status codes:
  201 Created  — success; body: {data: {otpauth_url, qr_png_base64}}
  401 Unauthorized — invalid credentials (re-auth failed)
  422 Unprocessable — Pydantic validation error (malformed payload)
  500 Internal     — encryption, QR generation, or unexpected DB failure

Exception handler → HTTP mapping:
  InvalidCredentialsError → 401 {errors: [{code: AUTH_INVALID_CREDENTIALS}]}
  Exception (unexpected)  → 500 {errors: [{code: INTERNAL_ERROR}]}

Auth scheme (D1, task-pack §9 D1):
  Re-authentication via email+password in request body. No Bearer JWT required.
  This avoids the chicken-and-egg: T002 sign-in (which issues JWTs) depends on
  T006 2fa/verify, which depends on enrollment. email+password is the simplest
  secure pattern (step-up auth, used by GitHub, AWS, Stripe for 2FA setup).

Security notes:
  - password is SecretStr in MfaEnrollRequest — never repr'd or logged by Pydantic.
  - No secret, otpauth_url, or qr_png_base64 is logged here or in the service.
  - Rate-limit dependency: T008 (pending) must include this endpoint in its allowlist.
    Until T008 lands, this endpoint is public with no rate-limit (tracked R2 in pack).

Dependencies:
  - fastapi 0.136.1
  - app.core.db.get_session (async SQLAlchemy session)
  - app.features.auth.mfa_service (enroll_mfa use case)
  - app.features.auth.errors (InvalidCredentialsError)
  - app.features.auth.schemas (MfaEnrollRequest, MfaEnrollResponse, ...)

Source:
  task-pack P01-S02-T009 §5 (endpoint contract) + §6 (architecture + wiring)
  HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 (endpoint table gap — closed by this slice)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.logging import get_logger
from app.features.auth import mfa_service
from app.features.auth.errors import InvalidCredentialsError
from app.features.auth.schemas import (
    AuthErrorCode,
    AuthErrorDetail,
    AuthErrorResponse,
    MfaEnrollRequest,
    MfaEnrollResponse,
    MfaEnrollResponseData,
)

_logger = get_logger(__name__)

# Sub-router mounted at '/2fa' within the auth_router ('/api/v1/auth')
# → full path: /api/v1/auth/2fa/...
mfa_router = APIRouter(tags=["auth", "mfa"])


@mfa_router.post(
    "/enroll",
    response_model=MfaEnrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll MFA (TOTP) for a user",
    description=(
        "Generate a TOTP secret for the authenticated user via re-auth (email+password). "
        "Returns the otpauth Key URI and a QR code PNG (base64) for scanning with an "
        "authenticator app (Google Authenticator, 1Password, Authy, etc.). "
        "The secret is stored Fernet-encrypted in mfa_totp_secrets (enabled=false). "
        "The user must call POST /2fa/verify (T006) to activate the enrollment. "
        "Re-enrollment is allowed (rotates the secret — enabled reset to false). "
        "Public endpoint — auth via email+password in request body (step-up auth)."
    ),
)
async def enroll_endpoint(
    body: MfaEnrollRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """POST /2fa/enroll — MFA enrollment handler.

    Purpose: HTTP layer for the enroll_mfa use case. Extracts request metadata
    (IP, User-Agent) and delegates to mfa_service.enroll_mfa(); maps typed domain
    errors to structured HTTP responses per task-pack §5.3.

    Params:
      body    — validated MfaEnrollRequest (email: EmailStr, password: SecretStr).
      request — FastAPI Request (for client IP + User-Agent extraction).
      session — async SQLAlchemy session (from get_session dependency).
    Returns: 201 with MfaEnrollResponse envelope.
    Raises (mapped to HTTP):
      401 — invalid credentials (email not found OR wrong password — same response).
      422 — Pydantic validation error (payload malformed).
      500 — unexpected error (encryption fail, DB fail, QR generation fail).
    """
    client_ip: str | None = request.client.host if request.client else None
    user_agent: str | None = request.headers.get("user-agent")

    try:
        data: MfaEnrollResponseData = await mfa_service.enroll_mfa(
            request=body,
            session=session,
            client_ip=client_ip,
            user_agent=user_agent,
        )
    except InvalidCredentialsError:
        # Generic 401 — does NOT reveal whether email exists or password is wrong.
        # This prevents user-enumeration attacks (task-pack §5.3 D1).
        error_body = AuthErrorResponse(
            errors=[
                AuthErrorDetail(
                    code=AuthErrorCode.AUTH_INVALID_CREDENTIALS,
                    message="Credenciales inválidas.",
                )
            ]
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_body.model_dump(),
        )
    except Exception:
        # Catch unexpected errors (encryption failure, DB failure, QR generation)
        # and return a generic 500 without leaking internals.
        _logger.warning(
            "ERROR auth.mfa.enroll.unexpected_error: returning 500",
        )
        error_body = AuthErrorResponse(
            errors=[
                AuthErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Error interno del servidor.",
                )
            ]
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body.model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=MfaEnrollResponse(data=data).model_dump(mode="json"),
    )
