"""
CLI entry point for the verification seed bundle loader.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Usage:
  python -m app.seeds.bootstrap_verification_data --source <dir> [--only <ns>]

  --source <dir>   Path to the verification bundle root (e.g. data/verification/).
  --only   <ns>    Load only one namespace. Allowed: auth, rag_chat, history,
                   admin_ai, rag_docs, mcp_agents. Omit to load all six.
  --dry-run        Validate fixtures and schemas; do NOT write to DB.

Exit codes:
  0  All consumed namespaces either persisted rows OR cleanly skipped (table missing).
  1  A fixture failed JSON/Pydantic validation, or a required namespace directory is missing.
  2  The --source directory does not exist.

Logging:
  Every namespace logs BEFORE/AFTER under ENABLE_VERBOSE_LOGGING=true.
  ENABLE_VERBOSE_LOGGING=false shows only WARN/ERROR.
  No PII (emails hashed), no raw credentials (masked to first 4 chars).
  request_id bound at CLI entry — consistent with /ready middleware convention.

Security (CWE-532): do NOT log exc_info=True. Use structured fields (error_class,
  detail) only. No DSN/password/secret ever surfaces in log output.

Dependencies:
  - structlog 25.5.0
  - pydantic 2.12.5
  - sqlalchemy[asyncio] 2.0.49
  - app.core.config, app.core.logging
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

import structlog.contextvars

from app.core.db import get_engine
from app.core.logging import configure_logging, get_logger
from app.seeds.io import BundleLoadError, check_bundle_dir
from app.seeds.loader import (
    LoadReport,
    load_admin_ai,
    load_auth,
    load_history,
    load_mcp_agents,
    load_rag_chat,
    load_rag_docs,
)

# Canonical namespace set (matches TECHNICAL_GUIDE §6.5 column 4 exactly).
_ALL_NAMESPACES: tuple[str, ...] = (
    "auth",
    "rag_chat",
    "history",
    "admin_ai",
    "rag_docs",
    "mcp_agents",
)

_NAMESPACE_LOADERS = {
    "auth": load_auth,
    "rag_chat": load_rag_chat,
    "history": load_history,
    "admin_ai": load_admin_ai,
    "rag_docs": load_rag_docs,
    "mcp_agents": load_mcp_agents,
}


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser.

    Purpose: argparse (stdlib) — no new dep needed (task pack §Notes for developer).
    Returns: configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="python -m app.seeds.bootstrap_verification_data",
        description=(
            "Idempotent loader for the data/verification/ bundle. "
            "Loads all six namespaces or a single one via --only. "
            "Table-tolerant: skips namespaces whose tables do not yet exist."
        ),
    )
    parser.add_argument(
        "--source",
        required=True,
        metavar="DIR",
        help="Path to the verification bundle root directory.",
    )
    parser.add_argument(
        "--only",
        choices=list(_ALL_NAMESPACES),
        default=None,
        metavar="NAMESPACE",
        help=(
            f"Load only this namespace. Choices: {', '.join(_ALL_NAMESPACES)}. "
            "Omit to load all six."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate fixtures without writing to DB. Exit 0 if all valid.",
    )
    return parser


async def _run(
    source_dir: Path,
    namespaces: tuple[str, ...],
    *,
    dry_run: bool,
) -> int:
    """Async main: load each namespace and collect reports.

    Purpose: inner async coroutine so the sync _main() can call asyncio.run().
    Params:
      source_dir — verified bundle root path.
      namespaces — namespaces to load in order.
      dry_run    — if True, no DB writes.
    Returns: exit code (0 = ok, 1 = fixture/schema error, 2 = dir missing).
    Errors: any unexpected error is caught here; logged with error_class only (no DSN/traceback).
    """
    _logger = get_logger(__name__)

    engine = get_engine()

    _logger.info(
        "seed.run.start",
        source=str(source_dir),
        namespaces=list(namespaces),
        dry_run=dry_run,
        db_host_redacted="[redacted]",
    )

    reports: list[LoadReport] = []
    exit_code = 0

    for ns in namespaces:
        loader_fn = _NAMESPACE_LOADERS[ns]
        _logger.debug("seed.dispatch.before", namespace=ns)
        try:
            report = await loader_fn(engine, source_dir, dry_run=dry_run)
            reports.append(report)
            _logger.debug(
                "seed.dispatch.after",
                namespace=ns,
                rows_inserted=report.rows_inserted,
                skipped_tables=report.skipped_tables,
            )
        except BundleLoadError as exc:
            _logger.error(
                "seed.fixture.error",
                namespace=ns,
                error_class=type(exc).__name__,
                detail=str(exc),
            )
            return 1
        except Exception as exc:  # noqa: BLE001
            # Unexpected error — log error_class and sanitized message only.
            # DO NOT use exc_info=True (CWE-532 / T002 lesson).
            _logger.error(
                "seed.unexpected.error",
                namespace=ns,
                error_class=type(exc).__name__,
                detail=repr(exc)[:200],
            )
            return 2

    # Summary.
    total_inserted = sum(r.rows_inserted for r in reports)
    total_skipped_tables = sum(len(r.skipped_tables) for r in reports)
    _logger.info(
        "seed.run.done",
        namespaces_loaded=len(reports),
        total_rows_inserted=total_inserted,
        total_skipped_tables=total_skipped_tables,
        dry_run=dry_run,
        exit_code=exit_code,
    )

    # Cleanup engine connections.
    await engine.dispose()

    return exit_code


def main() -> None:
    """Synchronous entry point for module invocation.

    Purpose: parse args, configure logging, bind request_id, run async loader.
    Exits with the appropriate code (0/1/2).
    """
    parser = _build_parser()
    args = parser.parse_args()

    # Configure logging before anything else.
    verbose = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")
    configure_logging(verbose=verbose)

    _logger = get_logger(__name__)

    # Bind a request_id for this CLI run — consistent with /ready middleware pattern.
    request_id = uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    _logger.info(
        "seed.cli.start",
        source=args.source,
        only=args.only,
        dry_run=args.dry_run,
        request_id=request_id,
    )

    source_dir = Path(args.source).resolve()

    # Guard 1: --source directory must exist. Exit 2 (not 1) per spec.
    try:
        check_bundle_dir(source_dir)
    except FileNotFoundError as exc:
        _logger.error(
            "seed.cli.source_missing",
            source=args.source,
            error_class="FileNotFoundError",
            detail=str(exc),
        )
        print(f"ERROR: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(2)

    # Determine which namespaces to run.
    namespaces = (args.only,) if args.only else _ALL_NAMESPACES

    # Run the async loader.
    try:
        exit_code = asyncio.run(_run(source_dir, namespaces, dry_run=args.dry_run))
    except BundleLoadError as exc:
        _logger.error(
            "seed.cli.bundle_error",
            error_class=type(exc).__name__,
            detail=str(exc),
        )
        print(f"ERROR: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        _logger.error(
            "seed.cli.fatal_error",
            error_class=type(exc).__name__,
            detail=repr(exc)[:200],
        )
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(2)
    finally:
        structlog.contextvars.clear_contextvars()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
