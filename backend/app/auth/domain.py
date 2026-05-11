"""
Hilo People — Auth domain value objects and pure domain rules.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Pure domain objects (no DB, no FastAPI) for corporate email validation
         and password policy enforcement. These are instantiated by the service
         layer BEFORE any I/O to fail fast.

Key deps:
  - app.auth.errors — typed domain errors (no external deps)
  - os, re: stdlib only — domain layer must remain free of third-party imports

Source refs:
  - TECHNICAL_GUIDE §10.2 (auth strategy — Argon2, no magic sign-in at sign-up)
  - task pack §F.1 (CORPORATE_EMAIL_DOMAINS env var, comma-separated, fail-closed)
  - task pack §F.2 (password policy: 12-256 chars, 1 letter + 1 digit)
  - 01-non-negotiables.md §Code architecture (domain imports nothing external)

Decisions:
  - Corporate domain list loaded from env var CORPORATE_EMAIL_DOMAINS at module
    import time. Empty value → empty set → all corporate emails rejected
    (fail-closed security posture).
  - Domain-only is logged (not full email) at INFO level for compliance.
"""

from __future__ import annotations

import os
import re

from app.auth.errors import NonCorporateEmailError, PasswordPolicyError


# ---------------------------------------------------------------------------
# Corporate email domain allowlist — loaded from environment (fail-closed)
# ---------------------------------------------------------------------------
_DEFAULT_DOMAINS = (
    "inditex.com,inditex-sandbox.com,zara.com,zarahome.com,"
    "massimodutti.com,bershka.com,pullandbear.com,"
    "stradivarius.com,oysho.com,lefties.com"
)

_CORPORATE_DOMAINS_RAW: str = os.getenv("CORPORATE_EMAIL_DOMAINS", _DEFAULT_DOMAINS)
# Normalise: lowercase, strip whitespace, remove empty entries.
CORPORATE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    d.strip().lower()
    for d in _CORPORATE_DOMAINS_RAW.split(",")
    if d.strip()
)

# ---------------------------------------------------------------------------
# Password policy constants
# ---------------------------------------------------------------------------
PASSWORD_MIN_LENGTH: int = 12
PASSWORD_MAX_LENGTH: int = 256
_RE_HAS_LETTER = re.compile(r"[a-zA-Z]")
_RE_HAS_DIGIT = re.compile(r"\d")


# ---------------------------------------------------------------------------
# CorporateEmail value object
# ---------------------------------------------------------------------------

class CorporateEmail:
    """Validated corporate email value object.

    Validates that the email domain (the part after @) is in the allowed
    CORPORATE_EMAIL_DOMAINS set. Syntax validation is handled upstream by
    Pydantic EmailStr; this class only checks domain membership.

    Attributes:
        value: The full email address (lowercase-normalised).
        domain: The domain part only (e.g. 'inditex-sandbox.com').

    Raises:
        NonCorporateEmailError: If the domain is not in the corporate allowlist.

    Example:
        >>> ce = CorporateEmail("alice@inditex.com")
        >>> ce.domain
        'inditex.com'
    """

    __slots__ = ("value", "domain")

    def __init__(self, email: str) -> None:
        """
        Args:
            email: Syntactically-valid email string (already validated by Pydantic).

        Raises:
            NonCorporateEmailError: If domain not in CORPORATE_EMAIL_DOMAINS.
        """
        normalised = email.strip().lower()
        # domain extraction — syntax already validated upstream by EmailStr
        at_idx = normalised.rfind("@")
        domain = normalised[at_idx + 1:] if at_idx != -1 else ""
        if domain not in CORPORATE_EMAIL_DOMAINS:
            raise NonCorporateEmailError(domain)
        self.value: str = normalised
        self.domain: str = domain

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CorporateEmail):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


# ---------------------------------------------------------------------------
# Password value object
# ---------------------------------------------------------------------------

class Password:
    """Validated password value object.

    Enforces the password policy: min 12, max 256 characters, must contain
    at least 1 letter and 1 digit. The plain-text value is never stored
    after the Argon2 hash is computed.

    Attributes:
        plain: The plain-text password (used once for hashing; never logged).

    Raises:
        PasswordPolicyError: If the password violates any policy rule.

    Note on security: the caller (service layer) must ensure plain is never
    logged. This class stores it only transiently for the hash call.
    """

    __slots__ = ("plain",)

    def __init__(self, plain: str) -> None:
        """
        Args:
            plain: The raw password string from the sign-up request.

        Raises:
            PasswordPolicyError: too short, too long, missing letter, missing digit.
        """
        if len(plain) < PASSWORD_MIN_LENGTH:
            raise PasswordPolicyError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
            )
        if len(plain) > PASSWORD_MAX_LENGTH:
            raise PasswordPolicyError(
                f"Password must not exceed {PASSWORD_MAX_LENGTH} characters"
            )
        if not _RE_HAS_LETTER.search(plain):
            raise PasswordPolicyError("Password must contain at least one letter")
        if not _RE_HAS_DIGIT.search(plain):
            raise PasswordPolicyError("Password must contain at least one digit")
        self.plain: str = plain
