"""
Structured logging configuration via structlog.

Slice: P00-S01-T003 — Backend dependency pack
Phase: P00 — Scaffold + Design System

Provides:
  - configure_logging(verbose: bool) — must be called once at app startup (main.py).
  - get_logger(name: str) — returns a bound structlog logger for the caller.

Logging contract (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.5):
  - BEFORE / AFTER / ERROR pattern in every function that calls this logger.
  - ENABLE_VERBOSE_LOGGING=true  → DEBUG level (full flow visible).
  - ENABLE_VERBOSE_LOGGING=false → WARNING level (warning + error only).
  - Redacted keys: password, token, secret, api_key, encrypted_secret,
    prompt (full), document.content.
  - request_id propagated end-to-end (middleware wired in P00-S02-T002).
  - No PII, tokens, or secrets in any log field.

Dependencies:
  - structlog 25.5.0
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

# Keys that must never appear in log payloads.
_REDACTED_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
        "encrypted_secret",
        "jwt_secret",
        "provider_encryption_key",
        "litellm_master_key",
        "resend_api_key",
        "prompt",
        "document.content",
    }
)

_REDACTED_SENTINEL = "***REDACTED***"

_configured: bool = False


def _redaction_processor(
    logger: Any,  # noqa: ANN401
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor: replace sensitive keys with a sentinel.

    Purpose: prevent accidental leakage of secrets in structured logs.
    Params:
      logger  — structlog logger (unused).
      method  — log method name (unused).
      event_dict — mutable log record dict.
    Returns: event_dict with sensitive keys replaced by _REDACTED_SENTINEL.
    Errors: none (processor never raises).
    """
    for key in list(event_dict.keys()):
        if key.lower() in _REDACTED_KEYS:
            event_dict[key] = _REDACTED_SENTINEL
    return event_dict


def configure_logging(verbose: bool = False) -> None:
    """Configure structlog + stdlib logging for the application.

    Must be called ONCE at application startup (app/main.py) before any
    logger is used. Idempotent — subsequent calls are no-ops.

    Purpose: wire structlog processors, set log level based on verbose flag.
    Params:
      verbose — True → DEBUG level; False → WARNING level.
    Returns: None.
    Errors: RuntimeError if structlog.configure raises (propagated).
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    log_level = logging.DEBUG if verbose else logging.WARNING

    logging.basicConfig(
        stream=sys.stdout,
        level=log_level,
        format="%(message)s",
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _redaction_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if verbose:
        renderer: Any = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    _configured = True

    _internal = get_logger(__name__)
    _internal.debug(
        "AFTER configure_logging: structlog configured",
        verbose=verbose,
        log_level=logging.getLevelName(log_level),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name.

    Purpose: single factory so every module uses a consistent logger type.
    Params:
      name — typically __name__ of the calling module.
    Returns: structlog BoundLogger bound to name.
    Errors: none.
    """
    return structlog.get_logger(name)
