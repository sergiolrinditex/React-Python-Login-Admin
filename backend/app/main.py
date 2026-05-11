"""
Hilo People — FastAPI application entry point.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up (WRITE_SET_DRIFT: main.py)
Phase:  P01 Auth + Data Foundation
Purpose: Creates the FastAPI application instance and mounts routers:
         - api_router: /health, /live, /ready probes (root-level).
         - auth_router: /api/v1/auth/* — sign-up and future auth endpoints.

WRITE_SET_DRIFT from P01-S02-T001:
  This file was last modified in P00-S02-T002 (health probes). T001 adds
  auth router mounting — a minimal two-line change. Flagged in handoff.

Key deps:
  - fastapi: ASGI web framework (uvicorn transport, port 8000 per STACK_PROFILE).
  - logging: stdlib; level driven by ENABLE_VERBOSE_LOGGING env var.
  - app.api.router: api_router with /health, /live, /ready.
  - app.auth: auth_router with /api/v1/auth/sign-up.

Source refs:
  - TECHNICAL_GUIDE §6.2 health endpoints contract.
  - STACK_PROFILE.yaml backend.dev_cmd (uvicorn port 8000).
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR pattern, no PII/secrets).
"""

import logging
import os

from fastapi import FastAPI

from app.api.router import api_router
from app.auth import auth_router

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
    description="Internal HR platform — Hilo People",
)

# ---------------------------------------------------------------------------
# Mount routers
# api_router: /health, /live, /ready (root-level — no prefix)
# auth_router: /api/v1/auth/* (feature routes)
# ---------------------------------------------------------------------------
app.include_router(api_router)
app.include_router(auth_router, prefix="/api/v1")
