"""
Hilo People — In-memory token-bucket rate limiter for auth endpoints.

Slice:  P01-S02-T002 — POST /api/v1/auth/sign-in (extends T001 sign-up)
        P01-S02-T003 — POST /api/v1/auth/refresh (adds REFRESH bucket)
Phase:  P01 Auth + Data Foundation
Purpose: Per-IP token-bucket rate limiter for sign-up, sign-in, and refresh
         endpoints. Each endpoint has its own env-var-configurable bucket but
         shares the same in-memory bucket store and locking machinery.

         sign-up:   AUTH_SIGNUP_RATE_PER_MINUTE  (default 10)
         sign-in:   AUTH_SIGNIN_RATE_PER_MINUTE  (default 20)
         refresh:   AUTH_REFRESH_RATE_PER_MINUTE (default 30)

TODO(P02-S02-T001): Replace this in-memory token bucket with the platform
Redis-backed rate limiter (P02-S02-T001 owns rate-limit infra). This module
will be replaced; it is here to implement the security control NOW and
ensure it is configurable via env vars without code changes.

Key deps:
  - app.auth.errors.RateLimitExceededError, SignInRateLimitedError,
    RefreshRateLimitedError
  - threading — for thread-safe bucket state
  - time.monotonic — for testable wall-clock-independent timestamps

Source refs:
  - task pack §F.4 (sign-in rate limit: tighter than sign-up, own env vars)
  - task pack P01-S02-T003 §F.9 (refresh rate limit: own env vars)
  - 01-non-negotiables.md §Security (rate-limit public endpoints, especially auth)

Decisions:
  - D-RL1: _load_limits(prefix) helper extracts env vars so sign-up, sign-in and
    refresh each have their own limits but share the _store/_lock bucket machinery.
  - D-RL2: Window is hardcoded to 60 s (1 min) per endpoint; not an env var (YAGNI).
  - D-RL3: State is in-process dict — not shared across workers. Acceptable for V1.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple

from app.auth.errors import RateLimitExceededError, RefreshRateLimitedError, SignInRateLimitedError

logger = logging.getLogger(__name__)

_WINDOW_SECONDS: int = 60  # fixed 60-second window for all buckets


@dataclass
class _Bucket:
    """Internal state for one IP's token bucket.

    Attributes:
        tokens: Remaining attempts in the current window.
        window_start: monotonic timestamp when the current window started.
    """

    tokens: int
    window_start: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Global in-memory store + lock (replaced by Redis in P02-S02-T001)
# Store key: "<prefix>:<ip>" to keep sign-up, sign-in, refresh buckets separate.
# ---------------------------------------------------------------------------
_store: Dict[str, _Bucket] = {}
_lock = threading.Lock()


def _load_limits(prefix: str) -> Tuple[int, int]:
    """Load rate-limit configuration from environment for the given prefix.

    Reads AUTH_{PREFIX}_RATE_PER_MINUTE and AUTH_{PREFIX}_RATE_BURST env vars.
    BURST defaults to RATE_PER_MINUTE if not set.

    Args:
        prefix: Uppercase prefix (e.g. 'SIGNUP', 'SIGNIN', 'REFRESH').

    Returns:
        Tuple of (rate_per_minute, burst).
    """
    defaults = {
        "SIGNUP": ("10", None),
        "SIGNIN": ("20", None),
        "REFRESH": ("30", None),
        "FORGOT": ("3", None),   # tight: reset emails = potential harassment vector
        "RESET": ("10", None),   # DB + argon2 path
    }
    default_rate, _ = defaults.get(prefix, ("10", None))
    rate_per_minute = int(os.getenv(f"AUTH_{prefix}_RATE_PER_MINUTE", default_rate))
    burst = int(os.getenv(f"AUTH_{prefix}_RATE_BURST", str(rate_per_minute)))
    return rate_per_minute, burst


def _get_ip_key(prefix: str, ip: str) -> str:
    """Build a namespaced store key: '<prefix>:<ip>'.

    Args:
        prefix: Bucket namespace (e.g. 'SIGNUP', 'SIGNIN', 'REFRESH').
        ip: Raw IP string from request.

    Returns:
        Lower-cased namespaced key.
    """
    return f"{prefix}:{ip.strip().lower() if ip else 'unknown'}"


def _check_bucket(prefix: str, ip: str, rate_per_minute: int, burst: int) -> int:
    """Check and consume one token for the given prefix+IP bucket.

    If the bucket is empty, returns the retry-after seconds (negative) and
    the caller raises the correct typed error. Returns remaining token count
    if allowed.

    Args:
        prefix: Bucket namespace ('SIGNUP', 'SIGNIN', or 'REFRESH').
        ip: Client IP address.
        rate_per_minute: Max requests per minute window.
        burst: Initial bucket size (allows short burst above average).

    Returns:
        Remaining token count (>=0) if allowed, negative value (abs=retry_after)
        if rate limit exceeded.
    """
    if rate_per_minute == 0:
        logger.warning(
            "rate_limit.disabled prefix=%s AUTH_%s_RATE_PER_MINUTE=0 ip=%s",
            prefix,
            prefix,
            ip,
        )
        return 0

    key = _get_ip_key(prefix, ip)
    now = time.monotonic()

    logger.debug(
        "rate_limit.check.start prefix=%s ip=%s rate_per_min=%d burst=%d",
        prefix,
        key,
        rate_per_minute,
        burst,
    )  # BEFORE

    with _lock:
        bucket = _store.get(key)
        if bucket is None or (now - bucket.window_start) >= _WINDOW_SECONDS:
            _store[key] = _Bucket(tokens=burst - 1, window_start=now)
            logger.debug(
                "rate_limit.check.ok prefix=%s ip=%s new_window remaining=%d",
                prefix,
                key,
                burst - 1,
            )
            return burst - 1

        if bucket.tokens <= 0:
            elapsed = now - bucket.window_start
            retry_after = max(1, int(_WINDOW_SECONDS - elapsed) + 1)
            logger.warning(
                "rate_limit.check.exceeded prefix=%s ip=%s retry_after=%ds",
                prefix,
                key,
                retry_after,
            )  # AFTER — warning level (visible in non-verbose)
            return -(retry_after)  # negative = exceeded; abs = retry_after

        bucket.tokens -= 1
        logger.debug(
            "rate_limit.check.ok prefix=%s ip=%s remaining=%d",
            prefix,
            key,
            bucket.tokens,
        )  # AFTER
        return bucket.tokens


def check_rate_limit(ip: str) -> None:
    """Check and consume one sign-up token for the given IP.

    If the IP's bucket is empty, raises RateLimitExceededError with retry_after.
    Rate is configured via AUTH_SIGNUP_RATE_PER_MINUTE (default 10) and
    AUTH_SIGNUP_RATE_BURST env vars.

    Args:
        ip: Client IP address.

    Raises:
        RateLimitExceededError: Rate limit exceeded; includes retry_after seconds.
    """
    rate_per_minute, burst = _load_limits("SIGNUP")
    result = _check_bucket("SIGNUP", ip, rate_per_minute, burst)
    if result < 0:
        raise RateLimitExceededError(retry_after=abs(result))


def check_rate_limit_signin(ip: str) -> None:
    """Check and consume one sign-in token for the given IP.

    If the IP's bucket is empty, raises SignInRateLimitedError with retry_after.
    Rate is configured via AUTH_SIGNIN_RATE_PER_MINUTE (default 20) and
    AUTH_SIGNIN_RATE_BURST env vars. Sign-in has a tighter per-minute cap than
    sign-up to limit credential-stuffing velocity.

    Args:
        ip: Client IP address.

    Raises:
        SignInRateLimitedError: Rate limit exceeded; includes retry_after seconds.
    """
    rate_per_minute, burst = _load_limits("SIGNIN")
    result = _check_bucket("SIGNIN", ip, rate_per_minute, burst)
    if result < 0:
        raise SignInRateLimitedError(retry_after=abs(result))


def check_rate_limit_refresh(ip: str) -> None:
    """Check and consume one refresh token for the given IP.

    If the IP's bucket is empty, raises RefreshRateLimitedError with retry_after.
    Rate is configured via AUTH_REFRESH_RATE_PER_MINUTE (default 30) and
    AUTH_REFRESH_RATE_BURST env vars. Refresh is normal traffic (authStore calls
    it on every 401); the cap exists to block cookie-theft replay storms.

    Args:
        ip: Client IP address.

    Raises:
        RefreshRateLimitedError: Rate limit exceeded; includes retry_after seconds.
    """
    rate_per_minute, burst = _load_limits("REFRESH")
    result = _check_bucket("REFRESH", ip, rate_per_minute, burst)
    if result < 0:
        raise RefreshRateLimitedError(retry_after=abs(result))

def check_rate_limit_forgot(ip: str) -> None:
    """Check and consume one forgot-password token for the given IP.

    Rate is configured via AUTH_FORGOT_RATE_PER_MINUTE (default 3) — tight
    because password-reset emails are a potential account-harassment vector.

    Args:
        ip: Client IP address.

    Raises:
        ForgotPasswordRateLimitedError: Rate limit exceeded.
    """
    from app.auth.errors import ForgotPasswordRateLimitedError  # noqa: PLC0415

    rate_per_minute, burst = _load_limits("FORGOT")
    result = _check_bucket("FORGOT", ip, rate_per_minute, burst)
    if result < 0:
        raise ForgotPasswordRateLimitedError(retry_after=abs(result))


def check_rate_limit_reset(ip: str) -> None:
    """Check and consume one reset-password token for the given IP.

    Rate is configured via AUTH_RESET_RATE_PER_MINUTE (default 10).
    Higher than forgot because reset attempts hit DB + argon2 (expensive path).

    Args:
        ip: Client IP address.

    Raises:
        ResetPasswordRateLimitedError: Rate limit exceeded.
    """
    from app.auth.errors import ResetPasswordRateLimitedError  # noqa: PLC0415

    rate_per_minute, burst = _load_limits("RESET")
    result = _check_bucket("RESET", ip, rate_per_minute, burst)
    if result < 0:
        raise ResetPasswordRateLimitedError(retry_after=abs(result))
