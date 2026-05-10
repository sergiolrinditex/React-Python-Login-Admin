"""
Pydantic v2 request/response schemas for the auth feature.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up (base)
       P01-S02-T009 — POST /api/v1/auth/2fa/enroll (extended)
Phase: P01 — Auth + Base Capabilities

Schemas:
  - SignUpRequest     — validated POST body for /api/v1/auth/sign-up
  - SignUpResponseData — inner data payload (mfa_required, user_id)
  - SignUpResponse    — envelope {data: SignUpResponseData} per §6.2
  - AuthErrorDetail   — single error item {code, message, field, details}
  - AuthErrorResponse — error envelope {errors: list[AuthErrorDetail]}
  - MfaEnrollRequest  — validated POST body for /api/v1/auth/2fa/enroll (T009)
  - MfaEnrollResponseData — inner data payload (otpauth_url, qr_png_base64)
  - MfaEnrollResponse — envelope {data: MfaEnrollResponseData} (T009)

Error codes (AuthErrorCode):
  AUTH_EMAIL_TAKEN, AUTH_WEAK_PASSWORD, AUTH_NON_CORPORATE_EMAIL,
  AUTH_LEGAL_ACCEPTANCE_REQUIRED, AUTH_INVALID_CREDENTIALS (T009),
  AUTH_2FA_ALREADY_ENROLLED (T009)

Source:
  HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 + §6.4 (endpoint contract + error envelope)
  task-pack P01-S02-T001 §6.1 + §6.4
  task-pack P01-S02-T009 §5.1 + §5.2 + §5.3
  instrucciones.md §3.2 (sign-up fields)

Dependencies:
  - pydantic 2.12.5 (EmailStr, SecretStr, model_validator)
"""
from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class AuthErrorCode(StrEnum):
    """Auth feature error codes used in API error responses.

    Purpose: typed enum so routes.py and tests can reference codes without magic strings.
    Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.4 + task-pack §4.7 (T001) + §5.3 (T009).
    """

    AUTH_EMAIL_TAKEN = "AUTH_EMAIL_TAKEN"
    AUTH_WEAK_PASSWORD = "AUTH_WEAK_PASSWORD"
    AUTH_NON_CORPORATE_EMAIL = "AUTH_NON_CORPORATE_EMAIL"
    AUTH_LEGAL_ACCEPTANCE_REQUIRED = "AUTH_LEGAL_ACCEPTANCE_REQUIRED"
    # Added in P01-S02-T009 (MFA enrollment)
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_2FA_ALREADY_ENROLLED = "AUTH_2FA_ALREADY_ENROLLED"


class SignUpRequest(BaseModel):
    """POST /api/v1/auth/sign-up request body.

    Business rules (task-pack §6.4):
      - email: RFC-5322 validated by Pydantic EmailStr; corporate-domain rule enforced
        in service.py (config-driven, not in schema).
      - password: min 12 chars + complexity validated in service.py (schema accepts any str;
        business validation separated to avoid leaking raw value into Pydantic error messages).
      - full_name: 1..200 chars after strip; whitespace-only → rejected.
      - legal_acceptance: must be True; enforced in service.py (schema accepts bool).

    Params:
      email           — corporate email address.
      password        — plain-text password (hashed by service; NEVER stored or logged raw).
      full_name       — display name (trimmed).
      legal_acceptance — must be True per instrucciones §3.2.
    """

    email: EmailStr = Field(
        ...,
        description="Corporate email address (RFC-5322). Corporate-domain rule config-driven.",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Plain-text password. Never stored raw; Argon2id-hashed in service.",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name (1..200 chars; trimmed).",
    )
    legal_acceptance: bool = Field(
        ...,
        description="Must be True. Explicit acceptance of terms per instrucciones §3.2.",
    )

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: Any) -> str:
        """Strip surrounding whitespace from full_name.

        Purpose: ensure whitespace-only strings fail the min_length=1 check.
        Params: v — raw value before Pydantic coercion.
        Returns: stripped string.
        """
        if isinstance(v, str):
            return v.strip()
        return v


class SignUpResponseData(BaseModel):
    """Inner data payload for a successful sign-up response.

    Purpose: carry the new user's ID and MFA redirect signal.
    Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 line 249.

    mfa_required is always True (sign-up always requires MFA enrollment;
    next_action = /auth/2fa per UX_CONTRACT §3 + task-pack §9 D3).
    """

    mfa_required: bool = Field(True, description="Always True — sign-up triggers MFA enrollment.")
    user_id: uuid.UUID = Field(..., description="UUID of the newly created user row.")


class SignUpResponse(BaseModel):
    """Envelope for a successful POST /api/v1/auth/sign-up response.

    Shape: {data: SignUpResponseData} per HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 envelope.
    """

    data: SignUpResponseData


class AuthErrorDetail(BaseModel):
    """Single error item in the errors array.

    Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.4 error envelope.
    """

    code: str = Field(..., description="Machine-readable error code (e.g. AUTH_EMAIL_TAKEN).")
    message: str = Field(..., description="Human-readable description (safe to display).")
    field: str | None = Field(None, description="Which request field triggered the error.")
    details: list[Any] = Field(default_factory=list, description="Per-field sub-errors.")


class AuthErrorResponse(BaseModel):
    """Error response envelope: {errors: [AuthErrorDetail]}.

    Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.4 (error envelope structure).
    """

    errors: list[AuthErrorDetail]


# ---------------------------------------------------------------------------
# P01-S02-T009 — POST /api/v1/auth/2fa/enroll schemas
# ---------------------------------------------------------------------------


class MfaEnrollRequest(BaseModel):
    """POST /api/v1/auth/2fa/enroll request body.

    Re-authentication scheme (D1, task-pack §9 D1 + §5.4):
      The user proves identity via email+password (step-up auth).
      This avoids a chicken-and-egg with Bearer JWT which doesn't exist yet
      (T002 sign-in / T006 verify not yet implemented at this slice).

    Security notes:
      - `password` is SecretStr — Pydantic will NOT print or repr it in error
        messages or logs. CWE-532 guard at the schema boundary.
      - email validated as EmailStr (requires email-validator==2.2.0).
      - Corporate-domain rule is NOT enforced here (the user already registered;
        sign-up enforced it). The service only checks credentials.

    Source: task-pack P01-S02-T009 §5.1
    """

    email: EmailStr = Field(
        ...,
        description="Email address used at sign-up (re-auth identity).",
    )
    password: SecretStr = Field(
        ...,
        description=(
            "Plain-text password for re-authentication. "
            "SecretStr prevents repr/logging of the value."
        ),
    )


class MfaEnrollResponseData(BaseModel):
    """Inner data payload for a successful MFA enrollment response.

    Purpose: carry the otpauth URI and QR PNG so the frontend can render the
    QR code to the user for scanning with an authenticator app.

    Fields:
      otpauth_url    — standard Key URI (RFC 6238 + Google Authenticator format).
                       Contains the TOTP secret in the `?secret=` query param.
                       The frontend uses this for deep-linking to authenticator apps.
      qr_png_base64 — PNG of the otpauth_url, base64-encoded (no data: prefix).
                      Frontend renders as <img src={`data:image/png;base64,${qr}`} />.

    Security: this response MUST only be sent over HTTPS in production.
    The secret travels as plaintext in the QR data — it is not stored by the
    server after this response. The encrypted form is in mfa_totp_secrets.

    Source: task-pack P01-S02-T009 §5.2
    """

    otpauth_url: str = Field(
        ...,
        description=(
            "otpauth Key URI (RFC 6238). Example: "
            "otpauth://totp/Hilo%20People:user@example.com?"
            "secret=BASE32SECRET&issuer=Hilo%20People"
        ),
    )
    qr_png_base64: str = Field(
        ...,
        description=(
            "PNG image of the QR code for the otpauth_url, base64-encoded "
            "(no data:image/png;base64, prefix). Use with "
            "<img src={`data:image/png;base64,${qr_png_base64}`} /> in the frontend."
        ),
    )


class MfaEnrollResponse(BaseModel):
    """Envelope for a successful POST /api/v1/auth/2fa/enroll response.

    Shape: {data: MfaEnrollResponseData} per HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 envelope.
    Source: task-pack P01-S02-T009 §5.2
    """

    data: MfaEnrollResponseData
