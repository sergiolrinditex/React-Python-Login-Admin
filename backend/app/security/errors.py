"""
Hilo People — Typed domain errors for the security module.

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: Defines the typed exception hierarchy for app.security. These are
         domain errors — they do NOT import FastAPI. Callers (permissions.py,
         rate_limit.py) may wrap them into HTTP responses, but the errors
         themselves are stack-agnostic.

Key deps:  None (pure Python).

Source refs:
  - task pack P02-S02-T001 §D-S2-T001-D1
  - 01-non-negotiables.md §Error handling (typed domain errors, no generic catch)

Decisions:
  - D-E1: All security errors inherit from SecurityError so callers can
    catch the base class when needed.
  - D-E2: No FastAPI import here — Clean Architecture; HTTP mapping
    happens in permissions.py and rate_limit.py.
"""

from __future__ import annotations


class SecurityError(Exception):
    """Base class for all security module domain errors."""


class EncryptionKeyError(SecurityError):
    """Raised when ENCRYPTION_KEY is missing, placeholder, or invalid.

    Attributes:
        message: Human-readable description including the repair command.
    """

    def __init__(self, message: str) -> None:
        """Initialize with a descriptive message including the repair command.

        Args:
            message: Explanation of why the key is invalid, with repair hint.
        """
        super().__init__(message)
        self.message = message


class EncryptionError(SecurityError):
    """Raised when encryption or decryption fails at runtime.

    Wraps cryptography.fernet.InvalidToken and similar low-level errors
    into a typed domain error.

    Attributes:
        message: Human-readable reason for the failure.
        cause:   Original exception, if available.
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        """Initialize with message and optional root cause.

        Args:
            message: Description of the failure.
            cause:   Original exception for stack-trace context.
        """
        super().__init__(message)
        self.message = message
        self.cause = cause


class PermissionDeniedError(SecurityError):
    """Raised when an authenticated user lacks a required role.

    Represents a 403 Forbidden scenario: user is authenticated but does
    not hold the required role.

    Attributes:
        role_required: Name of the role that was checked and found missing.
        request_id:    Request correlation ID for log tracing.
    """

    def __init__(self, role_required: str, request_id: str = "") -> None:
        """Initialize with the role that was required but missing.

        Args:
            role_required: Role name the guard expected (e.g. 'people_admin').
            request_id:    X-Request-ID for correlation (optional).
        """
        super().__init__(
            f"Role '{role_required}' required but not present for this user."
        )
        self.role_required = role_required
        self.request_id = request_id


class RateLimitedError(SecurityError):
    """Raised when a Redis-backed rate limiter bucket is exhausted.

    Carries retry_after seconds so callers can emit Retry-After HTTP header.

    Attributes:
        prefix:      Rate-limiter bucket prefix (e.g. 'ADMIN_AI').
        retry_after: Seconds to wait before the next allowed request.
        request_id:  Request correlation ID for log tracing.
    """

    def __init__(
        self,
        prefix: str,
        retry_after: int,
        request_id: str = "",
    ) -> None:
        """Initialize with bucket prefix and retry delay.

        Args:
            prefix:      Rate-limiter bucket namespace.
            retry_after: Seconds until the window resets.
            request_id:  X-Request-ID for correlation (optional).
        """
        super().__init__(
            f"Rate limit exceeded for '{prefix}'. Retry after {retry_after}s."
        )
        self.prefix = prefix
        self.retry_after = retry_after
        self.request_id = request_id
