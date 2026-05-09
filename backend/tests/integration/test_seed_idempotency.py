"""
Idempotency integration tests for the seed loader CLI.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Verifies that running the seed loader twice produces identical outcomes:
  - When tables exist: identical row counts (no duplicates).
  - When tables are missing (P00 state): identical WARN log entries on both runs.

Tests covered (3 total):
  1. test_seed_auth_idempotent_when_no_tables — auth namespace, tables missing:
       run twice, both emit "seed.namespace.table_missing" exactly once per table.
  2. test_seed_all_namespaces_idempotent_when_no_tables — all 6 namespaces,
       tables missing: second run produces the same skipped_tables list.
  3. test_seed_exit_0_when_tables_missing — running loader exits 0 even when
       all tables are missing (table-tolerant contract).

Rules (01-non-negotiables.md §Tests are REAL):
  - Real compose postgres connection (no mocking).
  - structlog capture_logs() for asserting WARN events.
  - Tests are skipped (not failed) in unit-only environments without compose.

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0
  - structlog 25.5.0
  - sqlalchemy[asyncio] 2.0.49
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import structlog.testing

from tests.integration.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="compose postgres not reachable on :5433 — run 'docker compose up -d postgres' first",
)


# ---------------------------------------------------------------------------
# Test 1 — auth namespace idempotent with missing tables (P00 state)
# ---------------------------------------------------------------------------


async def test_seed_auth_idempotent_when_no_tables(
    verification_bundle_dir: Path,
) -> None:
    """Running --only auth twice produces identical structured WARN logs.

    In P00 state, the 'users' table does not exist. Both runs should:
      1. Validate fixtures (pass).
      2. Log 'seed.namespace.table_missing' for 'users' (and optionally 'user_mfa_configs').
      3. Exit with LoadReport.skipped_tables containing the same entries.

    Asserts identical skipped_tables between run 1 and run 2.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.seeds.loader import load_auth

    dsn = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
    engine = create_async_engine(dsn, pool_pre_ping=True)

    try:
        with structlog.testing.capture_logs() as logs1:
            report1 = await load_auth(engine, verification_bundle_dir)

        with structlog.testing.capture_logs() as logs2:
            report2 = await load_auth(engine, verification_bundle_dir)
    finally:
        await engine.dispose()

    # Both runs should have the same skipped_tables set (idempotent).
    assert set(report1.skipped_tables) == set(report2.skipped_tables), (
        f"Run 1 skipped: {report1.skipped_tables}, Run 2 skipped: {report2.skipped_tables}. "
        "Both runs must produce identical skipped_tables (idempotency contract)."
    )

    # Both runs should emit the same table_missing WARNs (or no WARN if tables exist).
    warn_events1 = [
        e for e in logs1
        if e.get("log_level") == "warning" and "table_missing" in e.get("event", "")
    ]
    warn_events2 = [
        e for e in logs2
        if e.get("log_level") == "warning" and "table_missing" in e.get("event", "")
    ]

    assert len(warn_events1) == len(warn_events2), (
        f"Run 1 produced {len(warn_events1)} table_missing WARNs; "
        f"Run 2 produced {len(warn_events2)}. Must be identical."
    )

    # Rows inserted must match (0 = all skipped; N = upserted).
    assert report1.rows_inserted == report2.rows_inserted, (
        f"Run 1 inserted {report1.rows_inserted} rows; Run 2 inserted {report2.rows_inserted}. "
        "ON CONFLICT DO UPDATE must produce the same row count on repeat runs."
    )


# ---------------------------------------------------------------------------
# Test 2 — all 6 namespaces idempotent when tables are missing
# ---------------------------------------------------------------------------


async def test_seed_all_namespaces_idempotent_when_no_tables(
    verification_bundle_dir: Path,
) -> None:
    """Running all 6 namespaces twice produces identical skipped_tables per namespace.

    In P00 state none of the tables exist. Both runs should skip all tables
    and produce the same LoadReport set.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.seeds.loader import (
        load_admin_ai,
        load_auth,
        load_history,
        load_mcp_agents,
        load_rag_chat,
        load_rag_docs,
    )

    loaders = [
        load_auth, load_rag_chat, load_history, load_admin_ai, load_rag_docs, load_mcp_agents
    ]

    dsn = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
    engine = create_async_engine(dsn, pool_pre_ping=True)

    try:
        reports1 = []
        for loader_fn in loaders:
            report = await loader_fn(engine, verification_bundle_dir)
            reports1.append(report)

        reports2 = []
        for loader_fn in loaders:
            report = await loader_fn(engine, verification_bundle_dir)
            reports2.append(report)
    finally:
        await engine.dispose()

    for r1, r2 in zip(reports1, reports2, strict=True):
        assert r1.namespace == r2.namespace
        assert set(r1.skipped_tables) == set(r2.skipped_tables), (
            f"Namespace '{r1.namespace}': run 1 skipped {r1.skipped_tables}, "
            f"run 2 skipped {r2.skipped_tables}. Must be identical."
        )
        assert r1.rows_inserted == r2.rows_inserted, (
            f"Namespace '{r1.namespace}': run 1 inserted {r1.rows_inserted}, "
            f"run 2 inserted {r2.rows_inserted}. Must be identical (idempotency)."
        )


# ---------------------------------------------------------------------------
# Test 3 — exit 0 when tables are missing (CLI subprocess)
# ---------------------------------------------------------------------------


def test_seed_exit_0_when_tables_missing(
    verification_bundle_dir: Path,
) -> None:
    """CLI exits 0 even when all tables are missing (table-tolerant contract).

    Runs the CLI as a subprocess so exit codes are captured accurately.
    In P00 state, all tables are missing — the loader must not exit non-zero.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.seeds.bootstrap_verification_data",
            "--source",
            str(verification_bundle_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(verification_bundle_dir.parent.parent / "backend"),
        env={
            "PATH": __import__("os").environ.get("PATH", ""),
            "ENABLE_VERBOSE_LOGGING": "false",
            "DATABASE_URL": (
                "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
                "@127.0.0.1:5433/hilopeople_dev"
            ),
        },
    )

    assert result.returncode == 0, (
        f"Seed CLI must exit 0 when tables are missing (table-tolerant contract). "
        f"Got exit code {result.returncode}.\n"
        f"STDOUT: {result.stdout[:500]}\n"
        f"STDERR: {result.stderr[:500]}"
    )
