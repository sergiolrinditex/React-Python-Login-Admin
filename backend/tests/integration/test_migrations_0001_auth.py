"""
Hilo People — Integration tests for migration 0001_auth_users_employee_audit.

Slice:  P01-S01-T001 — DB auth baseline
Phase:  P01 Auth + Data Foundation
Purpose: Verifies that migration 0001 creates all required tables with correct
         constraints, FKs, and cascade behavior. Tests both upgrade and downgrade
         idempotency against a real PostgreSQL instance.

         Tests cover:
           1. All 9 tables exist after upgrade head.
           2. CHECK users_language_chk rejects invalid preferred_language.
           3. UNIQUE users.email rejects duplicate email.
           4. ON DELETE CASCADE: deleting user cascades to employee_profiles,
              user_roles, refresh_tokens, mfa_totp_secrets, password_reset_tokens.
           5. ON DELETE SET NULL: deleting user sets audit_logs.actor_user_id = NULL.
           6. Downgrade drops all 9 tables (only alembic_version remains).

         All tests use a real Postgres DB — no mocks. Marked pytest.mark.integration.

Key deps:
  - pytest==9.0.2
  - sqlalchemy==2.0.49 (create_engine, text)
  - psycopg[binary]==3.3.4
  - alembic==1.18.4 (via CLI binary)
  - DATABASE_URL env var

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3
  - 01-non-negotiables.md §Tests are REAL
  - P01-S01-T001 task pack §10.3 recommended integration tests
  - WRITE_SET_EXTENSION: optional integration test justified by §13 task pack
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent.parent  # backend/
_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev"
)


# Locate alembic binary — prefer user Python path, fall back to PATH lookup.
def _find_alembic() -> str:
    """Find the alembic binary, searching common install locations."""
    candidates = [
        # User-level Python 3.11 (confirmed present)
        Path.home() / "Library" / "Python" / "3.11" / "bin" / "alembic",
        # Homebrew locations
        Path("/opt/homebrew/bin/alembic"),
        Path("/usr/local/bin/alembic"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "alembic"  # last resort — must be in PATH


_ALEMBIC_BIN = _find_alembic()


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Run alembic command with DATABASE_URL set in env."""
    env = {**os.environ, "DATABASE_URL": _DATABASE_URL}
    return subprocess.run(
        [_ALEMBIC_BIN, *args],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _get_sync_engine():
    """Create a synchronous SQLAlchemy engine for test assertions."""
    url = _DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    return create_engine(url, pool_pre_ping=True)


def _get_tables(engine) -> list[str]:
    """Return list of table names in public schema, sorted."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
        )
        return [row[0] for row in result]


# ---------------------------------------------------------------------------
# Fixture — ensure clean migration state before each test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_migrations():
    """Downgrade to base before each test (clean slate), upgrade head after (suite hygiene).

    CHANGED P04-S01-T010: teardown was `downgrade base`. Changed to `upgrade head` to prevent
    schema-teardown pollution of tests that run alphabetically after this file:
    test_model_test, test_password_reset, test_rag_*, test_users_me,
    test_vectorization_worker, test_verification_data_*. See FU-20260517220254.
    """
    _run_alembic("downgrade", "base")
    yield
    _run_alembic("upgrade", "head")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_upgrade_creates_all_9_tables():
    """After upgrade head, exactly 9 auth tables + alembic_version must exist."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed: {result.stderr}"

    engine = _get_sync_engine()
    tables = _get_tables(engine)
    engine.dispose()

    expected = {
        "alembic_version",
        "users",
        "employee_profiles",
        "roles",
        "permissions",
        "user_roles",
        "refresh_tokens",
        "mfa_totp_secrets",
        "password_reset_tokens",
        "audit_logs",
    }
    assert set(tables) == expected, f"Expected {expected}, got {set(tables)}"


@pytest.mark.integration
def test_check_language_constraint_rejects_invalid():
    """CHECK users_language_chk must reject preferred_language='de'."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    with engine.connect() as conn:
        with pytest.raises(Exception) as exc_info:
            conn.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name, preferred_language)"
                    " VALUES (:email, :pw, :name, :lang)"
                ),
                {
                    "email": "invalid.lang@test.com",
                    "pw": "somehash",
                    "name": "Test User",
                    "lang": "de",  # not in ('es','en','fr')
                },
            )
            conn.commit()
    engine.dispose()
    error_str = str(exc_info.value).lower()
    assert "users_language_chk" in error_str or "check" in error_str, (
        f"Expected CHECK constraint violation, got: {exc_info.value}"
    )


@pytest.mark.integration
def test_unique_email_constraint_rejects_duplicate():
    """UNIQUE users.email must reject duplicate email inserts."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    with engine.connect() as conn:
        # First insert — must succeed
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, full_name)"
                " VALUES (:email, :pw, :name)"
            ),
            {"email": "dup@test.com", "pw": "hash1", "name": "User A"},
        )
        conn.commit()
        # Second insert with same email — must fail
        with pytest.raises(Exception) as exc_info:
            conn.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name)"
                    " VALUES (:email, :pw, :name)"
                ),
                {"email": "dup@test.com", "pw": "hash2", "name": "User B"},
            )
            conn.commit()
    engine.dispose()
    error_str = str(exc_info.value).lower()
    assert "users_email_key" in error_str or "unique" in error_str, (
        f"Expected UNIQUE constraint violation, got: {exc_info.value}"
    )


@pytest.mark.integration
def test_on_delete_cascade_removes_child_rows():
    """ON DELETE CASCADE: deleting user must cascade to all child tables."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    user_id = str(uuid.uuid4())
    role_id = str(uuid.uuid4())

    with engine.connect() as conn:
        # Insert a user
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name)"
                " VALUES (:id, :email, :pw, :name)"
            ),
            {
                "id": user_id,
                "email": "cascade@test.com",
                "pw": "hash",
                "name": "Cascade User",
            },
        )
        # Insert employee_profile (FK CASCADE)
        conn.execute(
            text(
                "INSERT INTO employee_profiles"
                " (user_id, employee_id, brand, society, center, country, department)"
                " VALUES (:uid, :eid, :brand, :soc, :ctr, :cntry, :dept)"
            ),
            {
                "uid": user_id,
                "eid": "EMP-001",
                "brand": "Zara",
                "soc": "ITX",
                "ctr": "HQ",
                "cntry": "ES",
                "dept": "Tech",
            },
        )
        # Insert role and user_role (FK CASCADE)
        conn.execute(
            text("INSERT INTO roles (id, name) VALUES (:id, :name)"),
            {"id": role_id, "name": "user"},
        )
        conn.execute(
            text("INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid)"),
            {"uid": user_id, "rid": role_id},
        )
        # Insert refresh_token (FK CASCADE)
        conn.execute(
            text(
                "INSERT INTO refresh_tokens (user_id, token_hash, expires_at)"
                " VALUES (:uid, :th, now() + interval '1 hour')"
            ),
            {"uid": user_id, "th": "testhash1"},
        )
        # Insert mfa_totp_secrets (FK CASCADE)
        conn.execute(
            text(
                "INSERT INTO mfa_totp_secrets (user_id, secret_encrypted)"
                " VALUES (:uid, :sec)"
            ),
            {"uid": user_id, "sec": "encrypted_secret"},
        )
        # Insert password_reset_token (FK CASCADE)
        conn.execute(
            text(
                "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)"
                " VALUES (:uid, :th, now() + interval '1 hour')"
            ),
            {"uid": user_id, "th": "resethash1"},
        )
        conn.commit()

        # Delete user — cascade must clean up all child rows
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        conn.commit()

        # Assert all cascaded rows are gone
        for table, col in [
            ("employee_profiles", "user_id"),
            ("user_roles", "user_id"),
            ("refresh_tokens", "user_id"),
            ("mfa_totp_secrets", "user_id"),
            ("password_reset_tokens", "user_id"),
        ]:
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :uid"),  # noqa: S608
                {"uid": user_id},
            ).scalar()
            assert count == 0, (
                f"Expected 0 rows in {table} after CASCADE delete, got {count}"
            )

    engine.dispose()


@pytest.mark.integration
def test_audit_log_actor_set_null_on_user_delete():
    """ON DELETE SET NULL: deleting user sets audit_logs.actor_user_id = NULL."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    user_id = str(uuid.uuid4())

    with engine.connect() as conn:
        # Insert user
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name)"
                " VALUES (:id, :email, :pw, :name)"
            ),
            {
                "id": user_id,
                "email": "audit.setnull@test.com",
                "pw": "hash",
                "name": "Audit User",
            },
        )
        # Insert audit log with actor_user_id
        conn.execute(
            text(
                "INSERT INTO audit_logs (actor_user_id, action) VALUES (:uid, :action)"
            ),
            {"uid": user_id, "action": "user.login"},
        )
        conn.commit()

        # Get the audit log row for verification
        log_row = conn.execute(
            text("SELECT id, actor_user_id FROM audit_logs WHERE actor_user_id = :uid"),
            {"uid": user_id},
        ).fetchone()
        assert log_row is not None
        log_id = log_row[0]

        # Delete user — SET NULL must preserve the audit log row
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        conn.commit()

        # Assert audit_log row still exists but actor_user_id is NULL
        row = conn.execute(
            text("SELECT actor_user_id FROM audit_logs WHERE id = :id"),
            {"id": log_id},
        ).fetchone()
        assert row is not None, (
            "audit_logs row must NOT be deleted (SET NULL, not CASCADE)"
        )
        assert row[0] is None, (
            f"actor_user_id must be NULL after user deletion, got {row[0]}"
        )

    engine.dispose()


@pytest.mark.integration
def test_downgrade_removes_all_tables():
    """Downgrade -1 must remove all 9 tables created by this migration."""
    _run_alembic("upgrade", "head")
    result = _run_alembic("downgrade", "-1")
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"

    engine = _get_sync_engine()
    tables = _get_tables(engine)
    engine.dispose()

    # Only alembic_version should remain after downgrade
    assert tables == ["alembic_version"], (
        f"Expected only ['alembic_version'] after downgrade, got {tables}"
    )
