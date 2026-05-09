"""
CLI entry point for the verification seed bundle loader.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Usage:
  python -m app.seeds.bootstrap_verification_data --source <dir> [--only <ns>]

  --source <dir>   Path to the verification bundle root (e.g. data/verification/).
  --only   <ns>    Load only one namespace. Allowed: auth, rag_chat, history,
                   admin_ai, rag_docs, mcp_agents. Omit to load all six.
  --dry-run        Validate fixtures and schemas; do NOT write to DB.

CHANGE from T003:
  - Reads MANIFEST.json to extract _bundle_type ('synthetic' or 'productive').
  - Propagates bundle_type to each namespace loader so schema guards are enforced.
  - Fails fast if bundle_type is 'productive' and required env vars are missing
    (delegated to resolve_env_var in loaders).
  - MANIFEST._bundle_type defaults to 'synthetic' when field is absent
    (backward-compat for old bundles without the field).

Exit codes:
  0  All consumed namespaces either persisted rows OR cleanly skipped (table missing).
  1  A fixture failed JSON/Pydantic validation, or a required namespace directory is
     missing, or a required productive env var is not set.
  2  The --source directory does not exist.

Logging:
  Every namespace logs BEFORE/AFTER under ENABLE_VERBOSE_LOGGING=true.
  ENABLE_VERBOSE_LOGGING=false shows only WARN/ERROR.
  No PII (emails hashed), no raw credentials (masked to env var name only).
  request_id bound at CLI entry — consistent with /ready middleware convention.

Security (CWE-532): do NOT log exc_info=True. No DSN/password/secret in logs.

Dependencies:
  - structlog 25.5.0
  - pydantic 2.12.5
  - sqlalchemy[asyncio] 2.0.49
  - app.core.config, app.core.logging
"""
from __future__ import annotations

import argparse
import asyncio
import json
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
from app.seeds.loader._common import BundleType

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


def _read_bundle_type(source_dir: Path) -> BundleType:
    """Read _bundle_type from MANIFEST.json; default 'synthetic' if absent.

    Purpose: propagate bundle_type to each namespace loader so schema guards
    (synthetic/productive) are correctly applied.

    Params:
      source_dir — verified bundle root path.
    Returns: 'synthetic' or 'productive'.
    Errors: BundleLoadError if MANIFEST.json is malformed JSON.
    """
    manifest_path = source_dir / "MANIFEST.json"
    if not manifest_path.exists():
        return "synthetic"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleLoadError(
            manifest_path,
            f"MANIFEST.json is not valid JSON: {exc}",
        ) from exc

    bundle_type = manifest.get("_bundle_type", "synthetic")
    if bundle_type not in ("synthetic", "productive"):
        raise BundleLoadError(
            manifest_path,
            f"MANIFEST._bundle_type must be 'synthetic' or 'productive', got: {bundle_type!r}",
        )
    return bundle_type  # type: ignore[return-value]


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.seeds.bootstrap_verification_data",
        description=(
            "Idempotent loader for the data/verification/ bundle. "
            "Loads all six namespaces or a single one via --only. "
            "Table-tolerant: skips namespaces whose tables do not yet exist. "
            "Reads MANIFEST._bundle_type to enforce synthetic/productive guards."
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
    bundle_type: BundleType,
) -> int:
    """Async main: load each namespace and collect reports.

    Purpose: inner async coroutine so the sync _main() can call asyncio.run().
    Params:
      source_dir  — verified bundle root path.
      namespaces  — namespaces to load in order.
      dry_run     — if True, no DB writes.
      bundle_type — 'synthetic' or 'productive'; forwarded to each loader.
    Returns: exit code (0 = ok, 1 = fixture/schema/env error, 2 = dir missing).
    """
    _logger = get_logger(__name__)

    engine = get_engine()

    _logger.info(
        "seed.run.start",
        source=str(source_dir),
        namespaces=list(namespaces),
        dry_run=dry_run,
        bundle_type=bundle_type,
        db_host_redacted="[redacted]",
    )

    reports: list[LoadReport] = []
    exit_code = 0

    for ns in namespaces:
        loader_fn = _NAMESPACE_LOADERS[ns]
        _logger.debug("seed.dispatch.before", namespace=ns)
        try:
            report = await loader_fn(
                engine, source_dir, dry_run=dry_run, bundle_type=bundle_type
            )
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
        bundle_type=bundle_type,
        exit_code=exit_code,
    )

    await engine.dispose()

    return exit_code


def main() -> None:
    """Synchronous entry point for module invocation.

    Purpose: parse args, configure logging, bind request_id, run async loader.
    Reads MANIFEST._bundle_type and propagates to all loaders.
    Exits with the appropriate code (0/1/2).
    """
    parser = _build_parser()
    args = parser.parse_args()

    verbose = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")
    configure_logging(verbose=verbose)

    _logger = get_logger(__name__)

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

    # Read bundle type from MANIFEST.
    try:
        bundle_type = _read_bundle_type(source_dir)
    except BundleLoadError as exc:
        _logger.error(
            "seed.cli.manifest_error",
            error_class="BundleLoadError",
            detail=str(exc),
        )
        print(f"ERROR: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    _logger.info("seed.cli.bundle_type_detected", bundle_type=bundle_type)

    namespaces = (args.only,) if args.only else _ALL_NAMESPACES

    try:
        exit_code = asyncio.run(
            _run(source_dir, namespaces, dry_run=args.dry_run, bundle_type=bundle_type)
        )
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
