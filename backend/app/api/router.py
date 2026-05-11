"""
Health probes router — platform observability endpoints.

Slice:  P00-S02-T002 — Health live ready endpoints
Phase:  P00 Scaffold + Design System
Purpose: Provides three root-level health endpoints consumed by load balancers
         and K8s liveness/readiness probes:
         - GET /health  (backward-compat stub from T001)
         - GET /live    (liveness probe — always 200 while process is up)
         - GET /ready   (readiness probe — pings DB + Redis; 503 if degraded)

Key deps:
  - fastapi: APIRouter, Depends, status.HTTP_503_SERVICE_UNAVAILABLE
  - sqlalchemy 2.0: create_engine, text, exc.OperationalError (sync engine)
  - redis 7.4.0: Redis.from_url, exceptions.ConnectionError/TimeoutError
  - psycopg[binary] 3.3.3: SQLAlchemy dialect postgresql+psycopg://

Source refs:
  - TECHNICAL_GUIDE §6.2 health endpoints contract.
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR, ENABLE_VERBOSE_LOGGING).
  - official-doc-notes: P00-S02-T002-sqlalchemy-sync-ping (RESOLVED),
                        P00-S02-T002-redis-ping (RESOLVED),
                        P00-S02-T002-fastapi-healthcheck (RESOLVED).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import redis as redis_module
import redis.exceptions as redis_exc
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy import exc as sa_exc
from sqlalchemy.engine import Engine

# ---------------------------------------------------------------------------
# Logger — level driven by ENABLE_VERBOSE_LOGGING per 01-non-negotiables.md.
# The level is read once at module import; tests that need to observe the
# level use caplog/monkeypatch on the logger directly.
# ---------------------------------------------------------------------------
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
_LOG_LEVEL: int = logging.INFO if _VERBOSE else logging.WARNING
logger = logging.getLogger(__name__)
logger.setLevel(_LOG_LEVEL)

# ---------------------------------------------------------------------------
# Process-start timestamp for /health uptime field (same as main.py reference)
# ---------------------------------------------------------------------------
_START_TIME: float = time.monotonic()

# ---------------------------------------------------------------------------
# Module-level singletons — created lazily on first request.
# SQLAlchemy engine with pool_pre_ping avoids stale-connection false negatives.
# redis.Redis with short socket timeouts avoids hanging probes.
# Source: official-doc-notes P00-S02-T002-sqlalchemy-sync-ping RESOLVED,
#         P00-S02-T002-redis-ping RESOLVED.
# ---------------------------------------------------------------------------
_engine_singleton: Engine | None = None
_redis_singleton: redis_module.Redis | None = None  # type: ignore[type-arg]


def get_db_engine() -> Engine:
    """
    FastAPI dependency: return (or lazily create) the SQLAlchemy sync engine.

    Uses module-level singleton so every request reuses the same connection
    pool. pool_pre_ping=True ensures stale connections are discarded on
    checkout (SQLAlchemy 2.0 official pattern).

    Returns:
        Engine: SQLAlchemy sync Engine pointed at DATABASE_URL.

    Source: TECHNICAL_GUIDE §6.2; SQLAlchemy 2.0 pooling guide.
    """
    global _engine_singleton
    if _engine_singleton is None:
        db_url = os.getenv("DATABASE_URL", "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev")
        # Ensure psycopg3 dialect prefix — replace legacy postgres:// shorthand.
        if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine_singleton = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=2,
        )
    return _engine_singleton


def get_redis_client() -> redis_module.Redis:  # type: ignore[type-arg]
    """
    FastAPI dependency: return (or lazily create) the redis.Redis client.

    socket_timeout and socket_connect_timeout are set to 2s so that a
    slow/unreachable Redis fails fast instead of hanging the probe.

    Returns:
        redis.Redis: configured sync client.

    Source: TECHNICAL_GUIDE §6.2; redis-py from_url docs.
    """
    global _redis_singleton
    if _redis_singleton is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_singleton = redis_module.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
    return _redis_singleton


# ---------------------------------------------------------------------------
# Internal ping helpers — keep handlers ≤ 50 lines.
# ---------------------------------------------------------------------------

def _ping_db(engine: Engine) -> dict[str, Any]:
    """
    Attempt SELECT 1 via the provided SQLAlchemy engine.

    Returns:
        dict: {"status": "ok"} on success;
              {"status": "error", "error": <truncated message>} on failure.
    """
    logger.info("health.ready.db.ping.start engine=%s", type(engine).__name__)  # BEFORE
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("health.ready.db.ping.ok")  # AFTER
        return {"status": "ok"}
    except sa_exc.OperationalError as exc:
        msg = str(exc)[:120]
        logger.warning("health.ready.db.ping.error error=%s", msg)  # ERROR
        return {"status": "error", "error": msg}


def _ping_redis(client: redis_module.Redis) -> dict[str, Any]:  # type: ignore[type-arg]
    """
    Attempt PING via the provided redis.Redis client.

    Catches both ConnectionError (refused) and TimeoutError (timeout exceeded)
    per redis-py official exception hierarchy. Both result in "error" state.
    Source: official-doc-notes P00-S02-T002-redis-ping RESOLVED.

    Returns:
        dict: {"status": "ok"} on success;
              {"status": "error", "error": <truncated message>} on failure.
    """
    logger.info("health.ready.redis.ping.start")  # BEFORE
    try:
        client.ping()
        logger.info("health.ready.redis.ping.ok")  # AFTER
        return {"status": "ok"}
    except (redis_exc.ConnectionError, redis_exc.TimeoutError) as exc:
        msg = str(exc)[:120]
        logger.warning("health.ready.redis.ping.error error=%s", msg)  # ERROR
        return {"status": "error", "error": msg}


# ---------------------------------------------------------------------------
# APIRouter — root-level probes (no /api/v1 prefix; infra, not business API).
# ---------------------------------------------------------------------------
api_router = APIRouter(tags=["observability"])


@api_router.get("/health", response_model=None)
def health() -> dict:
    """
    GET /health — platform health stub (backward compatible with T001 shape).

    Returns:
        dict: {"data": {"status": "ok", "version": "0.1.0", "uptime": float}}

    Errors:
        500: unexpected exception; logged with full context, no PII.
    """
    logger.info("health.check.start route=/health")  # BEFORE
    try:
        uptime_s = round(time.monotonic() - _START_TIME, 2)
        payload = {
            "data": {
                "status": "ok",
                "version": "0.1.0",
                "uptime": uptime_s,
            }
        }
        logger.info("health.check.ok status=ok uptime=%s", uptime_s)  # AFTER
        return payload
    except Exception:
        logger.error("health.check.error", exc_info=True)  # ERROR — no PII
        raise


@api_router.get("/live", response_model=None)
def live() -> dict:
    """
    GET /live — liveness probe. Always returns 200 while the process is running.

    No dependency checks. Indicates only that the Python process is alive.
    Consumed by K8s livenessProbe / load balancer TCP checks.

    Returns:
        dict: {"data": {"status": "ok"}}
    """
    logger.info("health.live.start route=/live")  # BEFORE
    payload = {"data": {"status": "ok"}}
    logger.info("health.live.ok")  # AFTER
    return payload


@api_router.get("/ready", response_model=None)
def ready(
    engine: Engine = Depends(get_db_engine),
    redis_client: redis_module.Redis = Depends(get_redis_client),  # type: ignore[type-arg]
) -> JSONResponse:
    """
    GET /ready — readiness probe. Pings DB and Redis; 503 if either is degraded.

    LiteLLM status is informational ("unknown") — no HTTP ping is performed
    (httpx is not a runtime dep in this slice; TECHNICAL_GUIDE §6.2 side-effect
    lists only "DB/Redis ping"). Per source-of-truth §U2 resolution.

    Args:
        engine: injected SQLAlchemy Engine (overridable in tests via dependency_overrides).
        redis_client: injected redis.Redis client.

    Returns:
        JSONResponse 200: all critical dependencies reachable.
        JSONResponse 503: at least one critical dependency degraded.

    Errors:
        500: unexpected/unhandled exception; logged with full context, no PII.
    """
    logger.info("health.ready.start route=/ready")  # BEFORE
    try:
        db_status = _ping_db(engine)
        redis_status = _ping_redis(redis_client)
        litellm_status: dict[str, Any] = {"status": "unknown"}

        all_ok = db_status["status"] == "ok" and redis_status["status"] == "ok"
        http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

        payload = {
            "data": {
                "db": db_status,
                "redis": redis_status,
                "litellm": litellm_status,
            }
        }

        if all_ok:
            logger.info("health.ready.ok db=%s redis=%s", db_status["status"], redis_status["status"])  # AFTER
        else:
            logger.warning(
                "health.ready.degraded db=%s redis=%s",
                db_status["status"],
                redis_status["status"],
            )  # AFTER degraded

        return JSONResponse(content=payload, status_code=http_status)

    except Exception:
        logger.error("health.ready.error", exc_info=True)  # ERROR — no PII
        raise
