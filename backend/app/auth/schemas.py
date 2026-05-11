"""
Hilo People — Auth Pydantic request/response schemas.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Pydantic v2 schemas for the sign-up endpoint request body and response
         envelope. These are the data-transfer objects (DTOs) for the presentation
         layer. The frontend TypeScript types (T003-S01-T002) must mirror these.

Key deps:
  - pydantic==2.12.5 (BaseModel, EmailStr, field_validator)
  - pydantic[email] / email-validator==2.3.0 — required for EmailStr
  - app.auth.domain.CORPORATE_EMAIL_DOMAINS — used for domain validation hint

Source refs:
  - TECHNICAL_GUIDE §6.2 request body: {email, password, full_name, legal_acceptance}
  - TECHNICAL_GUIDE §6.2 response: {data: {mfa_required: bool, user_id: UUID}}
  - task pack §C.3 error codes (AUTH_SIGNUP_*)
  - task pack §E (UX note: errors[].field must match request schema keys)
  - official-doc-notes M.2: Pydantic v2 EmailStr + field_validator pattern

Decisions:
  - EmailStr provides RFC 5322 syntactic validation (no DNS lookup — email-validator
    2.3.0 does not perform DNS by default when check_deliverability=False is set,
    but pydantic uses check_deliverability=False internally). Domain membership
    is checked separately by CorporateEmail value object in the service layer.
  - legal_acceptance is a plain `bool` at the schema layer. Policy enforcement
    (must equal True) lives in the SERVICE layer (`service.py:134-146`) so that:
      (a) HTTP status is 400 (as pinned by task pack §C.3), not Pydantic's 422,
      (b) response uses the project `{data, meta, errors}` envelope (not FastAPI's
          default `{detail:[...]}` shape from RequestValidationError),
      (c) the BR5 audit-every-attempt invariant holds — the service writes a
          rejection audit row for `legal_acceptance=false` before raising
          LegalNotAcceptedError. Validators in Pydantic would bypass the service
          and silently break BR5.
  - full_name: min 1 char after strip (Pydantic min_length would not strip).
  - Password raw str — policy validated by Password value object in service layer
    (avoids duplicating policy here; Pydantic only checks min 1 / max 512 guard
    to prevent giant payloads before reaching service).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class SignUpRequest(BaseModel):
    """Request body for POST /api/v1/auth/sign-up.

    All fields are required. Legal acceptance must be the boolean True
    (not a truthy value) — validated server-side per BR2.

    Attributes:
        email: Corporate email address (RFC 5322 syntax; domain checked by service).
        password: Raw password (12-256 chars with letter+digit; policy in service).
        full_name: Employee display name (1-200 chars, stripped).
        legal_acceptance: Must be literal True; 400 if False or missing.
    """

    email: EmailStr = Field(
        ...,
        description="Corporate email address. Domain must be in the allowed corporate set.",
        json_schema_extra={"example": "employee@inditex-sandbox.com"},
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=512,  # guard against oversized payloads; service checks ≤256
        description="Password. Min 12 chars, must contain at least 1 letter and 1 digit.",
        json_schema_extra={"example": "VerifyPass2024!"},
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Employee display name.",
        json_schema_extra={"example": "Ana García"},
    )
    legal_acceptance: bool = Field(
        ...,
        description=(
            "Must be true to complete registration. False is rejected by the "
            "service layer with HTTP 400 + envelope code "
            "AUTH_SIGNUP_LEGAL_NOT_ACCEPTED + audit row (BR5)."
        ),
    )

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: Any) -> str:
        """Strip whitespace from full_name before min_length check.

        Args:
            v: Raw full_name value from request body.

        Returns:
            Stripped string.

        Raises:
            ValueError: If stripped value is empty.
        """
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("full_name must not be empty or whitespace-only")
            return stripped
        return v

    # NOTE: There is intentionally NO field_validator for `legal_acceptance`.
    # Policy enforcement (must equal True) is performed in the SERVICE layer
    # (`service.py:134-146`) so the rejection path produces:
    #   - HTTP 400 (not Pydantic's 422), matching task pack §C.3 pin.
    #   - The project `{data, meta, errors}` envelope (not FastAPI's
    #     `{detail:[...]}` from RequestValidationError).
    #   - An audit_logs row with action='auth.sign_up', outcome='rejected',
    #     reason='LEGAL_NOT_ACCEPTED', preserving the BR5 audit-every-attempt
    #     invariant.
    # See validator finding F2 (cycle 1) and debugger fix (cycle 1).


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SignUpData(BaseModel):
    """Data payload returned in the success envelope for sign-up.

    Attributes:
        user_id: UUID of the newly created user account.
        mfa_required: Always False for new employees at sign-up (forward-compat
                      field for future admin onboarding flows).
    """

    user_id: uuid.UUID = Field(description="UUID of the newly created user.")
    mfa_required: bool = Field(
        default=False,
        description="Whether 2FA setup is required before first sign-in.",
    )


class ResponseMeta(BaseModel):
    """Standard response metadata wrapper."""

    request_id: str = Field(description="X-Request-ID correlation header value.")


class SignUpResponse(BaseModel):
    """Envelope response for POST /api/v1/auth/sign-up (HTTP 201).

    Shape: {data: SignUpData, meta: ResponseMeta, errors: []}.
    Per TECHNICAL_GUIDE §6.2 envelope contract: {data, meta, errors}.
    """

    data: SignUpData
    meta: ResponseMeta
    errors: list[Any] = Field(default_factory=list)


class ErrorItem(BaseModel):
    """Single error item in the errors[] array of the error envelope.

    Attributes:
        code: Machine-readable error code (e.g. 'AUTH_SIGNUP_NON_CORPORATE_EMAIL').
        message: English debug message (NOT displayed to the user — frontend localises).
        field: Optional field name for field-level errors (e.g. 'email', 'password').
        details: Optional additional context.
    """

    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Error envelope returned on 4xx/5xx responses.

    Shape: {data: null, meta: ResponseMeta, errors: [ErrorItem]}.
    """

    data: None = None
    meta: ResponseMeta
    errors: list[ErrorItem]
