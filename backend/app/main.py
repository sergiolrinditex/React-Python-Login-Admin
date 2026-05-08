"""
FastAPI application entry point for Hilo People backend.

Slice: P00-S01-T001 (scaffold) + P00-S01-T003 (structlog wiring)
Phase: P00 — Scaffold + Design System
Dependencies:
  - fastapi 0.136.1
  - uvicorn 0.46.0
  - structlog 25.5.0 (wired in T003 via core.logging)
  - pydantic-settings 2.14.1 (wired in T003 via core.config)

This module declares the FastAPI app instance and a minimal GET /health stub
conformant with the API contract in HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2.
Full health/live/ready implementation lives in P00-S02-T002.

Logging: stdlib is replaced by structlog in T003 via configure_logging().
ENABLE_VERBOSE_LOGGING=true  → DEBUG level (full flow visible).
ENABLE_VERBOSE_LOGGING=false → WARNING level (warning + error only).
No PII, tokens or secrets are logged.

T003 amendment: one-line wiring of core.logging.configure_logging() per
task-pack §Front→Back→DB decision (option b). This keeps ENABLE_VERBOSE_LOGGING
semantics identical while migrating from basicConfig to structlog.
"""
from __future__ import annotations

import os
import time
from typing import Any

# ---------------------------------------------------------------------------
# Logging bootstrap — structlog wired here (T003 option b).
# configure_logging() is idempotent; safe to call at module import.
# ---------------------------------------------------------------------------
_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")

from app.core.logging import configure_logging, get_logger  # noqa: E402

configure_logging(verbose=_VERBOSE)
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app — dependency installed in T003
# ---------------------------------------------------------------------------
from fastapi import FastAPI  # noqa: E402  # installed in T003

_START_TIME: float = time.monotonic()

APP_VERSION: str = os.getenv("APP_VERSION", "0.0.0")

app = FastAPI(
    title="Hilo People",
    version=APP_VERSION,
    description="Internal AI-powered People app — FastAPI backend.",
)


# ---------------------------------------------------------------------------
# GET /health — stub (envelope shape per API contract)
# Full implementation (live/ready checks) added in P00-S02-T002.
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
async def health() -> dict[str, Any]:
    """Return application health status.

    Purpose: Basic liveness probe confirming the process is running.
    Params: none
    Returns: JSON dict with `status`, `version`, `uptime` fields.
    Errors: 500 on unexpected exceptions (handled by FastAPI default handler).

    API contract reference: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 GET /health.
    Full impl with DB/Redis probes lives in P00-S02-T002.
    """
    logger.debug("BEFORE health check: computing uptime")
    uptime_seconds = round(time.monotonic() - _START_TIME, 3)
    response: dict[str, Any] = {
        "status": "ok",
        "version": APP_VERSION,
        "uptime": uptime_seconds,
    }
    logger.debug("AFTER health check: status=%s uptime=%s", response["status"], uptime_seconds)
    return response
