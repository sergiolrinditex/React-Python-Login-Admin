"""
FastAPI application entry point for Hilo People backend.

Slice: P00-S01-T001 — Repo scaffold + scripts + env
Phase: P00 — Scaffold + Design System
Dependencies:
  - fastapi (installed in T003)
  - uvicorn (installed in T003)

This module declares the FastAPI app instance and a minimal GET /health stub
conformant with the API contract in HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2.
Full health/live/ready implementation lives in P00-S02-T002.
Core config (Settings, structlog) lives in T003/P00-S02-T002.

Logging uses stdlib logging with ENABLE_VERBOSE_LOGGING env flag:
  - true  → DEBUG level (full flow visible)
  - false → WARNING level (warning + error only)
No PII, tokens or secrets are logged.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

# ---------------------------------------------------------------------------
# Logging bootstrap — respects ENABLE_VERBOSE_LOGGING
# structlog is introduced in T003; until then stdlib logging is used here.
# ---------------------------------------------------------------------------
_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")
logging.basicConfig(
    level=logging.DEBUG if _VERBOSE else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

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
