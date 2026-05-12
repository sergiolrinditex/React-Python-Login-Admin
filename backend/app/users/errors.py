"""
Hilo People — Domain errors for the users feature.

Slice:  P01-S02-T007 — GET /api/v1/users/me + PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: Typed domain errors raised by the users service layer and caught by
         the users router to produce standardised HTTP error responses.
         These errors carry no PII — only codes and reason strings.

Dependencies:
  - none (pure Python, no external imports)

Source refs:
  - task pack §I (errors.py entry in expected file list)
  - TECHNICAL_GUIDE §6.2 rows 262/263 (error codes: AUTH_SESSION_EXPIRED, AUTH_INVALID_PAYLOAD)
  - 01-non-negotiables.md §Error handling (typed domain errors, not generic Exception)
"""

from __future__ import annotations


class UserNotFoundError(Exception):
    """Raised by repository when the user identified by token sub does not exist.

    The router catches this and emits AUTH_SESSION_EXPIRED (anti-enum, G.3).
    """

    def __init__(self, user_id: str) -> None:
        """Initialise with the lookup user_id (UUID string — not PII).

        Args:
            user_id: String form of the user UUID that was not found.
        """
        super().__init__(f"User not found: {user_id}")
        self.user_id = user_id


class UserInactiveError(Exception):
    """Raised by service when the user's status is not 'active'.

    The router catches this and emits AUTH_SESSION_EXPIRED (anti-enum, G.3).
    """

    def __init__(self, user_id: str, status: str) -> None:
        """Initialise with user_id and current status.

        Args:
            user_id: String form of the user UUID.
            status: Current status value (e.g. 'inactive', 'locked').
        """
        super().__init__(f"User {user_id} is not active (status={status})")
        self.user_id = user_id
        self.status = status


class PurposeMismatchError(Exception):
    """Raised when a token carries a 'purpose' claim (e.g. mfa_challenge).

    Access tokens MUST NOT carry a 'purpose' claim. This prevents an MFA
    challenge token from being replayed as an access token (G.2 defensive check).
    """


class LanguageInvalidError(Exception):
    """Raised by service when the requested language is not in {es, en, fr}.

    Should not normally reach the service layer (Pydantic validates first),
    but exists as a defence-in-depth safeguard.

    The router catches this and emits AUTH_INVALID_PAYLOAD with field='language'.
    """

    def __init__(self, value: str) -> None:
        """Initialise with the invalid language value.

        Args:
            value: The language code that was rejected.
        """
        super().__init__(f"Invalid language: {value!r}")
        self.value = value


class MissingBearerError(Exception):
    """Raised when no Authorization: Bearer header is present in the request.

    The router catches this and emits AUTH_SESSION_EXPIRED (anti-enum, G.3).
    """
