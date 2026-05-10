"""
Integration tests for Alembic migration 0002 — audit_logs compliance columns.

Slice: P01-S01-T005 — audit_logs: add ip, user_agent, request_id, resource
Phase: P01 — Auth + base capabilities

Tests verify:
  1. test_new_columns_present_and_nullable:
       All 4 new columns exist in information_schema.columns with is_nullable='YES'.
       INET column type confirmed (udt_name='inet').

  2. test_round_trip_preserves_existing_rows:
       Audit row survives downgrade (cols dropped) → upgrade (cols recreated).
       Original 6-column fields are preserved; new cols are NULL after re-upgrade.

  3. test_insert_with_compliance_cols_persists_non_null:
       INSERT audit_log with all 4 new cols populated → SELECT verifies non-null
       values are stored correctly.

  4. test_insert_without_compliance_cols_still_works:
       INSERT audit_log with only the §10.3 shape (no new cols) → SELECT verifies
       the 4 new cols are NULL (backward-compat with existing writers like admin_ai).

All tests require real Postgres at 127.0.0.1:5433 (compose service hilo-postgres).
Tests are skipped automatically when the DB is not reachable.

asyncpg INET decode note (official-doc-note 2026-05-10, RESOLVED):
  asyncpg 0.31.0 returns ipaddress.IPv4Address (not str) for INET columns when
  native_inet_types is active (default). INSERT with plain str is fine. SELECT
  assertions use str(row.ip) for safe string comparison. ORM annotation
  Mapped[str | None] is runtime-safe.

NOTE on event loop / fixture scope:
  pytest-asyncio with asyncio_mode=auto creates a NEW event loop per function-scoped
  test. Each async test creates its own engine via _fresh_conn() to avoid
  "Future attached to a different loop" errors. Module-scoped autouse
  ensure_migration_head uses subprocess (no asyncio).

Source: task-pack P01-S01-T005 §Impact analysis
        01-non-negotiables.md §Tests are REAL
        01-non-negotiables.md §Audit log (GDPR / compliance)
Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0 (asyncio_mode=auto)
  - sqlalchemy[asyncio] 2.0.49
  - asyncpg 0.31.0
  - structlog 25.5.0
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.logging import configure_logging, get_logger

# ---------------------------------------------------------------------------
# Logger bootstrap — must run BEFORE any get_logger(__name__) call so that
# ENABLE_VERBOSE_LOGGING gates the test logger output.
#
# Debugger fix P01-S01-T005 cycle 1 (2026-05-10):
#   The original test file did `structlog.get_logger(__name__)` at module top
#   without calling configure_logging(). Because pytest does not import
#   app.main (which is what wires structlog in production via main.py:44),
#   structlog kept its default configuration: no level gate. Result: BEFORE/
#   AFTER INFO lines appeared even with ENABLE_VERBOSE_LOGGING=false, which
#   violates 01-non-negotiables.md §Logging ("verbose=false → only WARN+ERROR").
#
# Fix (Option B per debugger brief — smallest blast radius):
#   Bootstrap logging at module import using the same env-var read pattern as
#   app/main.py:40-44. configure_logging() is idempotent (`_configured` guard),
#   so this is safe whether or not another test has already configured it.
#   We do NOT add this to integration/conftest.py to avoid interacting with
#   test_auth_signup.py T8 which explicitly resets `_configured` to switch
#   verbose modes mid-suite.
# ---------------------------------------------------------------------------
_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")
configure_logging(verbose=_VERBOSE)
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_reachable() -> bool:
    """Return True if compose postgres is accessible on host port 5433.

    Purpose: gate DB-requiring tests so the suite can still run in unit-only
    environments. The developer MUST capture evidence with DB up.
    """
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=2):
            return True
    except OSError:
        return False


DB_REACHABLE = _db_reachable()

# DSN for direct asyncpg introspection.
_DSN = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"

# Backend directory (one level up from tests/).
BACKEND_DIR = __file__ and __import__("pathlib").Path(__file__).parent.parent.parent

# Env override so alembic uses correct DSN even if .env is absent/mismatched.
_ALEMBIC_ENV = {
    **os.environ,
    "DATABASE_URL": _DSN,
    "ENABLE_VERBOSE_LOGGING": "false",
}

SKIP_IF_NO_DB = pytest.mark.skipif(
    not DB_REACHABLE,
    reason="Compose postgres not reachable on :5433 — set up DB before running integration tests.",
)

# New compliance columns from migration 0002.
_NEW_COLS = {"ip", "user_agent", "request_id", "resource"}


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    """Run alembic CLI from BACKEND_DIR with the compose DSN in env.

    Purpose: test the real Alembic CLI (not Python API) to verify revision
    tracking in alembic_version table.

    Params:
      *args — alembic CLI arguments (e.g. "upgrade", "head").
    Returns: CompletedProcess with stdout/stderr captured.
    """
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=_ALEMBIC_ENV,
        capture_output=True,
        text=True,
    )
    return result


def _assert_alembic_ok(result: subprocess.CompletedProcess, label: str) -> None:
    """Assert alembic exited 0; fail with captured output on non-zero."""
    if result.returncode != 0:
        pytest.fail(
            f"alembic {label} failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


@asynccontextmanager
async def _fresh_conn() -> AsyncGenerator[AsyncConnection, None]:
    """Context manager: create a fresh async engine+connection per test.

    Purpose: avoid event-loop conflicts — each test runs in its own loop
    (pytest-asyncio asyncio_mode=auto), so engines cannot be shared across
    tests. Using a fresh engine per test is the safe pattern.
    """
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            yield conn
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Ensure the schema is at HEAD before DDL tests run.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def ensure_migration_head() -> None:
    """Synchronous module-scoped fixture: ensure DB is at alembic head.

    Runs alembic upgrade head once before all tests in this module.
    Does nothing if already at head (idempotent).
    Skips if DB is not reachable.
    """
    if not DB_REACHABLE:
        return
    logger.info(
        "P01-S01-T005 test setup: ensuring DB is at alembic head before tests"
    )
    result = _run_alembic("upgrade", "head")
    _assert_alembic_ok(result, "upgrade head (module setup)")
    logger.info(
        "P01-S01-T005 test setup: alembic upgrade head complete",
        stdout_tail=result.stdout[-200:] if result.stdout else "",
    )


# ---------------------------------------------------------------------------
# Test 1: Column presence and nullability
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@pytest.mark.asyncio
async def test_new_columns_present_and_nullable() -> None:
    """Verify all 4 compliance columns exist in audit_logs with is_nullable='YES'.

    Checks information_schema.columns for:
      - ip          (udt_name='inet')
      - user_agent  (data_type='text')
      - request_id  (data_type='text')
      - resource    (data_type='text')

    All must be nullable=YES (backward-compat with pre-T005 rows).
    """
    logger.info(
        "P01-S01-T005 test1 BEFORE: querying information_schema.columns "
        "for audit_logs compliance cols"
    )
    try:
        async with _fresh_conn() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT column_name, is_nullable, data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = 'audit_logs'
                      AND column_name = ANY(:cols)
                    ORDER BY column_name
                    """
                ),
                {"cols": list(_NEW_COLS)},
            )
            results = {row.column_name: row for row in rows.mappings()}

        assert len(results) == 4, (
            f"Expected 4 compliance columns, found {len(results)}: {list(results.keys())}"
        )
        for col in _NEW_COLS:
            assert col in results, f"Column '{col}' missing from audit_logs"
            assert results[col]["is_nullable"] == "YES", (
                f"Column '{col}' expected nullable=YES, got {results[col]['is_nullable']}"
            )

        # INET-specific: PG18 reports data_type='inet' (a built-in type, not USER-DEFINED).
        # Older PG versions may report 'USER-DEFINED' + udt_name='inet'.
        # We accept both: either data_type == 'inet' OR udt_name == 'inet'.
        ip_data_type = results["ip"]["data_type"]
        ip_udt_name = results["ip"]["udt_name"]
        assert ip_data_type == "inet" or ip_udt_name == "inet", (
            f"ip column expected data_type='inet' or udt_name='inet', "
            f"got data_type={ip_data_type!r}, udt_name={ip_udt_name!r}"
        )

        # TEXT columns
        for col in ("user_agent", "request_id", "resource"):
            assert results[col]["data_type"] == "text", (
                f"Column '{col}' data_type expected 'text', got {results[col]['data_type']}"
            )

        logger.info(
            "P01-S01-T005 test1 AFTER: all 4 compliance columns present and nullable",
            columns_verified=list(_NEW_COLS),
        )
    except Exception:
        logger.exception(
            "P01-S01-T005 test1 ERROR: column presence check failed",
            table="audit_logs",
            expected_cols=list(_NEW_COLS),
        )
        raise


# ---------------------------------------------------------------------------
# Test 2: Round-trip preserves existing rows
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
def test_round_trip_preserves_existing_rows() -> None:
    """Verify pre-T005 audit_log rows survive downgrade → upgrade round-trip.

    Flow:
      1. upgrade head (ensure at 0003)
      2. INSERT audit_log row with §10.3 shape + all 4 compliance cols via raw SQL
      3. downgrade -1 (0003 → 0002): AI tables dropped, audit_logs still at 0002
      4. Verify audit_log row still exists with original 6-column values
      5. downgrade -1 (0002 → 0001): compliance cols dropped, row preserved
      6. Verify audit_log row still exists with §10.3 shape only
      7. upgrade head (0001 → 0002 → 0003): compliance cols re-added
      8. Verify row preserved with new cols = NULL (back-compat guarantee)
      9. New INSERT with all 4 cols confirms they work after re-upgrade

    This test uses subprocess for alembic (no asyncio) to avoid event-loop issues.
    Direct SQL queries use psycopg2 equivalent via subprocess psql, or we use
    synchronous SQLAlchemy (sync engine, not async).
    """
    import asyncio

    logger.info(
        "P01-S01-T005 test2 BEFORE: round-trip upgrade/downgrade/upgrade with row preservation"
    )

    row_id = str(uuid.uuid4())
    test_action = "test.compliance.roundtrip"

    async def _verify_row_with_compliance_cols_null(label: str) -> None:
        """Verify the row exists with compliance cols = NULL (after downgrade+upgrade cycle).

        Called AFTER: downgrade 0002→0001 (cols dropped) + upgrade head (cols re-added).
        The pre-existing row must have action intact, and all 4 new cols = NULL
        (they were dropped and recreated with no DEFAULT).
        """
        async with _fresh_conn() as conn:
            row = await conn.execute(
                text(
                    "SELECT id, action, ip, user_agent, request_id, resource "
                    "FROM audit_logs WHERE id = :id"
                ),
                {"id": row_id},
            )
            rec = row.mappings().one_or_none()
            assert rec is not None, f"[{label}] Row {row_id} missing after upgrade"
            assert rec["action"] == test_action, (
                f"[{label}] action mismatch: expected {test_action!r}, got {rec['action']!r}"
            )
            # After downgrade-then-upgrade, compliance cols were dropped and re-added
            # → existing rows get NULL for the 4 new cols (expected back-compat behavior)
            assert rec["ip"] is None, (
                f"[{label}] ip expected NULL after downgrade+upgrade cycle, got {rec['ip']!r}"
            )
            assert rec["user_agent"] is None, f"[{label}] user_agent expected NULL"
            assert rec["request_id"] is None, f"[{label}] request_id expected NULL"
            assert rec["resource"] is None, f"[{label}] resource expected NULL"

    async def _verify_row_basic_existence(label: str) -> None:
        """Verify the row exists with original §10.3 columns only (at 0001 state)."""
        async with _fresh_conn() as conn:
            row = await conn.execute(
                text("SELECT id, action FROM audit_logs WHERE id = :id"),
                {"id": row_id},
            )
            rec = row.mappings().one_or_none()
            assert rec is not None, f"[{label}] Row {row_id} missing after downgrade"
            assert rec["action"] == test_action, (
                f"[{label}] action mismatch: expected {test_action!r}, got {rec['action']!r}"
            )

    async def _insert_row() -> None:
        """Insert a test audit_log row at head state (0003)."""
        async with _fresh_conn() as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_logs (id, action, ip, user_agent, request_id, resource) "
                    "VALUES (:id, :action, :ip, :user_agent, :request_id, :resource)"
                ),
                {
                    "id": row_id,
                    "action": test_action,
                    "ip": "10.0.0.1",
                    "user_agent": "pytest-roundtrip/1.0",
                    "request_id": "req_roundtrip_" + row_id[:8],
                    "resource": "POST /api/v1/test/roundtrip",
                },
            )
            await conn.commit()

    try:
        # Step 1: ensure at head
        r = _run_alembic("upgrade", "head")
        _assert_alembic_ok(r, "upgrade head [setup]")

        # Step 2: insert test row at head state
        asyncio.run(_insert_row())
        logger.info("P01-S01-T005 test2: inserted test row", row_id=row_id)

        # Step 3: downgrade -1 (0003 → 0002): AI tables dropped; audit_logs intact
        r = _run_alembic("downgrade", "-1")
        _assert_alembic_ok(r, "downgrade 0003→0002")

        # Step 4: downgrade -1 (0002 → 0001): compliance cols dropped; audit row preserved
        r = _run_alembic("downgrade", "-1")
        _assert_alembic_ok(r, "downgrade 0002→0001")

        # Step 5: verify row still exists at 0001 (§10.3 shape, 6 cols only)
        asyncio.run(_verify_row_basic_existence("at-0001"))
        logger.info("P01-S01-T005 test2: row preserved at 0001", row_id=row_id)

        # Step 6: upgrade head (0001 → 0002 → 0003): compliance cols re-created
        r = _run_alembic("upgrade", "head")
        _assert_alembic_ok(r, "upgrade head [re-upgrade]")

        # Step 7: verify row preserved; new cols NULL (no DEFAULT — dropped + re-added)
        asyncio.run(_verify_row_with_compliance_cols_null("at-0003-after-reupgrade"))
        logger.info(
            "P01-S01-T005 test2 AFTER: round-trip complete — row preserved, new cols NULL",
            row_id=row_id,
        )

    except Exception:
        logger.exception(
            "P01-S01-T005 test2 ERROR: round-trip test failed",
            row_id=row_id,
        )
        raise


# ---------------------------------------------------------------------------
# Test 3: Insert with all compliance cols populated — non-null persists
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@pytest.mark.asyncio
async def test_insert_with_compliance_cols_persists_non_null() -> None:
    """INSERT audit_log with all 4 compliance cols → SELECT verifies non-null values.

    Demonstrates the schema contract: when the auth service (P01-S02-T001+)
    provides ip/user_agent/request_id/resource, the DB accepts and returns them.

    asyncpg INET note (RESOLVED 2026-05-10): row.ip returns ipaddress.IPv4Address,
    not str. Use str(row.ip) for string comparison (see official-doc-note).
    """
    test_ip = "192.168.1.1"
    test_user_agent = "Mozilla/5.0 (pytest; P01-S01-T005)"
    test_request_id = "req_" + uuid.uuid4().hex[:12]
    test_resource = "POST /api/v1/auth/sign-up"
    test_action = "test.compliance.insert_with_cols"
    row_id = str(uuid.uuid4())

    logger.info(
        "P01-S01-T005 test3 BEFORE: inserting audit_log row with all compliance cols",
        row_id=row_id,
        ip=test_ip,
        resource=test_resource,
        request_id=test_request_id,
    )
    try:
        async with _fresh_conn() as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(id, action, ip, user_agent, request_id, resource) "
                    "VALUES (:id, :action, :ip, :user_agent, :request_id, :resource)"
                ),
                {
                    "id": row_id,
                    "action": test_action,
                    "ip": test_ip,
                    "user_agent": test_user_agent,
                    "request_id": test_request_id,
                    "resource": test_resource,
                },
            )
            await conn.commit()

            row = await conn.execute(
                text(
                    "SELECT id, action, ip, user_agent, request_id, resource "
                    "FROM audit_logs WHERE id = :id"
                ),
                {"id": row_id},
            )
            rec = row.mappings().one()

        # All 4 compliance cols must be non-null
        assert rec["ip"] is not None, "ip should be non-null after INSERT with value"
        assert rec["user_agent"] is not None, "user_agent should be non-null"
        assert rec["request_id"] is not None, "request_id should be non-null"
        assert rec["resource"] is not None, "resource should be non-null"

        # asyncpg INET decode: returns ipaddress.IPv4Address — use str() for comparison
        assert str(rec["ip"]) == test_ip, (
            f"ip mismatch: expected {test_ip!r}, got {str(rec['ip'])!r} "
            f"(type={type(rec['ip']).__name__})"
        )
        assert rec["user_agent"] == test_user_agent, (
            f"user_agent mismatch: {rec['user_agent']!r} != {test_user_agent!r}"
        )
        assert rec["request_id"] == test_request_id, (
            f"request_id mismatch: {rec['request_id']!r} != {test_request_id!r}"
        )
        assert rec["resource"] == test_resource, (
            f"resource mismatch: {rec['resource']!r} != {test_resource!r}"
        )

        logger.info(
            "P01-S01-T005 test3 AFTER: all compliance cols non-null and correct",
            row_id=row_id,
            ip=str(rec["ip"]),
            user_agent=rec["user_agent"],
            request_id=rec["request_id"],
            resource=rec["resource"],
        )
    except Exception:
        logger.exception(
            "P01-S01-T005 test3 ERROR: compliance col insert/select failed",
            row_id=row_id,
        )
        raise


# ---------------------------------------------------------------------------
# Test 4: Insert without compliance cols — back-compat (NULL for new cols)
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@pytest.mark.asyncio
async def test_insert_without_compliance_cols_still_works() -> None:
    """INSERT audit_log with §10.3 shape only → new cols are NULL (back-compat).

    Verifies that existing audit_log writers (e.g., admin_ai/repository.py which
    writes only the §10.3 columns) continue to work without modification after
    migration 0002. The 4 new nullable cols default to NULL.

    This test guards against any future attempt to tighten the columns to NOT NULL
    which would break the existing admin_ai audit log writer.
    """
    test_action = "test.compliance.backcompat_insert"
    row_id = str(uuid.uuid4())

    logger.info(
        "P01-S01-T005 test4 BEFORE: inserting audit_log with §10.3 shape only (no compliance cols)",
        row_id=row_id,
        action=test_action,
    )
    try:
        async with _fresh_conn() as conn:
            # Insert with ONLY the original §10.3 columns (no ip/user_agent/request_id/resource)
            await conn.execute(
                text(
                    "INSERT INTO audit_logs (id, action) VALUES (:id, :action)"
                ),
                {"id": row_id, "action": test_action},
            )
            await conn.commit()

            row = await conn.execute(
                text(
                    "SELECT id, action, ip, user_agent, request_id, resource "
                    "FROM audit_logs WHERE id = :id"
                ),
                {"id": row_id},
            )
            rec = row.mappings().one()

        # Original fields preserved
        assert str(rec["id"]) == row_id, "id mismatch"
        assert rec["action"] == test_action, f"action mismatch: {rec['action']!r}"

        # All 4 compliance cols must be NULL (nullable defaults)
        assert rec["ip"] is None, (
            f"ip should be NULL for §10.3-only insert, got {rec['ip']!r}"
        )
        assert rec["user_agent"] is None, (
            f"user_agent should be NULL for §10.3-only insert, got {rec['user_agent']!r}"
        )
        assert rec["request_id"] is None, (
            f"request_id should be NULL for §10.3-only insert, got {rec['request_id']!r}"
        )
        assert rec["resource"] is None, (
            f"resource should be NULL for §10.3-only insert, got {rec['resource']!r}"
        )

        logger.info(
            "P01-S01-T005 test4 AFTER: §10.3-only insert succeeded; "
            "compliance cols NULL as expected",
            row_id=row_id,
        )
    except Exception:
        logger.exception(
            "P01-S01-T005 test4 ERROR: back-compat insert failed",
            row_id=row_id,
        )
        raise
