"""
Pydantic models for the 'auth' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Covers data/verification/auth/mfa_primary.json.
The TOTP secret is a base32 string; must be marked synthetic_totp=True.
No real TOTP secrets may appear here — they would be rotated credentials.

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MfaPrimarySeed(BaseModel):
    """TOTP MFA configuration for the primary employee verification user.

    Purpose: pre-wire MFA for J100 journey without requiring a real OTP app.
    The secret is a base32-encoded string, clearly labelled synthetic.

    Params:
      totp_secret  — base32-encoded TOTP secret (RFC 4648).
      algorithm    — TOTP hash algorithm (SHA1 is the TOTP default per RFC 6238).
      digits       — OTP length (typically 6).
      period       — TOTP window in seconds (typically 30).
      synthetic_totp — MUST be True; rejects accidental copy of real secret.
    Errors: ValidationError if synthetic_totp is False or totp_secret is empty.
    """

    model_config = ConfigDict(extra="forbid")

    totp_secret: str = Field(
        ...,
        min_length=16,
        description="Base32-encoded TOTP shared secret.",
    )
    algorithm: Literal["SHA1", "SHA256", "SHA512"] = Field("SHA1")
    digits: int = Field(6, ge=6, le=8)
    period: int = Field(30, ge=15, le=60)
    synthetic_totp: bool = Field(
        ...,
        description="Must be True. Guard against copying real TOTP secrets.",
    )

    @field_validator("synthetic_totp")
    @classmethod
    def must_be_synthetic(cls, v: bool) -> bool:
        """Validate that synthetic_totp=True; reject real secrets by invariant."""
        if not v:
            raise ValueError(
                "synthetic_totp must be True. Do not place real TOTP secrets "
                "in the synthetic verification bundle."
            )
        return v
