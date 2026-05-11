"""
Hilo People — In-memory token-bucket rate limiter for sign-up endpoint.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Per-IP token-bucket rate limiter for the sign-up endpoint.
         Default: 10 attempts per 60 seconds per IP (configurable via env).
         Returns RateLimitExceededError when the bucket is empty.

TODO(P02-S02-T001): Replace this in-memory token bucket with the platform
Redis-backed rate limiter (P02-S02-T001 owns rate-limit infra). This module
will be replaced; it is here to implement the security control NOW and
ensure it is configurable via env vars without code changes.

Key deps:
  - app.auth.errors.RateLimitExceededError
  - threading — for thread-safe bucket state
  - time.monotonic — for testable wall-clock-independent timestamps

Source refs:
  - task pack §F.4 (rate limit: active now, configurable, in-memory for V1)
  - 01-non-negotiables.md §Security (rate-limit public endpoints, especially auth)

Decisions:
  - AUTH_SIGNUP_RATE_PER_MINUTE env var (int, default 10). 0 = disabled (not
    recommended; documented here for explicit override).
  - AUTH_SIGNUP_RATE_BURST env var (int, default = rate_per_minute). Allows
    a short burst above the per-minute rate before throttling.
  - State is in-process dict — not shared across workers. Acceptable for V1
    single-instance; P02-S02-T001 replaces with Redis.
  - window_seconds is hardcoded to 60 (1 min window); not an env var (YAGNI).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict

from app.auth.errors import RateLimitExceededError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
_RATE_PER_MINUTE: int = int(os.getenv("AUTH_SIGNUP_RATE_PER_MINUTE", "10"))
_BURST: int = int(os.getenv("AUTH_SIGNUP_RATE_BURST", str(_RATE_PER_MINUTE)))
_WINDOW_SECONDS: int = 60  # fixed 60-second window


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
# ---------------------------------------------------------------------------
_store: Dict[str, _Bucket] = {}
_lock = threading.Lock()


def _get_ip_key(ip: str) -> str:
    """Normalise IP key for store lookup.

    Args:
        ip: Raw IP string from request (may be IPv6 or empty).

    Returns:
        Lower-cased trimmed IP string.
    """
    return ip.strip().lower() if ip else "unknown"


def check_rate_limit(ip: str) -> None:
    """Check and consume one token for the given IP.

    If the IP's bucket is empty (all tokens consumed within the current 60-second
    window), raises RateLimitExceededError with retry_after seconds.

    If rate limiting is disabled (AUTH_SIGNUP_RATE_PER_MINUTE=0), returns
    immediately. Disabled state is NOT recommended in production.

    Args:
        ip: Client IP address (from X-Forwarded-For or request.client.host).

    Raises:
        RateLimitExceededError: Rate limit exceeded; includes retry_after seconds.

    Side effect:
        Decrements the IP's token count by 1.
    """
    if _RATE_PER_MINUTE == 0:
        logger.warning(
            "rate_limit.disabled AUTH_SIGNUP_RATE_PER_MINUTE=0 ip=%s",
            _get_ip_key(ip),
        )
        return

    key = _get_ip_key(ip)
    now = time.monotonic()

    logger.debug(
        "rate_limit.check.start ip=%s rate_per_min=%d burst=%d",
        key,
        _RATE_PER_MINUTE,
        _BURST,
    )  # BEFORE

    with _lock:
        bucket = _store.get(key)
        if bucket is None or (now - bucket.window_start) >= _WINDOW_SECONDS:
            # New window — full bucket
            _store[key] = _Bucket(tokens=_BURST - 1, window_start=now)
            logger.debug("rate_limit.check.ok ip=%s new_window remaining=%d", key, _BURST - 1)
            return

        if bucket.tokens <= 0:
            elapsed = now - bucket.window_start
            retry_after = max(1, int(_WINDOW_SECONDS - elapsed) + 1)
            logger.warning(
                "rate_limit.check.exceeded ip=%s retry_after=%ds",
                key,
                retry_after,
            )  # AFTER — warning level (visible in non-verbose)
            raise RateLimitExceededError(retry_after=retry_after)

        bucket.tokens -= 1
        logger.debug(
            "rate_limit.check.ok ip=%s remaining=%d",
            key,
            bucket.tokens,
        )  # AFTER
