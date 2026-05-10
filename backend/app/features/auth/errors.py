"""
Typed domain errors for the auth feature.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up
Phase: P01 — Auth + Base Capabilities

These errors are raised in service.py and caught in routes.py for HTTP mapping.
Using typed exceptions (not generic Exception) per 01-non-negotiables.md §Error handling.

Error → HTTP status mapping (see routes.py):
  EmailAlreadyExistsError     → 409 Conflict   (AUTH_EMAIL_TAKEN)
  WeakPasswordError           → 422             (AUTH_WEAK_PASSWORD)
  NonCorporateEmailError      → 422             (AUTH_NON_CORPORATE_EMAIL)
  LegalAcceptanceMissingError → 422             (AUTH_LEGAL_ACCEPTANCE_REQUIRED)

Dependencies: none (pure domain errors — no external imports).
"""
from __future__ import annotations


class AuthDomainError(Exception):
    """Base class for auth feature domain errors.

    Purpose: group all auth errors under one base so callers can catch broadly.
    Params: message — human-readable description (internal use only; never sent raw to client).
    """

    def __init__(self, message: str) -> None:
        """Initialize with an internal message."""
        super().__init__(message)
        self.message = message


class EmailAlreadyExistsError(AuthDomainError):
    """Raised when the email is already registered in the users table.

    Purpose: signals a 409 Conflict — the response message must be NON-LEAKY
    (must not reveal that the user exists; see instrucciones §3.2 + task-pack §4.7).

    Business rule: repository catches the UNIQUE constraint IntegrityError and
    re-raises this error. The service layer never does a SELECT-before-INSERT
    (TOCTOU risk; rely on the DB constraint as the atomic gate).
    """

    def __init__(self, email_masked: str) -> None:
        """Initialize with masked email for internal logging only.

        Params:
          email_masked — masked email (e.g. 's.l***@gmail.com'); NEVER the raw address.
        """
        super().__init__(f"Email already registered: {email_masked}")
        self.email_masked = email_masked


class WeakPasswordError(AuthDomainError):
    """Raised when the password does not meet the strength policy.

    Policy (task-pack §6.4):
      - Minimum 12 characters.
      - At least one uppercase letter, one lowercase letter, one digit, one symbol.
    Error code: AUTH_WEAK_PASSWORD
    """

    def __init__(self, reason: str = "does not meet strength requirements") -> None:
        """Initialize with an internal reason string."""
        super().__init__(f"Password {reason}")
        self.reason = reason


class NonCorporateEmailError(AuthDomainError):
    """Raised when the email domain is not in the CORPORATE_EMAIL_DOMAINS allowlist.

    Only raised when the allowlist is non-empty (empty = permissive dev mode).
    Error code: AUTH_NON_CORPORATE_EMAIL

    Params:
      domain — the domain that was rejected (e.g. 'gmail.com').
    """

    def __init__(self, domain: str) -> None:
        """Initialize with the rejected domain."""
        super().__init__(f"Email domain not in corporate allowlist: {domain}")
        self.domain = domain


class LegalAcceptanceMissingError(AuthDomainError):
    """Raised when legal_acceptance is False or missing.

    Error code: AUTH_LEGAL_ACCEPTANCE_REQUIRED
    Source: instrucciones.md §3.2 'aceptación legal en sign-up'
    """

    def __init__(self) -> None:
        """Initialize with a fixed message."""
        super().__init__("Legal acceptance must be True to complete sign-up")
