"""
Integration tests for Alembic migration 0001 — auth baseline schema.

Slice: P01-S01-T001 — DB auth baseline
Phase: P01 — Auth + base capabilities

Tests verify:
  - upgrade() creates all 9 tables with correct shape.
  - Explicit indexes listed in task-pack §7.2 exist after upgrade.
  - FK ON DELETE semantics (CASCADE, SET NULL) declared correctly.
  - users_language_chk CHECK constraint rejects languages outside ('es','en','fr').
  - downgrade() drops all 9 tables and indexes cleanly.
  - Round-trip: upgrade → downgrade → upgrade exits cleanly.
  - alembic_version tracks revision "0001" after upgrade head.
  - Extensions pgcrypto and vector are present after upgrade.

All tests require real Postgres at 127.0.0.1:5433 (compose service hilo-postgres).
Tests are skipped automatically when the DB is not reachable.

NOTE on event loop / fixture scope:
  pytest-asyncio with asyncio_mode=auto creates a NEW event loop per function-scoped
  test. Module/session-scoped AsyncEngine fixtures share the engine across loops,
  causing "Future attached to a different loop" errors. The solution used here:
  each async test creates its own engine and closes it after use.  CLI round-trip
  tests use subprocess (no asyncio) and share the alembic state as long as tests
  run sequentially.

Source: task-pack P01-S01-T001 §10.2
01-non-negotiables.md §Tests are REAL
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_reachable() -> bool:
    """Return True if compose postgres is accessible on host port 5433."""
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=2):
            return True
    except OSError:
        return False


DB_REACHABLE = _db_reachable()

# DSN for direct asyncpg introspection.
_DSN = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"

# Backend directory (one level up from tests/).
BACKEND_DIR = Path(__file__).parent.parent.parent

# Env override so alembic uses correct DSN even if .env is absent/mismatched.
_ALEMBIC_ENV = {
    **os.environ,
    "DATABASE_URL": "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev",
    "ENABLE_VERBOSE_LOGGING": "false",
}

SKIP_IF_NO_DB = pytest.mark.skipif(
    not DB_REACHABLE,
    reason="Compose postgres not reachable on :5433 — set up DB before running integration tests.",
)


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
# Using a synchronous autouse fixture to do the alembic setup once per module.
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
    result = _run_alembic("upgrade", "head")
    _assert_alembic_ok(result, "upgrade head (module setup)")


# ---------------------------------------------------------------------------
# Tests: migration round-trip (CLI-level)
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
def test_alembic_round_trip_upgrade_downgrade_upgrade() -> None:
    """Round-trip: upgrade head → downgrade -1 → upgrade head must all exit 0.

    Verifies: migration is reversible without SQL errors or orphaned objects.
    This is the registry verify command (task-pack §10.1, MANDATORY).
    """
    r1 = _run_alembic("upgrade", "head")
    _assert_alembic_ok(r1, "upgrade head [1]")

    r2 = _run_alembic("downgrade", "-1")
    _assert_alembic_ok(r2, "downgrade -1")

    r3 = _run_alembic("upgrade", "head")
    _assert_alembic_ok(r3, "upgrade head [2]")


# ---------------------------------------------------------------------------
# Tests: DDL shape introspection after upgrade
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
async def test_all_twelve_tables_exist() -> None:
    """All 12 baseline tables (9 auth + 3 admin_ai) must be present after upgrade head.

    Updated from test_all_nine_tables_exist (P00-S02-T006): migration 0003 added
    ai_providers, ai_provider_credentials, ai_models. The test name and expected
    set reflect the accumulated schema through 0003.
    """
    expected_tables = {
        # Auth baseline (0001)
        "users",
        "employee_profiles",
        "roles",
        "permissions",
        "user_roles",
        "refresh_tokens",
        "mfa_totp_secrets",
        "password_reset_tokens",
        "audit_logs",
        # Admin AI (0003 — P00-S02-T006)
        "ai_providers",
        "ai_provider_credentials",
        "ai_models",
    }
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "AND table_name != 'alembic_version'"
            )
        )
        found = {row[0] for row in result.fetchall()}
    assert expected_tables == found, f"Expected {expected_tables}, got {found}"


@SKIP_IF_NO_DB
async def test_alembic_version_is_0003() -> None:
    """alembic_version table must contain exactly '0003' after upgrade head.

    Updated from test_alembic_version_is_0001 (P00-S02-T006): migration 0003
    (admin_ai tables) is now the head revision. 0002 is reserved for P02-S01-T001.
    """
    async with _fresh_conn() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        rows = result.fetchall()
    assert len(rows) == 1, f"Expected 1 row in alembic_version, got {rows}"
    assert rows[0][0] == "0003", f"Expected revision '0003', got '{rows[0][0]}'"


@SKIP_IF_NO_DB
async def test_extensions_present() -> None:
    """pgcrypto and vector extensions must be installed after upgrade head."""
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT extname FROM pg_extension "
                "WHERE extname IN ('pgcrypto', 'vector') "
                "ORDER BY extname"
            )
        )
        found = {row[0] for row in result.fetchall()}
    assert "pgcrypto" in found, "pgcrypto extension not found"
    assert "vector" in found, "vector extension not found"


@SKIP_IF_NO_DB
async def test_users_email_is_unique() -> None:
    """users.email must have a unique constraint (covers login lookup index)."""
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.table_constraints tc "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON tc.constraint_name = ccu.constraint_name "
                "WHERE tc.table_name = 'users' "
                "AND tc.constraint_type = 'UNIQUE' "
                "AND ccu.column_name = 'email'"
            )
        )
        count = result.scalar()
    assert count == 1, f"Expected unique constraint on users.email, got count={count}"


@SKIP_IF_NO_DB
async def test_users_language_check_constraint() -> None:
    """users_language_chk must reject preferred_language values outside es/en/fr."""
    async with _fresh_conn() as conn:
        await conn.execute(text("SAVEPOINT sp_chk"))
        try:
            with pytest.raises(Exception, match="."):  # noqa: B017 — DB exception type varies
                await conn.execute(
                    text(
                        "INSERT INTO users (email, password_hash, full_name, preferred_language) "
                        "VALUES ('test_chk_uniq@example.com', 'hash', 'Test', 'pt')"
                    )
                )
        finally:
            await conn.execute(text("ROLLBACK TO SAVEPOINT sp_chk"))


@SKIP_IF_NO_DB
async def test_employee_profiles_user_id_cascade() -> None:
    """employee_profiles.user_id FK must be ON DELETE CASCADE."""
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT rc.delete_rule "
                "FROM information_schema.referential_constraints rc "
                "JOIN information_schema.table_constraints tc "
                "  ON rc.constraint_name = tc.constraint_name "
                "WHERE tc.table_name = 'employee_profiles' "
                "AND rc.constraint_name = 'fk_employee_profiles_user_id_users'"
            )
        )
        row = result.fetchone()
    assert row is not None, "FK fk_employee_profiles_user_id_users not found"
    assert row[0] == "CASCADE", f"Expected CASCADE, got '{row[0]}'"


@SKIP_IF_NO_DB
async def test_audit_logs_actor_user_id_set_null() -> None:
    """audit_logs.actor_user_id FK must be ON DELETE SET NULL."""
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT rc.delete_rule "
                "FROM information_schema.referential_constraints rc "
                "JOIN information_schema.table_constraints tc "
                "  ON rc.constraint_name = tc.constraint_name "
                "WHERE tc.table_name = 'audit_logs' "
                "AND rc.constraint_name = 'fk_audit_logs_actor_user_id_users'"
            )
        )
        row = result.fetchone()
    assert row is not None, "FK fk_audit_logs_actor_user_id_users not found"
    assert row[0] == "SET NULL", f"Expected SET NULL, got '{row[0]}'"


@SKIP_IF_NO_DB
async def test_required_explicit_indexes_exist() -> None:
    """All explicit indexes from task-pack §7.2 must exist after upgrade head."""
    required_indexes = {
        "user_roles_role_id_idx",
        "refresh_tokens_user_id_idx",
        "refresh_tokens_active_expires_idx",
        "password_reset_tokens_user_id_idx",
        "password_reset_tokens_expires_idx",
        "audit_logs_actor_created_idx",
        "audit_logs_created_idx",
        "audit_logs_entity_idx",
    }
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' "
                "AND indexname = ANY(:names)"
            ),
            {"names": list(required_indexes)},
        )
        found = {row[0] for row in result.fetchall()}
    missing = required_indexes - found
    assert not missing, f"Missing indexes after upgrade: {sorted(missing)}"


@SKIP_IF_NO_DB
async def test_audit_logs_has_metadata_jsonb() -> None:
    """audit_logs.metadata column must exist and be of type jsonb."""
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT data_type, udt_name "
                "FROM information_schema.columns "
                "WHERE table_name = 'audit_logs' AND column_name = 'metadata'"
            )
        )
        row = result.fetchone()
    assert row is not None, "audit_logs.metadata column not found"
    assert row[1] == "jsonb", f"Expected jsonb, got '{row[1]}'"


@SKIP_IF_NO_DB
async def test_audit_logs_has_created_at_with_index() -> None:
    """audit_logs.created_at must exist and have an index (audit_logs_created_idx)."""
    async with _fresh_conn() as conn:
        # Column exists
        col_result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'audit_logs' AND column_name = 'created_at'"
            )
        )
        col_row = col_result.fetchone()
        assert col_row is not None, "audit_logs.created_at column not found"

        # Index exists
        idx_result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'audit_logs' AND indexname = 'audit_logs_created_idx'"
            )
        )
        idx = idx_result.fetchone()
    assert idx is not None, "audit_logs_created_idx not found"


# ---------------------------------------------------------------------------
# Tests: downgrade clean-up
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
async def test_downgrade_drops_all_tables_and_leaves_alembic_version() -> None:
    """After downgrade base, only alembic_version survives in public schema.

    Note: runs alembic downgrade base then checks schema, then re-upgrades.
    """
    # Ensure at head before downgrade test.
    r_up = _run_alembic("upgrade", "head")
    _assert_alembic_ok(r_up, "upgrade head before downgrade check")

    r_down = _run_alembic("downgrade", "base")
    _assert_alembic_ok(r_down, "downgrade base")

    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
        remaining = {row[0] for row in result.fetchall()}

    assert remaining == {"alembic_version"}, (
        f"Expected only alembic_version after downgrade base, found: {remaining}"
    )

    # Re-upgrade so subsequent tests don't fail.
    r_up2 = _run_alembic("upgrade", "head")
    _assert_alembic_ok(r_up2, "upgrade head after downgrade check (cleanup)")
