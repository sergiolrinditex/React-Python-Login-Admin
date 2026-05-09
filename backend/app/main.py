"""
FastAPI application entry point for Hilo People backend.

Slice: P00-S01-T001 (scaffold) + P00-S01-T003 (structlog wiring)
       + P00-S02-T002 (health live/ready endpoints + request_id middleware)
Phase: P00 — Scaffold + Design System
Dependencies:
  - fastapi 0.136.1
  - uvicorn 0.46.0
  - structlog 25.5.0 (wired in T003 via core.logging)
  - pydantic-settings 2.14.1 (wired in T003 via core.config)

This module creates the FastAPI app and wires:
  1. configure_logging() — structlog setup (T003 option b: called at import).
  2. ops router — /health, /live, /ready (T002, in app.api.router).
  3. request_id middleware — reads X-Request-ID header or generates uuid4 hex;
     binds into structlog contextvars for end-to-end correlation;
     echoes back on response (T002, per HILO_PEOPLE_TECHNICAL_GUIDE.md §8).

Official doc note P00-S02-T002 (RESOLVED): @app.middleware("http") is the
FastAPI-idiomatic form for request_id middleware — equivalent to add_middleware
with BaseHTTPMiddleware, but avoids the Starlette Response/Awaitable type
mismatch that mypy flags on the BaseHTTPMiddleware.dispatch override.

Logging: ENABLE_VERBOSE_LOGGING=true  -> DEBUG level (full flow visible).
         ENABLE_VERBOSE_LOGGING=false -> WARNING level (warning + error only).
No PII, tokens or secrets are logged.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Awaitable, Callable

# ---------------------------------------------------------------------------
# Logging bootstrap — structlog wired here (T003 option b).
# configure_logging() is idempotent; safe to call at module import.
# MUST be called before any logger is used, including by imported modules.
# ---------------------------------------------------------------------------
_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")

from app.core.logging import configure_logging, get_logger  # noqa: E402

configure_logging(verbose=_VERBOSE)
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app — dependency installed in T003
# ---------------------------------------------------------------------------
import structlog.contextvars  # noqa: E402
from fastapi import FastAPI, Request, Response  # noqa: E402

from app.api.router import router as ops_router  # noqa: E402

APP_VERSION: str = os.getenv("APP_VERSION", "0.0.0")

app = FastAPI(
    title="Hilo People",
    version=APP_VERSION,
    description="Internal AI-powered People app — FastAPI backend.",
)


# ---------------------------------------------------------------------------
# Request-ID middleware (D3 from task-pack P00-S02-T002).
# Uses @app.middleware("http") — the FastAPI-idiomatic form per official docs
# (Pattern 1 in official doc note P00-S02-T002-health-endpoints-patterns).
# Reads X-Request-ID header; generates uuid4().hex when missing.
# Binds request_id into structlog contextvars so every log line in this
# request context carries the correlation ID.
# Echoes X-Request-ID on the response for end-to-end tracing.
# Reference: HILO_PEOPLE_TECHNICAL_GUIDE.md §8 (Logging y Observabilidad).
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Propagate or generate X-Request-ID per HTTP request.

    Purpose: ensure every backend log line carries a request_id field matching
    the X-Request-ID header visible to the API client, enabling end-to-end
    correlation across frontend, backend and future audit log.

    Params:
      request  — incoming FastAPI Request.
      call_next — next middleware/handler (FastAPI HTTP middleware callable).
    Returns: Response with X-Request-ID header added.
    Errors: any exception from call_next propagates after clearing contextvars.
    """
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:  # noqa: BLE001 — middleware must not silently swallow errors
        # NOTE (verify-slice debugger fix, P00-S02-T002, defense in depth):
        # We intentionally do NOT pass exc_info=True here.  structlog's Rich
        # traceback formatter renders frame locals — and any sensitive value
        # bound earlier in the request scope (DSN, cparams, password, JWT)
        # would leak via stdout (CWE-532).  Today this path is reached only
        # by call_next() exceptions, which can carry arbitrary upstream
        # locals.  The structured request_id field is enough for correlation;
        # FastAPI's default exception handler will still log/report the
        # exception itself.  Tracked under FU-20260509044829.
        logger.warning(
            "ERROR request_id_middleware: unhandled exception",
            request_id=request_id,
        )
        raise
    finally:
        structlog.contextvars.clear_contextvars()


# ---------------------------------------------------------------------------
# Ops router — /health, /live, /ready (P00-S02-T002)
# ---------------------------------------------------------------------------
app.include_router(ops_router)
