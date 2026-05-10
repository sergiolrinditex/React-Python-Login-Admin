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


class InvalidCredentialsError(AuthDomainError):
    """Raised when re-auth credentials are invalid (user not found OR wrong password).

    Purpose: intentionally generic — callers MUST return the same HTTP 401
    response for both cases (email not found and password mismatch) to prevent
    user-enumeration attacks.

    Slice: P01-S02-T009 — POST /api/v1/auth/2fa/enroll (re-auth scheme D1)
    Error code: AUTH_INVALID_CREDENTIALS
    Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.4 + task-pack §5.3
    """

    def __init__(self, reason: str = "email not found or password incorrect") -> None:
        """Initialize with an internal reason (NOT exposed to callers/HTTP responses).

        Params:
          reason — internal description; NEVER sent to the client to prevent enumeration.
        """
        super().__init__(f"Re-auth failed: {reason}")
        self.reason = reason


class AlreadyEnrolledError(AuthDomainError):
    """Raised when a user already has a row in mfa_totp_secrets AND the policy is 'reject'.

    Slice: P01-S02-T009 — POST /api/v1/auth/2fa/enroll
    Error code: AUTH_2FA_ALREADY_ENROLLED (409)

    Note: The default policy (D2) is 'rotate' (silently update the secret + audit_log),
    NOT 'reject'. This error is raised only if the caller selects policy='reject'.
    T009 does NOT select 'reject' — it uses the rotate policy. This class is kept
    for completeness and for future T008/config-driven policy switch.
    Source: task-pack §5.3 + §9 D2
    """

    def __init__(self, user_id: str) -> None:
        """Initialize with masked user_id for internal logging.

        Params:
          user_id — UUID string of the already-enrolled user.
        """
        super().__init__(f"User {user_id} already has MFA enrolled")
        self.user_id = user_id
