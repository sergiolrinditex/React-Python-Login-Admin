"""
FastAPI router for the auth feature — POST /api/v1/auth/sign-up.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up
Phase: P01 — Auth + Base Capabilities

Endpoint:
  POST /sign-up
  (mounted in main.py under prefix /api/v1/auth → full path:
   POST /api/v1/auth/sign-up)

Status codes:
  201 Created          — success; body: {data: {mfa_required: true, user_id: UUID}}
  400 Bad Request      — malformed JSON (FastAPI default)
  409 Conflict         — email already registered; NON-LEAKY message
  422 Unprocessable    — Pydantic validation error OR business-rule violation
                         (corporate-email, weak-password, legal-acceptance)

Exception handler → HTTP mapping:
  EmailAlreadyExistsError     → 409 {errors: [{code: AUTH_EMAIL_TAKEN, ...}]}
  WeakPasswordError           → 422 {errors: [{code: AUTH_WEAK_PASSWORD, field: 'password'}]}
  NonCorporateEmailError      → 422 {errors: [{code: AUTH_NON_CORPORATE_EMAIL, field: 'email'}]}
  LegalAcceptanceMissingError → 422 {errors: [{code: AUTH_LEGAL_ACCEPTANCE_REQUIRED, ...}]}
  RequestValidationError      → 422 {errors: [...]} (Pydantic)

Security (task-pack §4.7 UX table + instrucciones §3.2):
  - 409 message MUST be generic ("Email no disponible") — never say "user exists".
  - code 'AUTH_EMAIL_TAKEN' lets the frontend localize differently without leaking info.

Dependencies:
  - fastapi 0.136.1
  - sqlalchemy.ext.asyncio.AsyncSession (via app.core.db.get_session)
  - app.features.auth.service (sign_up use case)
  - app.features.auth.errors (typed domain errors)
  - app.features.auth.schemas (request/response models)

Source: task-pack P01-S02-T001 §6.1 + §6.2
HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 + §6.4
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.features.auth import service
from app.features.auth.errors import (
    EmailAlreadyExistsError,
    LegalAcceptanceMissingError,
    NonCorporateEmailError,
    WeakPasswordError,
)
from app.features.auth.schemas import (
    AuthErrorCode,
    AuthErrorDetail,
    AuthErrorResponse,
    SignUpRequest,
    SignUpResponse,
    SignUpResponseData,
)

router = APIRouter(tags=["auth"])


@router.post(
    "/sign-up",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Create a new user account (email + Argon2id password hash + employee profile). "
        "Returns {data: {mfa_required: true, user_id}} — the caller must complete MFA "
        "enrollment at /auth/2fa before receiving an access token. "
        "Public endpoint — no authentication required."
    ),
)
async def sign_up(
    body: SignUpRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """POST /sign-up — main handler.

    Purpose: HTTP layer for the SignUpUserUseCase. Extracts request metadata
    (IP, User-Agent) and delegates to service.sign_up(); maps typed domain
    errors to structured HTTP responses.

    Params:
      body    — validated SignUpRequest (email, password, full_name, legal_acceptance).
      request — FastAPI Request (for client IP + User-Agent extraction).
      session — async SQLAlchemy session (from get_session dependency).
    Returns: 201 with SignUpResponse envelope.
    Raises (mapped to HTTP):
      422 — Pydantic validation error (body params) or business-rule violation.
      409 — email already registered (non-leaky response).
    """
    client_ip: str | None = request.client.host if request.client else None
    user_agent: str | None = request.headers.get("user-agent")

    try:
        data: SignUpResponseData = await service.sign_up(
            request=body,
            session=session,
            client_ip=client_ip,
            user_agent=user_agent,
        )
    except EmailAlreadyExistsError:
        # NON-LEAKY: must not say "user already exists" — task-pack §4.7 UX table.
        # The code AUTH_EMAIL_TAKEN allows frontend localization without exposing enumeration.
        error_body = AuthErrorResponse(
            errors=[
                AuthErrorDetail(
                    code=AuthErrorCode.AUTH_EMAIL_TAKEN,
                    message="Email no disponible. Por favor utiliza otro email.",
                    field="email",
                )
            ]
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body.model_dump(),
        )
    except LegalAcceptanceMissingError:
        error_body = AuthErrorResponse(
            errors=[
                AuthErrorDetail(
                    code=AuthErrorCode.AUTH_LEGAL_ACCEPTANCE_REQUIRED,
                    message="Debes aceptar los términos y condiciones para registrarte.",
                    field="legal_acceptance",
                )
            ]
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body.model_dump(),
        )
    except NonCorporateEmailError:
        error_body = AuthErrorResponse(
            errors=[
                AuthErrorDetail(
                    code=AuthErrorCode.AUTH_NON_CORPORATE_EMAIL,
                    message="Solo se permiten emails corporativos.",
                    field="email",
                )
            ]
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body.model_dump(),
        )
    except WeakPasswordError:
        error_body = AuthErrorResponse(
            errors=[
                AuthErrorDetail(
                    code=AuthErrorCode.AUTH_WEAK_PASSWORD,
                    message=(
                        "La contraseña debe tener al menos 12 caracteres, "
                        "una mayúscula, una minúscula, un número y un símbolo."
                    ),
                    field="password",
                )
            ]
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body.model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=SignUpResponse(data=data).model_dump(mode="json"),
    )
