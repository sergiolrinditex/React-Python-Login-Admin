"""
Pydantic models for the 'users' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Covers data/verification/users/*.json fixtures.
Fields align with the DB schema defined in P01-S01-T001 (users + employee_profiles).
Uses extra='forbid' so structurally invalid fixtures fail fast.

NOTE: EmailStr is NOT used here — it requires email-validator which is not in the
  dep stack (rule: no dep for something doable in <20 lines). A field_validator
  with a simple regex provides the same gate without the extra package.

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmployeeProfileSeed(BaseModel):
    """Employee profile fields required for auth/journey verification.

    Purpose: capture employee-specific data for journey J100.
    """

    model_config = ConfigDict(extra="forbid")

    department: str = Field(..., description="Department name.")
    job_title: str = Field(..., description="Job title.")
    manager_email: str | None = Field(None, description="Manager email (optional).")
    hire_date: str = Field(..., description="ISO date string (YYYY-MM-DD).")
    language_preference: str = Field("es", description="Preferred UI language code.")


class UserSeed(BaseModel):
    """Verification seed for a single user record.

    Purpose: base fixture type for employee_primary and admin_peopletech.
    Params:
      email          — unique user email (hilopeople.com domain for synthetic).
      full_name      — display name.
      password_plain_for_seed — plaintext password for seeding only (loader hashes it).
      role           — 'employee' or 'admin'.
      mfa_enabled    — whether TOTP MFA is pre-configured for this user.
      employee_profile — optional employee profile data (only for role='employee').
    Errors: ValidationError if any required field is missing.
    """

    model_config = ConfigDict(extra="forbid")

    email: str
    full_name: str = Field(..., min_length=2, max_length=200)
    password_plain_for_seed: str = Field(
        ..., min_length=8, description="Plaintext for seed — loader hashes with argon2."
    )
    role: Literal["employee", "admin"] = Field("employee")
    mfa_enabled: bool = Field(False)
    is_active: bool = Field(True)
    employee_profile: EmployeeProfileSeed | None = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Validate that the email looks like a valid email address.

        Purpose: catch copy-paste errors in fixture files; not a full RFC 5322
        validator (email-validator package not in dep stack).
        """
        if not _EMAIL_RE.match(v):
            raise ValueError(
                f"Invalid email format: {v!r}. "
                "Verification bundle emails must match user@domain.tld."
            )
        return v
