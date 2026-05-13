"""
Hilo People — Redis sliding-window rate limiter dependency.

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: Provides RateLimiter(prefix, per_minute, burst, window_seconds) — a
         callable that FastAPI uses as Depends(RateLimiter(...)). Uses Redis
         INCR + conditional EXPIRE for atomic sliding-window counting.

         Co-exists with backend/app/auth/rate_limit.py (in-process token bucket
         for auth endpoints). Future auth endpoint slices will migrate per-endpoint
         to this Redis-backed pattern (R3 in task pack).

Key deps:
  - redis==7.4.0 (already pinned in pyproject.toml)
  - app.security._redis_client.get_redis_client — lazy singleton
  - app.security.errors.RateLimitedError

Source refs:
  - task pack P02-S02-T001 §R1 (custom Redis sliding-window, no external lib)
  - Redis "Rate limiting pattern" docs (INCR + conditional EXPIRE)
  - 01-non-negotiables.md §Security (rate-limit public endpoints)

Decisions:
  - D-RL1: INCR is atomic on Redis; conditional EXPIRE only fires when the
    counter is 1 (first hit in window). Race-safe: two concurrent requests
    both INCR, one gets count=1 and fires EXPIRE, the other gets count=2
    and skips EXPIRE — window is still correctly established.
  - D-RL2: Fail-closed on Redis error: returns 503 Service Unavailable.
    Fail-open would expose an abuse vector (burst through all limits when
    Redis goes down). 503 is honest and safe.
  - D-RL3: IP extracted from X-Forwarded-For (first hop) or request.client.host.
    Same helper used by auth rate limiter for consistency.
  - D-RL4: Key format: "{prefix}:{ip}:{window_bucket}" where window_bucket is
    int(time.time() / window_seconds). This creates fixed-length time windows,
    not a true sliding window, but is sufficient for V1 and matches Redis
    rate-limiting documentation.
  - D-RL5: window_seconds parameter on the constructor allows test-fast windows
    (e.g., 2 seconds) without monkey-patching env vars. Production always uses
    default of 60.
  - D-RL6: ENABLE_VERBOSE_LOGGING controls debug vs warning. Exceeded events
    are WARNING so they appear in non-verbose production logs.
"""

from __future__ import annotations

import logging
import os
import time

import redis as redis_lib
from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.routers._helpers import _error_response, _get_request_id
from app.security._redis_client import get_redis_client

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def _get_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or direct connection.

    Args:
        request: FastAPI Request.

    Returns:
        IP string (never empty — falls back to 'unknown').
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.client.host if request.client else "") or "unknown"


class RateLimiter:
    """Redis-backed sliding-window rate limiter for FastAPI Depends.

    Usage::

        rate_limiter = RateLimiter(prefix="ADMIN_AI", per_minute=60, burst=10)

        @router.post("/admin/ai-providers")
        async def create_provider(
            _rl: None = Depends(rate_limiter),
            ...
        ):
            ...

    Returns 429 JSONResponse with Retry-After header when bucket is exhausted.
    Returns 503 JSONResponse if Redis is unavailable (fail-closed per D-RL2).
    Returns None on success (caller proceeds normally).
    """

    def __init__(
        self,
        prefix: str,
        per_minute: int,
        burst: int,
        window_seconds: int = 60,
    ) -> None:
        """Initialize the rate limiter configuration.

        Args:
            prefix:         Bucket namespace (e.g. 'ADMIN_AI', 'MCP'). Used as
                            part of the Redis key, combined with client IP.
            per_minute:     Max requests allowed per window.
            burst:          Same as per_minute for this implementation
                            (burst is the initial allowance per window).
            window_seconds: Window length in seconds. Default 60 (1 minute).
                            Use smaller values in tests (e.g., 2).
        """
        self.prefix = prefix
        self.per_minute = per_minute
        self.burst = burst
        self.window_seconds = window_seconds

    def _make_key(self, ip: str) -> str:
        """Build the Redis key for this IP + current time window.

        Key format: "{prefix}:{ip}:{window_bucket}"
        window_bucket = int(time.time() / window_seconds)

        Args:
            ip: Client IP address.

        Returns:
            Redis key string.
        """
        bucket = int(time.time() / self.window_seconds)
        return f"{self.prefix}:{ip}:{bucket}"

    async def __call__(self, request: Request) -> JSONResponse | None:
        """FastAPI dependency: check and consume one request from the bucket.

        Emits DEBUG logs before/after when ENABLE_VERBOSE_LOGGING=true.
        Emits WARNING log on exceeded (always visible).

        Args:
            request: FastAPI Request (for IP extraction and request_id).

        Returns:
            None on success (caller proceeds).
            JSONResponse 429 when rate limit exceeded.
            JSONResponse 503 when Redis is unavailable (fail-closed).
        """
        ip = _get_ip(request)
        request_id = _get_request_id(request)
        key = self._make_key(ip)

        if _VERBOSE:
            logger.debug(
                "security.rate_limit.check.start prefix=%s ip=%s "
                "per_minute=%d window=%ds request_id=%s",
                self.prefix,
                ip,
                self.per_minute,
                self.window_seconds,
                request_id,
            )  # BEFORE

        try:
            client = get_redis_client()

            # Atomic INCR — returns new count after increment.
            count = client.incr(key)

            # D-RL1: Only set EXPIRE on the first hit (count == 1).
            # This is race-safe: the INCR is atomic; if two concurrent
            # requests both get count==1 (impossible in Redis since INCR
            # is sequential), only one EXPIRE fires — the window is still set.
            if count == 1:
                client.expire(key, self.window_seconds)

        except redis_lib.exceptions.RedisError as exc:
            logger.error(
                "security.rate_limit.redis_error prefix=%s ip=%s error=%s request_id=%s",
                self.prefix,
                ip,
                type(exc).__name__,
                request_id,
            )
            # D-RL2: Fail-closed — Redis unavailable → 503.
            return _error_response(
                request_id=request_id,
                code="SERVICE_UNAVAILABLE",
                message="Rate limiting service is temporarily unavailable.",
                http_status=503,
            )

        if count > self.burst:
            # Calculate retry_after as the remaining TTL on the key.
            try:
                ttl = get_redis_client().ttl(key)
                retry_after = max(1, ttl) if ttl > 0 else self.window_seconds
            except redis_lib.exceptions.RedisError:
                retry_after = self.window_seconds

            logger.warning(
                "security.rate_limit.exceeded prefix=%s ip=%s count=%d "
                "burst=%d retry_after=%ds request_id=%s",
                self.prefix,
                ip,
                count,
                self.burst,
                retry_after,
                request_id,
            )  # AFTER — warning level (always visible)

            return _error_response(
                request_id=request_id,
                code="RATE_LIMITED",
                message=f"Too many requests. Retry after {retry_after} seconds.",
                http_status=429,
                headers={"Retry-After": str(retry_after)},
            )

        if _VERBOSE:
            logger.debug(
                "security.rate_limit.check.ok prefix=%s ip=%s count=%d "
                "remaining=%d request_id=%s",
                self.prefix,
                ip,
                count,
                max(0, self.burst - count),
                request_id,
            )  # AFTER

        return None
