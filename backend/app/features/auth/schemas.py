"""
Pydantic v2 request/response schemas for the auth feature.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up
Phase: P01 — Auth + Base Capabilities

Schemas:
  - SignUpRequest     — validated POST body for /api/v1/auth/sign-up
  - SignUpResponseData — inner data payload (mfa_required, user_id)
  - SignUpResponse    — envelope {data: SignUpResponseData} per §6.2
  - AuthErrorDetail   — single error item {code, message, field, details}
  - AuthErrorResponse — error envelope {errors: list[AuthErrorDetail]}

Error codes (AuthErrorCode):
  AUTH_EMAIL_TAKEN, AUTH_WEAK_PASSWORD, AUTH_NON_CORPORATE_EMAIL,
  AUTH_LEGAL_ACCEPTANCE_REQUIRED

Source:
  HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 + §6.4 (endpoint contract + error envelope)
  task-pack P01-S02-T001 §6.1 + §6.4
  instrucciones.md §3.2 (sign-up fields)

Dependencies:
  - pydantic 2.12.5 (EmailStr, model_validator)
"""
from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class AuthErrorCode(StrEnum):
    """Auth feature error codes used in API error responses.

    Purpose: typed enum so routes.py and tests can reference codes without magic strings.
    Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.4 + task-pack §4.7.
    """

    AUTH_EMAIL_TAKEN = "AUTH_EMAIL_TAKEN"
    AUTH_WEAK_PASSWORD = "AUTH_WEAK_PASSWORD"
    AUTH_NON_CORPORATE_EMAIL = "AUTH_NON_CORPORATE_EMAIL"
    AUTH_LEGAL_ACCEPTANCE_REQUIRED = "AUTH_LEGAL_ACCEPTANCE_REQUIRED"


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
