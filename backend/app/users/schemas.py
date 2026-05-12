"""
Hilo People — Pydantic v2 schemas for the users feature.

Slice:  P01-S02-T007 — GET /api/v1/users/me + PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: Request/response DTOs (data transfer objects) for the users endpoints.
         Pins the UserProfile schema (§F.3 of task pack) as the merged shape
         consumed by both ChatHomePage (P03-S02-T001) and AccountPage (P03-S02-T004).

Key deps:
  - pydantic==2.12.5 (BaseModel, EmailStr, Literal, ConfigDict)
  - app.auth.schemas.ResponseMeta — reused for the meta envelope field

Source refs:
  - task pack §F.3 (UserProfile fields + rationale)
  - task pack §F.2 (PATCH /me/language — 200 with UserProfile body, NOT 204)
  - TECHNICAL_GUIDE §6.2 rows 262, 263 (envelope contract)
  - DISCREPANCY-2: UserProfile schema is not defined in §6.3; pinned here
  - DISCREPANCY-5: error_validation for PATCH only; GET has no body validation

Decisions:
  - UserProfile is the single merged shape for both GET /me and PATCH /me/language
    success responses. Keeps AccountPage + ChatHomePage aligned on one contract.
  - extra_metadata (DB column 'metadata') is intentionally omitted from response —
    prevents leaking arbitrary JSONB to UI by default (task pack §F.3 rationale).
  - password_hash is NEVER included. Hard non-negotiable.
  - roles: list[str] defaulting to ['employee'] matches encode_access_token (G.9).
  - LanguagePatchRequest uses ConfigDict(strict=True, extra='forbid') to reject
    extra fields per T19 (task pack §J).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.schemas import ResponseMeta


# ---------------------------------------------------------------------------
# Nested DTO — employee profile fields (returned inside UserProfile)
# ---------------------------------------------------------------------------

class UserProfileEmployeeFields(BaseModel):
    """Employee organisation fields nested in UserProfile.

    Intentionally omits extra_metadata (DB column 'metadata') — see module docstring.
    The 6 declared fields are exactly what UX needs: employee_id, brand, society,
    center, country, department.

    Attributes:
        employee_id: Internal HR identifier (globally unique).
        brand: Brand assignment (e.g. 'Zara', 'Massimo Dutti').
        society: Legal entity code (e.g. 'ITX-ES').
        center: Physical office/center (e.g. 'Madrid-HQ').
        country: ISO 3166-1 alpha-2 country code (e.g. 'ES').
        department: Department name (e.g. 'People & Talent').
    """

    model_config = ConfigDict(from_attributes=True)

    employee_id: str = Field(description="Internal HR employee identifier, globally unique.")
    brand: str = Field(description="Brand assignment (e.g. Zara, Massimo Dutti).")
    society: str = Field(description="Legal entity code (e.g. ITX-ES).")
    center: str = Field(description="Office or center name (e.g. Madrid-HQ).")
    country: str = Field(description="ISO 3166-1 alpha-2 country code (e.g. ES).")
    department: str = Field(description="Department name (e.g. People & Talent).")


# ---------------------------------------------------------------------------
# Primary DTO — full user profile (GET /me and PATCH /me/language)
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    """Merged user + employee profile shape returned by both /me endpoints.

    This schema is the pinned contract (task pack §F.3 / DISCREPANCY-2).
    Both ChatHomePage and AccountPage consume this exact shape. Any future
    field additions must go through a source-of-truth amendment.

    Attributes:
        id: User UUID.
        email: Corporate email address (EmailStr for format validation).
        full_name: Employee display name.
        status: Account status: one of active|inactive|pending|locked.
        preferred_language: Language preference: one of es|en|fr.
        roles: List of role names. Defaults to ['employee'] if no DB rows.
        employee_profile: Organisation fields; null for users without a profile row
                          (e.g. admin users — see DISCREPANCY-3).
        created_at: Account creation timestamp (ISO-8601 UTC).
        updated_at: Last update timestamp (ISO-8601 UTC). Updated by PATCH /me/language.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="User UUID.")
    email: EmailStr = Field(description="Corporate email address.")
    full_name: str = Field(description="Employee display name.")
    status: Literal["active", "inactive", "pending", "locked"] = Field(
        description="Account lifecycle status."
    )
    preferred_language: Literal["es", "en", "fr"] = Field(
        description="UI language preference."
    )
    roles: list[str] = Field(
        default_factory=list,
        description="List of assigned role names. Defaults to ['employee'] if empty.",
    )
    employee_profile: UserProfileEmployeeFields | None = Field(
        default=None,
        description=(
            "Organisation profile fields. Null for admin users who have no "
            "employee_profile row (DISCREPANCY-3)."
        ),
    )
    created_at: datetime = Field(description="Account creation timestamp (UTC).")
    updated_at: datetime = Field(description="Last update timestamp (UTC).")


# ---------------------------------------------------------------------------
# Response envelope — success (both endpoints return this)
# ---------------------------------------------------------------------------

class UserProfileResponse(BaseModel):
    """Envelope response for GET /api/v1/users/me and PATCH /api/v1/users/me/language.

    Shape: {data: UserProfile, meta: ResponseMeta, errors: []}.
    Both endpoints return HTTP 200 with this envelope (DISCREPANCY-1 resolved:
    PATCH returns 200 with body, NOT 204).

    Attributes:
        data: Full user profile including employee fields.
        meta: Standard request correlation metadata.
        errors: Always empty list on success.
    """

    data: UserProfile
    meta: ResponseMeta
    errors: list[Any] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request schema — PATCH /me/language
# ---------------------------------------------------------------------------

class LanguagePatchRequest(BaseModel):
    """Request body for PATCH /api/v1/users/me/language.

    Strict mode (ConfigDict strict=True) rejects non-string types for language.
    Extra fields are forbidden (ConfigDict extra='forbid') per T19 (task pack §J).
    The whitelist {es, en, fr} is enforced by Pydantic Literal at parse time;
    the global RequestValidationError handler in main.py maps the resulting 422
    to 400 AUTH_INVALID_PAYLOAD + field='language' (G.7 / DISCREPANCY-1).

    Attributes:
        language: New language preference. Must be one of 'es', 'en', or 'fr'.
                  Case-sensitive: 'EN' is rejected (T20).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    language: Literal["es", "en", "fr"] = Field(
        description=(
            "New language preference. Whitelist: 'es' | 'en' | 'fr'. "
            "Case-sensitive (no auto-lowercase). null/empty/uppercase rejected."
        ),
        json_schema_extra={"example": "en"},
    )
