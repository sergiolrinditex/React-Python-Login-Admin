"""
Structured logging configuration via structlog.

Slice: P00-S02-T004 — Disable structlog Rich-traceback show_locals globally
Phase: P00 — Scaffold + Design System

Security fix: CWE-532 — sensitive data in log files.
Origin: FU-20260509044829 promoted from T002 verify-slice BLOCKER finding #1.

ARCHITECTURAL FIX:
  structlog's RichTracebackFormatter defaults to show_locals=True.  When any
  caller invokes _logger.error(..., exc_info=True) or _logger.exception(...),
  the Rich traceback renderer walks every frame in the exception traceback and
  prints local variables verbatim (e.g. cparams={host,user,password,...} from
  asyncpg/SQLAlchemy connect paths).  The existing dict-level _redaction_processor
  does NOT prevent this because frame locals are opaque to it — they live inside
  the exc_info tuple, not in event_dict keys.

  Defense in depth (Option C, task pack §Strategy hints):
    1. ConsoleRenderer receives a RichTracebackFormatter(show_locals=False).
       This is the primary fix: frame locals are never rendered regardless of
       which code path logs the exception.
    2. _REDACTED_KEYS extended with pwd, dsn, database_url, connection_string
       (per acceptance criteria #1 in the task pack).  The dict-level scrubber
       still fires for top-level event_dict keys such as password=, token=, etc.

BEFORE: ConsoleRenderer(exception_formatter=RichTracebackFormatter(show_locals=True))
AFTER:  ConsoleRenderer(exception_formatter=RichTracebackFormatter(show_locals=False))

Provides:
  - configure_logging(verbose: bool) — must be called once at app startup (main.py).
  - get_logger(name: str) — returns a bound structlog logger for the caller.

Logging contract (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.5):
  - BEFORE / AFTER / ERROR pattern in every function that calls this logger.
  - ENABLE_VERBOSE_LOGGING=true  → DEBUG level (full flow visible).
  - ENABLE_VERBOSE_LOGGING=false → WARNING level (warning + error only).
  - Redacted keys: password, pwd, token, secret, api_key, encrypted_secret,
    dsn, database_url, connection_string, prompt (full), document.content.
  - request_id propagated end-to-end (middleware wired in P00-S02-T002).
  - No PII, tokens, or secrets in any log field or traceback frame locals.

Dependencies:
  - structlog 25.5.0
  - rich (pulled in by structlog[dev] extras)
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

# Keys that must never appear in log payloads.
# Extended in P00-S02-T004 with pwd, dsn, database_url, connection_string
# (acceptance criteria #1 — defense in depth for CWE-532 residual risk).
_REDACTED_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "pwd",
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
        "dsn",
        "database_url",
        "connection_string",
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

    Scope: top-level event_dict keys only.  Frame-locals in exc_info
    tracebacks are handled by RichTracebackFormatter(show_locals=False)
    configured in configure_logging().

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

    Security: ConsoleRenderer is wired with
    RichTracebackFormatter(show_locals=False) — see module docstring for
    the full CWE-532 mitigation rationale (FU-20260509044829 / T004).

    Purpose: wire structlog processors, set log level based on verbose flag.
    Params:
      verbose — True → DEBUG level; False → WARNING level.
    Returns: None.
    Errors: RuntimeError if structlog.configure raises (propagated).
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    # BEFORE: log startup intent before structlog machinery is active.
    print(  # noqa: T201
        f"[logging] BEFORE configure_logging: verbose={verbose}",
        file=sys.stderr,
    )

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
        # CWE-532 fix (P00-S02-T004): pass show_locals=False to the Rich
        # traceback formatter so that frame-local variables (e.g. asyncpg
        # cparams containing database credentials) are never rendered to
        # stdout when exc_info=True is used anywhere in the codebase.
        # structlog 25.5.0 API confirmed: RichTracebackFormatter(show_locals=False)
        # and ConsoleRenderer(exception_formatter=...) are both stable kwargs.
        _safe_traceback_formatter = structlog.dev.RichTracebackFormatter(
            show_locals=False,
        )
        renderer: Any = structlog.dev.ConsoleRenderer(
            exception_formatter=_safe_traceback_formatter,
        )
    else:
        # JSON renderer (production): traceback.format_exception does not
        # include locals by default.  Keeping show_locals=False in the
        # Console path ensures dev and prod behave identically on this axis.
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

    # AFTER: confirm configuration completed via structlog (now bootstrapped).
    _internal = get_logger(__name__)
    _internal.debug(
        "AFTER configure_logging: structlog configured with CWE-532 mitigation",
        verbose=verbose,
        log_level=logging.getLevelName(log_level),
        show_locals="False (security fix P00-S02-T004)",
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
