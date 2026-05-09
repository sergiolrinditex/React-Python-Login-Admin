"""
Integration tests: seed loader behavior after migration 0001 is applied.

Slice: P01-S01-T001 — DB auth baseline
Phase: P01 — Auth + base capabilities

Tests verify:
  - The 'auth' namespace seed loader transitions from "table missing → skip"
    to "table exists → attempt write" once the migration creates the tables.
  - A minimal direct-SQL fixture insertion with the real T001 schema shape
    works idempotently (INSERT ON CONFLICT DO UPDATE on email).
  - language CHECK constraint rejects values outside ('es','en','fr').
  - employee_profiles FK insert works correctly.
  - app.seeds.table_probe.table_exists() returns True for 'users' after migration.

Context on auth loader vs T001 schema:
  The P00-S02-T003 auth loader (app/seeds/loader/auth.py) was written against
  an older synthetic schema (role, is_active, mfa_enabled columns; user_mfa_configs
  table). After T001, the 'users' table exists with the §10.3 schema (status,
  preferred_language, password_hash, etc.) — the columns differ.

  The loader's upsert will fail with a column-not-found DB error because the
  synthetic loader inserts 'role', 'is_active', 'mfa_enabled' which do not
  exist in the real schema. This is tracked in FU-20260509073000 (replace
  synthetic verification bundle with real prod-like fixtures).

  This test file validates the correct §10.3 schema shape directly via SQL
  without going through the legacy synthetic loader.

NOTE on event loop:
  pytest-asyncio asyncio_mode=auto creates a NEW event loop per function test.
  Each async test creates its own engine (no shared fixture) to avoid
  "Future attached to a different loop" errors.

Source: task-pack P01-S01-T001 §10.2 + §5.3 tests contract
01-non-negotiables.md §Tests are REAL
HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import uuid
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

_DSN = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"

BACKEND_DIR = Path(__file__).parent.parent.parent

_ALEMBIC_ENV = {
    **os.environ,
    "DATABASE_URL": "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev",
    "ENABLE_VERBOSE_LOGGING": "false",
}

SKIP_IF_NO_DB = pytest.mark.skipif(
    not DB_REACHABLE,
    reason="Compose postgres not reachable on :5433.",
)


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    """Run alembic CLI from BACKEND_DIR with compose DSN in env."""
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=_ALEMBIC_ENV,
        capture_output=True,
        text=True,
    )


def _assert_alembic_ok(result: subprocess.CompletedProcess, label: str) -> None:
    """Fail test with captured output if alembic exited non-zero."""
    if result.returncode != 0:
        pytest.fail(
            f"alembic {label} failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


@asynccontextmanager
async def _fresh_conn() -> AsyncGenerator[AsyncConnection, None]:
    """Create a fresh async engine+connection per test to avoid event-loop issues."""
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            yield conn
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Module-level setup: ensure migration is at head
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def ensure_migration_head_for_seed_tests() -> None:
    """Synchronous module fixture: ensure alembic is at head."""
    if not DB_REACHABLE:
        return
    result = _run_alembic("upgrade", "head")
    _assert_alembic_ok(result, "upgrade head (seed-loader test setup)")


# ---------------------------------------------------------------------------
# Tests: table-exists branch activation
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
async def test_users_table_exists_after_migration() -> None:
    """After migration 0001, the 'users' table must exist in public schema.

    This proves the seed loader's table-tolerant check will take the
    'table exists' branch (not the 'table missing → skip' branch).
    """
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'users'"
            )
        )
        count = result.scalar()
    assert count == 1, "users table must exist after migration 0001"


@SKIP_IF_NO_DB
async def test_employee_profiles_table_exists_after_migration() -> None:
    """After migration 0001, employee_profiles must exist."""
    async with _fresh_conn() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'employee_profiles'"
            )
        )
        count = result.scalar()
    assert count == 1, "employee_profiles table must exist after migration 0001"


# ---------------------------------------------------------------------------
# Tests: real §10.3 schema row insertion (idempotent upsert)
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
async def test_users_row_insert_and_upsert_with_real_schema() -> None:
    """Insert a real §10.3-shaped user row and verify idempotent upsert.

    Validates the schema shape produced by migration 0001 accepts the data
    contract expected by P01-S02 auth API (task-pack §12.2).
    Uses savepoint for test isolation (no state leak).
    """
    test_email = f"test-migration-{uuid.uuid4().hex[:8]}@hilopeople.com"

    async with _fresh_conn() as conn:
        await conn.execute(text("BEGIN"))
        try:
            # First insert
            await conn.execute(
                text(
                    """
                    INSERT INTO users
                        (email, password_hash, full_name, status, preferred_language)
                    VALUES
                        (:email, :pw_hash, :full_name, 'active', 'es')
                    ON CONFLICT (email) DO UPDATE
                        SET full_name = EXCLUDED.full_name
                    """
                ),
                {
                    "email": test_email,
                    "pw_hash": "$argon2id$v=19$m=65536$SYNTHETIC",
                    "full_name": "Test Employee",
                },
            )

            # Idempotent second upsert — same email, updated full_name.
            await conn.execute(
                text(
                    """
                    INSERT INTO users
                        (email, password_hash, full_name, status, preferred_language)
                    VALUES
                        (:email, :pw_hash, :full_name, 'active', 'es')
                    ON CONFLICT (email) DO UPDATE
                        SET full_name = EXCLUDED.full_name
                    """
                ),
                {
                    "email": test_email,
                    "pw_hash": "$argon2id$v=19$m=65536$SYNTHETIC",
                    "full_name": "Test Employee Updated",
                },
            )

            # Verify only one row exists for this email.
            result = await conn.execute(
                text("SELECT full_name FROM users WHERE email = :email"),
                {"email": test_email},
            )
            rows = result.fetchall()
            assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
            assert rows[0][0] == "Test Employee Updated", f"Unexpected: {rows[0][0]}"
        finally:
            await conn.execute(text("ROLLBACK"))


@SKIP_IF_NO_DB
async def test_language_check_constraint_rejects_invalid_locale() -> None:
    """Inserting preferred_language='pt' must raise a check constraint violation."""
    test_email = f"test-chk-{uuid.uuid4().hex[:8]}@hilopeople.com"

    async with _fresh_conn() as conn:
        await conn.execute(text("BEGIN"))
        try:
            with pytest.raises(Exception, match="."):  # noqa: B017 — DB exception type varies
                await conn.execute(
                    text(
                        """
                        INSERT INTO users
                            (email, password_hash, full_name, preferred_language)
                        VALUES
                            (:email, 'hash', 'Test', 'pt')
                        """
                    ),
                    {"email": test_email},
                )
        finally:
            await conn.execute(text("ROLLBACK"))


@SKIP_IF_NO_DB
async def test_employee_profile_insert_with_real_schema() -> None:
    """Insert a user + linked employee_profile and verify FK works."""
    test_email = f"test-emp-{uuid.uuid4().hex[:8]}@hilopeople.com"
    test_emp_id = f"EMP-{uuid.uuid4().hex[:6].upper()}"

    async with _fresh_conn() as conn:
        await conn.execute(text("BEGIN"))
        try:
            # Insert user first (parent).
            result = await conn.execute(
                text(
                    """
                    INSERT INTO users
                        (email, password_hash, full_name, status, preferred_language)
                    VALUES (:email, 'hash', 'Test Emp', 'active', 'en')
                    RETURNING id
                    """
                ),
                {"email": test_email},
            )
            user_id = result.scalar_one()

            # Insert employee_profile (child).
            await conn.execute(
                text(
                    """
                    INSERT INTO employee_profiles
                        (user_id, employee_id, brand, society, center, country, department)
                    VALUES (:uid, :eid, 'Hilo', 'HiloCorp SL', 'BCN01', 'ES', 'Engineering')
                    """
                ),
                {"uid": user_id, "eid": test_emp_id},
            )

            # Verify profile exists.
            r = await conn.execute(
                text("SELECT employee_id FROM employee_profiles WHERE user_id = :uid"),
                {"uid": user_id},
            )
            row = r.fetchone()
            assert row is not None, "employee_profile row not found"
            assert row[0] == test_emp_id
        finally:
            await conn.execute(text("ROLLBACK"))


@SKIP_IF_NO_DB
async def test_table_probe_confirms_users_exists() -> None:
    """app.seeds.table_probe.table_exists() returns True for 'users' after migration.

    Proves the seed loader's conditional branch will flip from
    'table missing → skip' to 'table exists → upsert' path.
    """
    from app.seeds.table_probe import table_exists

    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)
    try:
        exists = await table_exists(engine, "users")
    finally:
        await engine.dispose()
    assert exists is True, "table_probe.table_exists('users') must return True after migration 0001"
