"""
Hilo People — Auth typed domain errors and HTTP code mapping.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Defines typed AuthError subclasses for every auth failure mode and
         the mapping from domain error to HTTP status code + envelope error code.
         Keeps error logic in the domain layer, away from FastAPI.

Key deps:
  - None (pure Python — domain layer must not import FastAPI)

Source refs:
  - TECHNICAL_GUIDE §6.4 auth error codes
  - TECHNICAL_GUIDE §6.2 HTTP status pin (201/400/409/422/429)
  - task pack §C.3 AUTH_SIGNUP_* error codes
  - 01-non-negotiables.md §Error handling (typed domain errors, no generic catch)
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Base auth domain error
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Base class for all authentication domain errors.

    Subclasses carry a stable machine-readable code that the presentation
    layer maps to HTTP status + envelope shape. Never use this base directly.
    """

    #: Machine-readable code returned in errors[].code in the API envelope.
    code: str = "AUTH_ERROR"
    #: Default HTTP status (overridable per subclass).
    http_status: int = 400


# ---------------------------------------------------------------------------
# Sign-up specific errors
# ---------------------------------------------------------------------------

class NonCorporateEmailError(AuthError):
    """Email domain is not in the allowed corporate domain whitelist.

    Returned when the email syntax is valid but the domain (part after @)
    is not in the CORPORATE_EMAIL_DOMAINS environment variable list.

    HTTP: 400  Code: AUTH_SIGNUP_NON_CORPORATE_EMAIL
    Field: email (surfaced by presentation layer for frontend highlighting)
    """

    code = "AUTH_SIGNUP_NON_CORPORATE_EMAIL"
    http_status = 400

    def __init__(self, domain: str) -> None:
        """
        Args:
            domain: The rejected domain string (e.g. 'gmail.com').
                    Never includes the local-part — no PII in error message.
        """
        super().__init__(f"Email domain not in corporate allowlist: {domain}")
        self.domain = domain


class LegalNotAcceptedError(AuthError):
    """legal_acceptance field is missing or False in the sign-up payload.

    HTTP: 400  Code: AUTH_SIGNUP_LEGAL_NOT_ACCEPTED
    Field: legal_acceptance
    """

    code = "AUTH_SIGNUP_LEGAL_NOT_ACCEPTED"
    http_status = 400

    def __init__(self) -> None:
        super().__init__("Legal acceptance is required to complete registration")


class EmailAlreadyExistsError(AuthError):
    """An account with that email already exists (or cannot be created).

    Generic 409 — never reveals whether the email is taken vs policy-blocked
    to prevent user enumeration. Ref: TECHNICAL_GUIDE §6.4, non-negotiables §Security.

    HTTP: 409  Code: AUTH_SIGNUP_EMAIL_TAKEN
    """

    code = "AUTH_SIGNUP_EMAIL_TAKEN"
    http_status = 409

    def __init__(self) -> None:
        super().__init__("An account with that email exists or cannot be created")


class PasswordPolicyError(AuthError):
    """Password does not meet the minimum policy requirements.

    Policy: min 12 chars, max 256 chars, at least 1 letter + 1 digit.
    Raised by the Password value object before persistence.

    HTTP: 422 (folded into Pydantic 422 at presentation layer)
    Code: AUTH_SIGNUP_INVALID_PAYLOAD  Field: password
    """

    code = "AUTH_SIGNUP_INVALID_PAYLOAD"
    http_status = 422

    def __init__(self, reason: str) -> None:
        super().__init__(f"Password policy violation: {reason}")
        self.reason = reason


class RateLimitExceededError(AuthError):
    """Too many sign-up attempts from this IP within the rate-limit window.

    HTTP: 429  Code: AUTH_SIGNUP_RATE_LIMITED
    """

    code = "AUTH_SIGNUP_RATE_LIMITED"
    http_status = 429

    def __init__(self, retry_after: int) -> None:
        """
        Args:
            retry_after: Seconds until the rate-limit window resets.
        """
        super().__init__(f"Rate limit exceeded; retry after {retry_after}s")
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Sign-in specific errors (added P01-S02-T002)
# ---------------------------------------------------------------------------

class InvalidCredentialsError(AuthError):
    """Email or password is incorrect.

    Returned for BOTH unknown email AND wrong password (aggregate-401) to
    prevent user enumeration. The HTTP response body is byte-for-byte identical
    for both failure reasons; only the audit_log.metadata.reason differs.

    HTTP: 401  Code: AUTH_INVALID_CREDENTIALS
    Ref: TECHNICAL_GUIDE §6.4, task pack §F.1
    """

    code = "AUTH_INVALID_CREDENTIALS"
    http_status = 401

    def __init__(self) -> None:
        super().__init__("Email or password is incorrect")


class AccountLockedError(AuthError):
    """Account is temporarily locked after repeated failed sign-in attempts.

    Triggered when the recent failure count for a user_id exceeds the
    AUTH_SIGNIN_LOCKOUT_THRESHOLD within the AUTH_SIGNIN_LOCKOUT_WINDOW_SECONDS
    rolling window. See task pack §F.3 for policy details.

    HTTP: 423  Code: AUTH_ACCOUNT_LOCKED
    Ref: TECHNICAL_GUIDE §6.2 (423 listed in error column), task pack §F.3
    """

    code = "AUTH_ACCOUNT_LOCKED"
    http_status = 423

    def __init__(self) -> None:
        super().__init__("Account temporarily locked due to repeated failed sign-in attempts")


class SignInRateLimitedError(AuthError):
    """Too many sign-in attempts from this IP within the rate-limit window.

    HTTP: 429  Code: AUTH_SIGNIN_RATE_LIMITED
    Ref: task pack §F.4
    """

    code = "AUTH_SIGNIN_RATE_LIMITED"
    http_status = 429

    def __init__(self, retry_after: int) -> None:
        """
        Args:
            retry_after: Seconds until the rate-limit window resets.
        """
        super().__init__(f"Too many sign-in attempts; retry after {retry_after}s")
        self.retry_after = retry_after


class InvalidPayloadError(AuthError):
    """Sign-in request has empty or missing required field.

    Raised by the SignIn use case (not Pydantic) when the validated payload
    contains an empty email or empty password — policy that requires audit rows
    and the project envelope shape (400, not Pydantic's 422).

    HTTP: 400  Code: AUTH_INVALID_PAYLOAD
    Field: email | password
    Ref: task pack §E.4 empty-email/empty-password row
    """

    code = "AUTH_INVALID_PAYLOAD"
    http_status = 400

    def __init__(self, field: str, reason: str = "Field must not be empty") -> None:
        """
        Args:
            field: Which field is invalid ('email' or 'password').
            reason: Human-readable reason (not PII).
        """
        super().__init__(f"{field}: {reason}")
        self.field = field
