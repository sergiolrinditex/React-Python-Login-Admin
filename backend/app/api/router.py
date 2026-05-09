"""
Ops router: GET /health, GET /live, GET /ready.

Slice: P00-S02-T002 — Health live ready endpoints
Phase: P00 — Scaffold + Design System

Responsibilities:
  - /health — backward-compatible flat liveness probe (status, version, uptime).
    Shape is intentionally flat (not {data:{...}} envelope) for T001 compose
    healthcheck back-compat.  See Discrepancy D1 in handoff P00-S02-T002.md.
  - /live  — process liveness only; never touches DB.
  - /ready — dependency readiness; DB is probed with SELECT 1; Redis and LiteLLM
    are declared as not_implemented until their clients land (D2).

Logging contract (01-non-negotiables.md §Logging):
  - BEFORE log at DEBUG (only visible when ENABLE_VERBOSE_LOGGING=true).
  - AFTER  log at DEBUG (same gate).
  - ERROR  log at ERROR with structured fields only (error_class + sanitized
    db_detail).  exc_info=True is intentionally NOT used: structlog's Rich
    traceback formatter renders frame locals, and the asyncpg/SQLAlchemy
    connect path stores DSN+password in those locals — that would leak
    credentials to stdout (CWE-532).  Tracked under FU-20260509044829.
  - No PII, DSNs, connection strings or secret values in any log field.
  - Structlog BoundLogger API: first positional arg is the event string;
    extra context is passed as keyword args.

Error handling:
  - /ready catches sqlalchemy.exc.SQLAlchemyError and asyncpg.PostgresError
    specifically — not bare Exception (non-negotiable §"Error handling").

Dependencies:
  - fastapi 0.136.1
  - sqlalchemy[asyncio] 2.0.49 (via app.core.db.get_engine)
  - structlog 25.5.0 (via app.core.logging.get_logger)
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_engine
from app.core.logging import get_logger

_logger = get_logger(__name__)

# Module-level start-time shared by /health, /live and /ready.
# Moved here from main.py so all three handlers share the same origin reference.
_START_TIME: float = time.monotonic()

APP_VERSION: str = os.getenv("APP_VERSION", "0.0.0")

router = APIRouter(tags=["ops"])


def _uptime_seconds() -> float:
    """Return seconds since module load, rounded to 3 dp.

    Purpose: provide monotonic uptime shared by all ops handlers.
    Returns: float seconds >= 0.
    Errors: none.
    """
    return round(time.monotonic() - _START_TIME, 3)


@router.get("/health")
async def health() -> dict[str, Any]:
    """Return application health status (backward-compatible flat shape).

    Purpose: basic liveness probe confirming the FastAPI process is alive.
    Flat shape {status, version, uptime} preserved for T001 compose HEALTHCHECK
    and T003 evidence curl.  See Discrepancy D1 in handoff P00-S02-T002.md.

    Params: none
    Returns: JSON dict with keys status="ok", version (str), uptime (float s).
    Errors: 500 on unexpected exceptions (FastAPI default handler).

    API contract: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 GET /health
    """
    _logger.debug("BEFORE health.start: computing uptime")
    uptime = _uptime_seconds()
    resp: dict[str, Any] = {
        "status": "ok",
        "version": APP_VERSION,
        "uptime": uptime,
    }
    _logger.debug("AFTER health.ok: returning status", status="ok", uptime_s=uptime)
    return resp


@router.get("/live")
async def live() -> dict[str, Any]:
    """Return process liveness status — no DB or external dependency calls.

    Purpose: confirm the FastAPI process is alive and responding.
    Never touches the database or any external service.

    Params: none
    Returns: JSON dict with keys status="alive", version (str), uptime (float s).
    Errors: 500 on unexpected exceptions (FastAPI default handler).

    API contract: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 GET /live
    """
    _logger.debug("BEFORE health.live.start: computing uptime")
    uptime = _uptime_seconds()
    resp: dict[str, Any] = {
        "status": "alive",
        "version": APP_VERSION,
        "uptime": uptime,
    }
    _logger.debug("AFTER health.live.ok: process alive", uptime_s=uptime)
    return resp


@router.get("/ready")
async def ready(response: Response) -> dict[str, Any]:
    """Return readiness status with dependency probe results.

    Purpose: confirm the service and its critical dependencies (DB) are ready
    to serve production traffic.

    DB probe: executes SELECT 1 via the async engine.  Catches SQLAlchemyError
    and asyncpg.PostgresError only — NOT bare Exception (non-negotiable).

    Redis + LiteLLM: marked not_implemented until their clients are wired.
    See Discrepancy D2 in handoff P00-S02-T002.md.

    Params:
      response — FastAPI Response injected to set HTTP status code.
    Returns: JSON dict with status and checks sub-dict.
      200: {status:"ready", checks:{db:{status:"ok"}, ...}}
      503: {status:"not_ready", reason:"db", checks:{db:{status:"fail",
           detail:"<sanitized>"}, ...}}
    Errors: 503 if DB probe fails.  500 on unexpected (non-SQLAlchemy) errors.

    API contract: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 GET /ready
    """
    _logger.debug("BEFORE health.ready.start: starting dependency probes")

    db_check: dict[str, Any] = await _probe_db()

    checks: dict[str, Any] = {
        "db": db_check,
        "redis": {"status": "not_implemented", "reason": "client_not_wired"},
        "litellm": {"status": "not_implemented", "reason": "client_not_wired"},
    }

    if db_check["status"] == "ok":
        _logger.debug("AFTER health.ready.ok: all wired probes passed", db_status="ok")
        return {"status": "ready", "checks": checks}

    # Critical probe failed — return 503.
    _logger.error(
        "AFTER health.ready.not_ready: critical probe failed",
        failed_probe="db",
        db_detail=db_check.get("detail", ""),
    )
    response.status_code = 503
    return {"status": "not_ready", "reason": "db", "checks": checks}


async def _probe_db() -> dict[str, Any]:
    """Execute SELECT 1 against the async DB engine.

    Purpose: validate that a real DB connection can be obtained and a trivial
    query completes.  pool_pre_ping=True fires on checkout; this probe adds
    an explicit per-request signal.

    Returns: {"status": "ok"} on success, {"status": "fail", "detail": "<msg>"}
    on any SQLAlchemy or asyncpg error.
    Errors: catches SQLAlchemyError first; falls back to bare Exception for
    asyncpg errors not wrapped by SQLAlchemy.
    The detail field is sanitized: DSN host/credentials are never included.
    """
    _logger.debug("BEFORE health.db.start: connecting to DB for SELECT 1")
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        _logger.debug("AFTER health.db.ok: SELECT 1 succeeded")
        return {"status": "ok"}
    except SQLAlchemyError as exc:
        detail = _sanitize_db_error(exc)
        # NOTE (verify-slice debugger fix, P00-S02-T002): exc_info=True dropped
        # to prevent CWE-532 leak via structlog Rich traceback frame locals.
        # The asyncpg/SQLAlchemy connect path stores cparams + ConnectionParameters
        # in stack frames — those contain the full DSN incl. password.  The
        # structured fields below (error_class + db_detail) are sufficient for
        # operational debugging.  Re-enabling exc_info requires a global structlog
        # tweak (RichTracebackFormatter(show_locals=False)) tracked under
        # follow-up FU-20260509044829-disable-structlog-rich-traceback-show-locals-glo
        # and is OUT OF SCOPE for T002.  See verify-slice handoff finding #1.
        _logger.error(
            "ERROR health.ready.db_failed: SQLAlchemy error on SELECT 1",
            error_class=type(exc).__name__,
            db_detail=detail,
        )
        return {"status": "fail", "detail": detail}
    except Exception as exc:  # noqa: BLE001 — asyncpg may raise non-SQLAlchemy errors
        # asyncpg.PostgresError subclasses may not always be wrapped by SQLAlchemy.
        # Catch here ONLY as a safety net so the probe returns 503 instead of 500.
        detail = _sanitize_db_error(exc)
        # NOTE (verify-slice debugger fix, P00-S02-T002): see SQLAlchemyError
        # branch above for the same exc_info=True drop rationale (CWE-532).
        _logger.error(
            "ERROR health.ready.db_failed: unexpected error on SELECT 1",
            error_class=type(exc).__name__,
            db_detail=detail,
        )
        return {"status": "fail", "detail": detail}


def _sanitize_db_error(exc: BaseException) -> str:
    """Return a log-safe, DSN-free summary of a DB error.

    Purpose: produce a human-readable detail string that NEVER leaks the
    DATABASE_URL, host name, password, or any other credential.

    Params: exc — the caught exception.
    Returns: str with the exception class name and a safe message fragment.
    Errors: none (never raises).
    """
    raw = str(exc)
    # Strip common credential patterns before exposing anything.
    safe_fragments = [
        frag
        for frag in raw.split()
        # Drop words that look like DSN components.
        if not any(
            frag.lower().startswith(prefix)
            for prefix in (
                "postgresql",
                "asyncpg",
                "postgres://",
                "localhost",
                "127.",
                "change-me",
                "password",
                "token",
                "secret",
            )
        )
    ]
    safe_msg = " ".join(safe_fragments[:8])  # Limit to first 8 safe words.
    return f"{type(exc).__name__}: {safe_msg}" if safe_msg else type(exc).__name__
