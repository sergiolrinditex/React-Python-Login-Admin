"""
Hilo People — FastAPI application entry point.

Slice:  P00-S01-T001 — Repo scaffold + scripts + env
Phase:  P00 Scaffold + Design System
Purpose: Creates the FastAPI application instance and registers the /health
         stub endpoint. The full health contract (DB+Redis+LiteLLM checks,
         /live and /ready) is implemented in P00-S02-T002.

Key deps:
  - fastapi: ASGI web framework (uvicorn transport, port 8000 per STACK_PROFILE).
  - logging: stdlib; level driven by ENABLE_VERBOSE_LOGGING env var.
  - time: used to track uptime from process start.

Source refs:
  - TECHNICAL_GUIDE §6.2 GET /health stub contract — response: {data:{status:"ok"}}.
  - STACK_PROFILE.yaml backend.dev_cmd (uvicorn port 8000).
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR pattern, no PII/secrets).
"""

import logging
import os
import time

from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Logging configuration
# ENABLE_VERBOSE_LOGGING drives level only; code never conditionally wraps
# log calls. Per 01-non-negotiables.md §Logging.
# ---------------------------------------------------------------------------
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
_LOG_LEVEL: int = logging.DEBUG if _VERBOSE else logging.WARNING
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Process-start timestamp — used to compute uptime in /health response.
# ---------------------------------------------------------------------------
_START_TIME: float = time.monotonic()

# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Hilo People API",
    version="0.1.0",
    description="Internal HR platform — Hilo People (scaffold)",
)


@app.get("/health", tags=["observability"], response_model=None)
async def health() -> dict:
    """
    GET /health — scaffold stub (P00-S01-T001).

    Returns a minimal status envelope per TECHNICAL_GUIDE §6.2.
    No DB, Redis or LiteLLM checks in this slice; those land in P00-S02-T002.

    Returns:
        dict: JSON ``{"data": {"status": "ok", "version": str, "uptime": float}}``.

    Errors:
        500: unexpected exception; logged with full context, no PII exposed.
    """
    logger.info("health.check.start route=/health")  # BEFORE
    try:
        uptime_s = round(time.monotonic() - _START_TIME, 2)
        payload = {
            "data": {
                "status": "ok",
                "version": app.version,
                "uptime": uptime_s,
            }
        }
        logger.info("health.check.ok status=ok uptime=%s", uptime_s)  # AFTER
        return payload
    except Exception:
        logger.error("health.check.error", exc_info=True)  # ERROR — no PII/secrets
        raise
