"""
Hilo People — FastAPI application entry point.

Slice:  P00-S02-T002 — Health live ready endpoints
Phase:  P00 Scaffold + Design System
Purpose: Creates the FastAPI application instance and mounts the api_router
         which provides /health (backward compat), /live and /ready probes.
         The inline /health stub from P00-S01-T001 has been migrated to
         backend/app/api/router.py so all observability endpoints live in one
         module.

Key deps:
  - fastapi: ASGI web framework (uvicorn transport, port 8000 per STACK_PROFILE).
  - logging: stdlib; level driven by ENABLE_VERBOSE_LOGGING env var.
  - app.api.router: api_router with /health, /live, /ready.

Source refs:
  - TECHNICAL_GUIDE §6.2 health endpoints contract.
  - STACK_PROFILE.yaml backend.dev_cmd (uvicorn port 8000).
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR pattern, no PII/secrets).
"""

import logging
import os

from fastapi import FastAPI

from app.api.router import api_router

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
# FastAPI application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Hilo People API",
    version="0.1.0",
    description="Internal HR platform — Hilo People (scaffold)",
)

# ---------------------------------------------------------------------------
# Mount routers
# api_router provides /health (backward-compat stub), /live, /ready at root.
# Future feature routers will mount at /api/v1/ prefix.
# ---------------------------------------------------------------------------
app.include_router(api_router)
