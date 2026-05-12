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
from typing import Any, Literal

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


# ---------------------------------------------------------------------------
# Sign-in request/response schemas (added P01-S02-T002)
# ---------------------------------------------------------------------------

class SignInRequest(BaseModel):
    """Request body for POST /api/v1/auth/sign-in.

    Both fields are required. Sign-in DOES NOT validate corporate email domain
    (that would create an enumeration oracle — see task pack §K Decision D-T002-1).

    Pydantic only provides syntactic RFC 5322 validation (EmailStr) and length
    guards. Business rejection (wrong password, unknown email) uses the service
    layer with aggregate-401 to prevent user enumeration.

    Attributes:
        email: Email address (RFC 5322; no domain restriction at sign-in).
        password: Raw password (min 1 char, max 512 char payload guard).
    """

    email: EmailStr = Field(
        ...,
        description="Email address. RFC 5322 syntax; domain not restricted at sign-in.",
        json_schema_extra={"example": "employee@inditex-sandbox.com"},
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Password. Minimum 1 char; maximum 512 char payload guard.",
    )


class SignInResponseSuccess(BaseModel):
    """Response envelope for successful sign-in without MFA (HTTP 200).

    Shape: {data: {mfa_required: false, access_token, token_type, expires_in},
            meta: {request_id}, errors: []}.

    The refresh token is NOT in the body — it is set as an HttpOnly cookie
    (D-RP5: access token never in cookie; refresh token never in body).

    Ref: task pack §E.2
    """

    data: dict = Field(description="Sign-in success payload with access_token.")
    meta: ResponseMeta
    errors: list[Any] = Field(default_factory=list)


class SignInResponseMfaChallenge(BaseModel):
    """Response envelope for sign-in requiring MFA (HTTP 200, mfa_required: true).

    Shape: {data: {mfa_required: true, mfa_challenge_token, expires_in},
            meta: {request_id}, errors: []}.

    No access_token, no Set-Cookie in this branch.
    mfa_challenge_token is a short-lived JWT (TTL = AUTH_MFA_CHALLENGE_TTL_SECONDS).
    Consumed by POST /api/v1/auth/2fa/verify (T006).

    Ref: task pack §E.3
    """

    data: dict = Field(description="MFA challenge payload with mfa_challenge_token.")
    meta: ResponseMeta
    errors: list[Any] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Forgot + reset password schemas (added P01-S02-T005)
# ---------------------------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/forgot-password.

    Anti-enumeration: if the email does not exist, the endpoint returns
    the same 200 body as if it did. The Pydantic layer only validates syntax.

    Attributes:
        email: User's email address (RFC 5322 syntax, no domain restriction).
    """

    email: EmailStr = Field(
        ...,
        description="Email address to send the reset link to.",
        json_schema_extra={"example": "employee@inditex-sandbox.com"},
    )


class ForgotPasswordResponse(BaseModel):
    """Response envelope for POST /api/v1/auth/forgot-password (HTTP 200).

    Always {data: {sent: true}, meta: {request_id}, errors: []} regardless
    of whether the email exists (anti-enumeration, per task pack §H-forgot-4).

    Attributes:
        data: Always {sent: true}.
        meta: Standard response metadata.
        errors: Always empty list.
    """

    data: dict = Field(
        default_factory=lambda: {"sent": True},
        description="Always {sent: true} — never reveals whether email exists.",
    )
    meta: ResponseMeta
    errors: list = Field(default_factory=list)


class ResetPasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/reset-password.

    Attributes:
        token: The URL-safe opaque token extracted from the reset link.
               Min 30 chars (token_urlsafe(32) produces ~43 chars).
        password: New plaintext password (policy enforced by service layer).
    """

    token: str = Field(
        ...,
        min_length=30,
        description="Reset token from the email link (URL-safe base64, ~43 chars).",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="New password. Min 12 chars, must contain upper, digit, and symbol.",
    )


class ResetPasswordResponse(BaseModel):
    """Response envelope for POST /api/v1/auth/reset-password (HTTP 200).

    Shape: {data: {reset: true}, meta: {request_id}, errors: []}.

    Attributes:
        data: Always {reset: true} on success.
        meta: Standard response metadata.
        errors: Always empty list.
    """

    data: dict = Field(
        default_factory=lambda: {"reset": True},
        description="Confirmation that the password was reset.",
    )
    meta: ResponseMeta
    errors: list = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 2FA verify request/response schemas (added P01-S02-T006) — WRITE_SET_DRIFT §D-MFA1.D
# ---------------------------------------------------------------------------


class MfaVerifyRequest(BaseModel):
    """Request body for POST /api/v1/auth/2fa/verify.

    The field `challenge_id` carries the full JWT mfa_challenge_token string
    issued by sign-in when MFA is required. Despite the name `challenge_id`,
    the VALUE is the JWT string itself — not a DB identifier. This naming
    matches §6.2 row 261 of the TECHNICAL_GUIDE exactly so the frontend
    TwoFactorPage (P03-S01-T005) sends the correct field name.

    Attributes:
        challenge_id: The mfa_challenge_token JWT from the sign-in response.
                      Min 30 chars (guard); real JWTs are ~180 chars.
        code: 6-digit TOTP code from the user's authenticator app.
              Must be all digits (field_validator enforces).
    """

    challenge_id: str = Field(
        ...,
        min_length=30,
        max_length=2048,
        description=(
            "JWT mfa_challenge_token from sign-in MFA branch. "
            "Despite the name 'challenge_id', the value IS the JWT string. "
            "Min 30 is a payload guard; real JWTs are ~180 chars."
        ),
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit TOTP code from the user's authenticator app.",
        json_schema_extra={"example": "123456"},
    )

    @field_validator("code")
    @classmethod
    def code_must_be_six_digits(cls, v: str) -> str:
        """Ensure code is exactly 6 numeric characters.

        Args:
            v: Raw code value.

        Returns:
            Validated code string.

        Raises:
            ValueError: If code is not exactly 6 digits.
        """
        if not v.isdigit() or len(v) != 6:
            raise ValueError("code must be exactly 6 numeric digits")
        return v


class MfaUserDto(BaseModel):
    """User summary returned in the 2FA verify success body.

    Included in the response so TwoFactorPage (P03-S01-T005) does not need
    a separate GET /users/me round-trip after successful MFA. Matches §6.2
    row 261 contract {data: {access_token, user}}.

    Attributes:
        id: User UUID.
        email: Corporate email address.
        preferred_language: Language preference ('es'|'en'|'fr').
        roles: List of assigned role names (e.g. ['employee']).
    """

    id: uuid.UUID
    email: EmailStr
    preferred_language: Literal["es", "en", "fr"]
    roles: list[str]


class MfaVerifySuccessData(BaseModel):
    """Data payload for the 2FA verify success envelope.

    Attributes:
        access_token: Short-lived JWT access token (HS256).
        token_type: Always 'Bearer'.
        expires_in: Access token TTL in seconds (AUTH_ACCESS_TTL_SECONDS default 1800).
        user: User summary DTO (avoids GET /users/me round-trip).
    """

    access_token: str = Field(description="Short-lived JWT access token. NEVER store in localStorage.")
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(description="Token TTL in seconds.")
    user: MfaUserDto


class MfaVerifyResponseSuccess(BaseModel):
    """Envelope response for POST /api/v1/auth/2fa/verify (HTTP 200).

    Shape: {data: MfaVerifySuccessData, meta: ResponseMeta, errors: []}.
    Ref: TECHNICAL_GUIDE §6.2 row 261, task pack §F.6.
    """

    data: MfaVerifySuccessData
    meta: ResponseMeta
    errors: list[Any] = Field(default_factory=list)
