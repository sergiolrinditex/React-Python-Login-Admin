"""
Hilo People backend — FastAPI application entry point.

Slice: P00-S01-T001 — Repo scaffold + scripts + env.
Phase: P00 — Scaffold + Design System.

Responsibilities:
  - Creates the FastAPI application instance.
  - Configures the root logger (DEBUG when ENABLE_VERBOSE_LOGGING=true, WARNING otherwise).
  - Registers the X-Request-ID propagation middleware.
  - Exposes GET /health — stub that confirms the app is alive and returns uptime.

Dependencies:
  - fastapi>=0.115 (from pyproject.toml)
  - uvicorn[standard]>=0.30 (from pyproject.toml)
  - pydantic>=2.9 (from pyproject.toml)
  - python-dotenv>=1.0 (loaded externally by uvicorn via .env when present)

Non-obvioius choices (see ADR in TECHNICAL_GUIDE §15):
  - Logger is set at the root level so every module in this package inherits
    the configured level without repeating setup code.
  - Request-ID middleware runs first so downstream handlers and logs always
    have a traceable X-Request-ID header, matching rule 01 §Security
    "Request correlation".
  - START_MONO is captured at import time (module-level constant) for accurate
    uptime across worker restarts under uvicorn --reload.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Startup timestamp — captured once when the module is first imported.
# ---------------------------------------------------------------------------
START_MONO: float = time.monotonic()


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """Configure root logger based on ENABLE_VERBOSE_LOGGING env var.

    true  -> level DEBUG; shows full request flow.
    false -> level WARNING; shows only warnings and errors (default for prod).
    Never log secrets, tokens or PII.
    """
    verbose_raw = os.environ.get("ENABLE_VERBOSE_LOGGING", "false").strip().lower()
    level = logging.DEBUG if verbose_raw == "true" else logging.WARNING

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Remove existing handlers to avoid duplicate output under --reload.
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


_configure_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Application lifespan handler.

    Logs app startup and shutdown events.
    Never logs sensitive env vars (JWT keys, DB passwords, encryption keys).
    """
    logger.info(
        "app.startup title=%s version=%s",
        app.title,
        app.version,
    )
    yield
    logger.info("app.shutdown title=%s", app.title)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

APP_VERSION: str = os.environ.get("APP_VERSION", "0.0.0")

app = FastAPI(
    title="hilo-people-backend",
    version=APP_VERSION,
    description="Hilo People backend API.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# X-Request-ID middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Response:
    """Propagate or generate X-Request-ID header.

    - If the incoming request carries X-Request-ID, propagate it downstream.
    - If not, generate a new UUID v4.
    - Always return the request ID in the response header.
    - Stores the resolved request_id in request.state for use by route handlers.

    Complies with rule 01 §Security "Request correlation": every HTTP request
    carries a traceable ID that appears in all related log entries.
    """
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id

    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health(request: Request) -> JSONResponse:
    """GET /health — liveness probe.

    Returns:
        200 OK with JSON:
            status: "ok"
            version: str — value of APP_VERSION env var (default "0.0.0")
            uptime: float — seconds since app module was first imported

    Returns:
        503 Service Unavailable (JSON with error/code/details) if the handler
        itself encounters an unexpected error.

    Logging:
        BEFORE: health.check.start with request_id
        AFTER:  health.check.ok   with uptime
    """
    req_id: str = getattr(request.state, "request_id", str(uuid.uuid4()))

    # BEFORE log — always emitted; visible only in DEBUG mode.
    logger.info("health.check.start request_id=%s", req_id)

    try:
        uptime: float = round(time.monotonic() - START_MONO, 3)
        payload: dict[str, Any] = {
            "status": "ok",
            "version": APP_VERSION,
            "uptime": uptime,
        }

        # AFTER log
        logger.info("health.check.ok request_id=%s uptime=%.3f", req_id, uptime)

        return JSONResponse(content=payload, headers={"X-Request-ID": req_id})

    except Exception as exc:
        # Full context logged; stack trace included.
        logger.exception(
            "health.check.error request_id=%s error=%s",
            req_id,
            str(exc),
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": "Health check failed",
                "code": "HEALTH_CHECK_FAILED",
                "details": str(exc),
            },
            headers={"X-Request-ID": req_id},
        )
