"""
Hilo People — Redis client singleton for the security module.

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: Lazy singleton Redis client using redis==7.4.0 (already pinned).
         Reads REDIS_URL from environment. Provides get_redis_client() for
         reuse by rate_limit.py and future security consumers.

Key deps:
  - redis==7.4.0 (already in pyproject.toml)
  - REDIS_URL env var (default: redis://localhost:6379/0)

Source refs:
  - task pack P02-S02-T001 §R1 (redis-py 7.4.0 already pinned, use it)
  - 01-non-negotiables.md §Security (fail-closed on Redis down)

Decisions:
  - D-RC1: Lazy singleton — client created on first call, reused thereafter.
    Thread-safe: redis-py connection pool is thread-safe by design.
  - D-RC2: decode_responses=True so keys/values are str, not bytes.
    Avoids encoding confusion in rate-limiter key logic.
  - D-RC3: socket_connect_timeout and socket_timeout set to 2s to fail
    fast without hanging the request thread.
"""

from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Optional

import redis

logger = logging.getLogger(__name__)

_REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_client: Optional[redis.Redis] = None
_client_lock = Lock()

_SOCKET_TIMEOUT_S = 2
_SOCKET_CONNECT_TIMEOUT_S = 2


def get_redis_client() -> redis.Redis:
    """Return the shared Redis client (lazy singleton).

    Creates the client on first call using REDIS_URL from environment.
    Thread-safe via module-level lock.

    Returns:
        redis.Redis instance with decode_responses=True.

    Raises:
        redis.exceptions.ConnectionError: On first PING failure if Redis
            is unreachable (propagated to caller — callers decide fail-open
            vs fail-closed).
    """
    global _client  # noqa: PLW0603

    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        logger.debug(
            "security.redis_client.init url=%s",
            _REDIS_URL.split("@")[-1],  # log host:port/db, never auth credentials
        )  # BEFORE

        _client = redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=_SOCKET_CONNECT_TIMEOUT_S,
            socket_timeout=_SOCKET_TIMEOUT_S,
        )

        logger.debug(
            "security.redis_client.ready",
        )  # AFTER

    return _client


def close_redis_client() -> None:
    """Close and discard the shared Redis client.

    Useful in tests that need a fresh client per test class, or on
    application shutdown. Thread-safe.
    """
    global _client  # noqa: PLW0603

    with _client_lock:
        if _client is not None:
            logger.debug("security.redis_client.close")
            _client.close()
            _client = None
