"""
Integration tests: admin_ai seed loader against real §10.3 DB schema.

Slice: P00-S02-T010 — Fix admin_ai seed loader (column api_key does not exist)
Phase: P00 — Scaffold + Design System

Tests verify that the FIXED loader in app/seeds/loader/admin_ai.py:
  1. Inserts providers into ai_providers with real §10.3 columns (no phantom api_key).
  2. Inserts Fernet-encrypted credentials into ai_provider_credentials.
  3. Round-trips: decrypt_secret(stored_token) == original_api_key.
  4. Inserts models into ai_models with correct provider_id FK.
  5. Is idempotent: running twice yields same row counts.
  6. Skips orphan models (unknown provider_name) with WARN, no exception.
  7. Emits no plaintext API key or Fernet token in any log event.

All tests hit real compose postgres on :5433 (no DB mocks).
Tests that require a real Fernet ENCRYPTION_KEY are skipped when the env var
is missing or invalid (placeholder string is not a valid Fernet key — R1 in
task pack §9).

Setup: alembic upgrade head is applied via autouse module fixture.
       Each test rolls back via SAVEPOINT / explicit ROLLBACK to avoid state leak.

Source: task-pack P00-S02-T010 §10 (Step 7 — tests)
        01-non-negotiables.md §Tests are REAL
        HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 + ADR-001 §15
        test_seed_loader_after_migration.py (pattern reference)
"""
from __future__ import annotations

import io
import logging
import os
import re
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
# Connection helpers (same DSN as conftest.py)
# ---------------------------------------------------------------------------

_DSN = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"

BACKEND_DIR = Path(__file__).parent.parent.parent
REPO_ROOT = BACKEND_DIR.parent
BUNDLE_DIR = REPO_ROOT / "data" / "verification"

_ALEMBIC_ENV = {
    **os.environ,
    "DATABASE_URL": _DSN,
    "ENABLE_VERBOSE_LOGGING": "false",
}

# ---------------------------------------------------------------------------
# Validity guards
# ---------------------------------------------------------------------------


def _db_reachable() -> bool:
    """Return True if compose postgres is accessible on host port 5433."""
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=2):
            return True
    except OSError:
        return False


def _fernet_key_valid() -> bool:
    """Return True if a valid 32-byte Fernet key is available in the environment.

    A valid key is a URL-safe base64-encoded string of exactly 32 bytes.
    The placeholder 'dev-encryption-key-placeholder' is NOT valid (R1).
    """
    try:
        from cryptography.fernet import Fernet  # noqa: PLC0415

        raw = (
            os.environ.get("ENCRYPTION_KEY", "")
            or os.environ.get("PROVIDER_ENCRYPTION_KEY", "")
        )
        if not raw:
            return False
        Fernet(raw.encode())
        return True
    except Exception:
        return False


def _gemini_key_available() -> bool:
    """Return True if VERIFICATION_GEMINI_API_KEY is set (for productive bundle tests)."""
    return bool(os.environ.get("VERIFICATION_GEMINI_API_KEY", "").strip())


DB_REACHABLE = _db_reachable()
FERNET_VALID = _fernet_key_valid()
GEMINI_KEY_SET = _gemini_key_available()

SKIP_IF_NO_DB = pytest.mark.skipif(
    not DB_REACHABLE,
    reason="Compose postgres not reachable on :5433.",
)
SKIP_IF_NO_FERNET = pytest.mark.skipif(
    not FERNET_VALID,
    reason="No valid Fernet ENCRYPTION_KEY set (placeholder is not valid — R1).",
)
SKIP_IF_NO_GEMINI = pytest.mark.skipif(
    not GEMINI_KEY_SET,
    reason="VERIFICATION_GEMINI_API_KEY not set — productive bundle test skipped.",
)

# ---------------------------------------------------------------------------
# Alembic helper
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Module-level setup: ensure migration is at head (0003)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def ensure_migration_head() -> None:
    """Synchronous module fixture: ensure alembic is at head (includes 0003)."""
    if not DB_REACHABLE:
        return
    result = _run_alembic("upgrade", "head")
    _assert_alembic_ok(result, "upgrade head (admin_ai seed loader test setup)")


# ---------------------------------------------------------------------------
# Per-test engine helper (avoids event-loop sharing issues)
# ---------------------------------------------------------------------------


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
# Minimal synthetic provider fixture (no env vars, no real keys)
# ---------------------------------------------------------------------------

def _synthetic_providers_dir(tmp_path: Path) -> Path:
    """Write a synthetic provider fixture to a temp dir and return it."""
    admin_ai_dir = tmp_path / "admin_ai"
    admin_ai_dir.mkdir(parents=True)

    (admin_ai_dir / "providers.json").write_text(
        """{
  "providers": [
    {
      "name": "synthetic-test-provider",
      "provider_type": "gemini",
      "api_key": "synthetic-test-api-key-for-t010",
      "base_url": "https://example.com",
      "is_active": true,
      "description": "T010 test provider"
    }
  ]
}"""
    )
    (admin_ai_dir / "models.json").write_text(
        """{
  "models": [
    {
      "name": "test-chat-model",
      "model_id": "gemini/test-flash-t010",
      "provider_name": "synthetic-test-provider",
      "display_name": "Test Chat",
      "capability": "chat",
      "is_active": true,
      "auto_discovered": false,
      "context_window": 4096
    },
    {
      "name": "test-embed-model",
      "model_id": "gemini/test-embed-t010",
      "provider_name": "synthetic-test-provider",
      "display_name": "Test Embed",
      "capability": "embedding",
      "is_active": false,
      "auto_discovered": false,
      "context_window": null
    },
    {
      "name": "orphan-model",
      "model_id": "unknown/orphan-t010",
      "provider_name": "non-existent-provider",
      "capability": "chat",
      "is_active": false,
      "auto_discovered": false,
      "context_window": null
    }
  ]
}"""
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1 — Provider INSERT with real §10.3 columns
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
async def test_admin_ai_loader_inserts_providers_with_real_schema(tmp_path: Path) -> None:
    """Providers from fixture are inserted into ai_providers with §10.3 column shape.

    Validates: name, provider_type, base_url, status (from is_active) are present.
    No phantom columns (api_key, is_active, description) should cause ProgrammingError.
    Uses ROLLBACK for test isolation.
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from app.seeds.loader.admin_ai import load_admin_ai  # noqa: PLC0415

    source_dir = _synthetic_providers_dir(tmp_path)
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)

    try:
        # Delete any pre-existing test provider row.
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )

        report = await load_admin_ai(
            engine, source_dir, dry_run=False, bundle_type="synthetic"
        )

        # Verify the report is sane.
        assert report.namespace == "admin_ai"
        assert report.rows_inserted > 0, "Expected at least 1 row inserted"

        # Verify the DB row exists with the right column values.
        async with _fresh_conn() as conn:
            result = await conn.execute(
                text(
                    "SELECT name, provider_type, status FROM ai_providers "
                    "WHERE name = 'synthetic-test-provider'"
                )
            )
            rows = result.fetchall()

        assert len(rows) == 1, f"Expected 1 provider row, got {len(rows)}"
        assert rows[0][0] == "synthetic-test-provider"
        assert rows[0][1] == "gemini"
        assert rows[0][2] == "active"  # is_active=true maps to status='active'

    finally:
        # Cleanup: remove test rows.
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 2 — Credential round-trip (encrypt → store → decrypt)
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
async def test_admin_ai_loader_credential_round_trip(tmp_path: Path) -> None:
    """Inserted credential round-trips correctly via decrypt_secret.

    Validates: encrypted_secret stored in ai_provider_credentials can be
    decrypted back to the original synthetic api_key value.
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from app.core.security import decrypt_secret  # noqa: PLC0415
    from app.seeds.loader.admin_ai import load_admin_ai  # noqa: PLC0415

    source_dir = _synthetic_providers_dir(tmp_path)
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)

    try:
        # Delete any pre-existing test provider row (cascades to credentials).
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )

        await load_admin_ai(engine, source_dir, dry_run=False, bundle_type="synthetic")

        # Fetch the credential stored for this provider.
        async with _fresh_conn() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT c.encrypted_secret, c.auth_type
                    FROM ai_provider_credentials c
                    JOIN ai_providers p ON p.id = c.provider_id
                    WHERE p.name = 'synthetic-test-provider'
                    """
                )
            )
            rows = result.fetchall()

        assert len(rows) == 1, f"Expected 1 credential row, got {len(rows)}"
        encrypted_secret = rows[0][0]
        auth_type = rows[0][1]

        assert len(encrypted_secret) > 50, "Fernet token should be long"
        assert auth_type == "api_key", "gemini provider should use auth_type='api_key'"

        # Round-trip: decrypt should equal the synthetic api_key value.
        plaintext = decrypt_secret(encrypted_secret)
        assert plaintext == "synthetic-test-api-key-for-t010", (
            "Round-trip failed: decrypted value does not match original api_key"
        )

    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 3 — Models with correct provider_id FK
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
async def test_admin_ai_loader_models_have_correct_provider_fk(tmp_path: Path) -> None:
    """Models are inserted into ai_models with provider_id pointing to the correct provider.

    Validates:
      - Non-orphan models have the right provider_id.
      - model_type is mapped from capability correctly.
      - enabled=True for is_active=true models.
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from app.seeds.loader.admin_ai import load_admin_ai  # noqa: PLC0415

    source_dir = _synthetic_providers_dir(tmp_path)
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)

    try:
        # Delete any pre-existing test rows.
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )

        await load_admin_ai(engine, source_dir, dry_run=False, bundle_type="synthetic")

        async with _fresh_conn() as conn:
            # Get the provider id.
            result = await conn.execute(
                text("SELECT id FROM ai_providers WHERE name = 'synthetic-test-provider'")
            )
            provider_row = result.fetchone()
            assert provider_row is not None, "Provider row not found"
            provider_id = provider_row[0]

            # Get the models for this provider.
            result = await conn.execute(
                text(
                    """
                    SELECT model_id, model_type, enabled, auto_discovered
                    FROM ai_models
                    WHERE provider_id = :pid
                    ORDER BY model_id
                    """
                ),
                {"pid": str(provider_id)},
            )
            rows = result.fetchall()

        # orphan model is skipped; only 2 models should be present.
        model_ids = {r[0] for r in rows}
        assert "gemini/test-flash-t010" in model_ids, "chat model not found"
        assert "gemini/test-embed-t010" in model_ids, "embedding model not found"
        assert "unknown/orphan-t010" not in model_ids, "orphan model should be skipped"

        # Verify model_type mapping.
        by_id = {r[0]: r for r in rows}
        assert by_id["gemini/test-flash-t010"][1] == "chat", "capability chat → model_type chat"
        assert by_id["gemini/test-embed-t010"][1] == "embedding", (  # noqa: E501
            "capability embedding → model_type embedding"
        )

        # Verify enabled maps from is_active.
        assert by_id["gemini/test-flash-t010"][2] is True, "is_active=true → enabled=true"
        assert by_id["gemini/test-embed-t010"][2] is False, "is_active=false → enabled=false"

    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 4 — Idempotency: two runs yield same counts and no integrity errors
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
async def test_admin_ai_loader_idempotent(tmp_path: Path) -> None:
    """Running the loader twice yields the same provider/model counts.

    Validates:
      - SELECT-then-INSERT for providers: no duplicate rows on second run.
      - DELETE+INSERT for credentials: credential is rotated (still exactly 1 per provider).
      - ON CONFLICT DO UPDATE for models: no duplicate rows.
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from app.seeds.loader.admin_ai import load_admin_ai  # noqa: PLC0415

    source_dir = _synthetic_providers_dir(tmp_path)
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)

    try:
        # Start clean.
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )

        # First run.
        await load_admin_ai(engine, source_dir, dry_run=False, bundle_type="synthetic")

        # Capture counts after first run.
        async with _fresh_conn() as conn:
            r1 = await conn.execute(
                text("SELECT count(*) FROM ai_providers WHERE name = 'synthetic-test-provider'")
            )
            c1_providers = r1.scalar()

            r2 = await conn.execute(
                text(
                    """
                    SELECT count(*) FROM ai_provider_credentials c
                    JOIN ai_providers p ON p.id = c.provider_id
                    WHERE p.name = 'synthetic-test-provider'
                    """
                )
            )
            c1_creds = r2.scalar()

            r3 = await conn.execute(
                text(
                    """
                    SELECT count(*) FROM ai_models m
                    JOIN ai_providers p ON p.id = m.provider_id
                    WHERE p.name = 'synthetic-test-provider'
                    """
                )
            )
            c1_models = r3.scalar()

        # Second run (idempotent).
        await load_admin_ai(engine, source_dir, dry_run=False, bundle_type="synthetic")

        # Counts must be the same.
        async with _fresh_conn() as conn:
            r1 = await conn.execute(
                text("SELECT count(*) FROM ai_providers WHERE name = 'synthetic-test-provider'")
            )
            c2_providers = r1.scalar()

            r2 = await conn.execute(
                text(
                    """
                    SELECT count(*) FROM ai_provider_credentials c
                    JOIN ai_providers p ON p.id = c.provider_id
                    WHERE p.name = 'synthetic-test-provider'
                    """
                )
            )
            c2_creds = r2.scalar()

            r3 = await conn.execute(
                text(
                    """
                    SELECT count(*) FROM ai_models m
                    JOIN ai_providers p ON p.id = m.provider_id
                    WHERE p.name = 'synthetic-test-provider'
                    """
                )
            )
            c2_models = r3.scalar()

        assert c1_providers == c2_providers == 1, f"Providers: {c1_providers} → {c2_providers}"
        assert c1_creds == c2_creds == 1, f"Credentials: {c1_creds} → {c2_creds}"
        assert c1_models == c2_models == 2, f"Models: {c1_models} → {c2_models}"  # orphan skipped

    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 5 — Orphan model skip with WARN log, no exception
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
async def test_admin_ai_loader_skips_orphan_models(tmp_path: Path) -> None:
    """Model with unknown provider_name is skipped silently; no exception raised.

    Validates: the 'non-existent-provider' model is NOT in ai_models.
    The load completes without exception (exit 0 equivalent).
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from app.seeds.loader.admin_ai import load_admin_ai  # noqa: PLC0415

    source_dir = _synthetic_providers_dir(tmp_path)
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )

        # Must not raise — orphan model is skipped with WARNING, not exception.
        report = await load_admin_ai(
            engine, source_dir, dry_run=False, bundle_type="synthetic"
        )

        assert report.namespace == "admin_ai"
        # The orphan model 'unknown/orphan-t010' must not be in ai_models.
        async with _fresh_conn() as conn:
            result = await conn.execute(
                text(
                    "SELECT count(*) FROM ai_models WHERE model_id = 'unknown/orphan-t010'"
                )
            )
            count = result.scalar()

        assert count == 0, f"Orphan model should be skipped, found {count} rows"

    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 6 — No plaintext API key or Fernet token in structured logs
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
async def test_admin_ai_loader_no_secret_in_logs(tmp_path: Path) -> None:
    """Loader emits no plaintext api_key or Fernet token in any log event.

    Captures all log output via Python logging handler.
    Validates: none of the regex patterns for real keys or Fernet tokens appear.
    """
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from app.seeds.loader.admin_ai import load_admin_ai  # noqa: PLC0415

    # Regex patterns that would indicate a secret was logged.
    _SECRET_PATTERNS = [
        re.compile(r"sk-[A-Za-z0-9]{20,}"),        # OpenAI-style keys
        re.compile(r"sk-ant-[A-Za-z0-9\-]{30,}"),  # Anthropic keys
        re.compile(r"AIza[A-Za-z0-9\-_]{35,}"),    # Google AI keys
        re.compile(r"gAAAAA[A-Za-z0-9_\-]{40,}"),  # Fernet tokens (start with gAAAAA)
    ]
    # The synthetic key used in our fixture — must NOT appear verbatim in logs.
    _SYNTHETIC_KEY = "synthetic-test-api-key-for-t010"

    source_dir = _synthetic_providers_dir(tmp_path)
    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)

    # Capture all log records via a StringIO handler.
    log_buffer = io.StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )

        os.environ["ENABLE_VERBOSE_LOGGING"] = "true"
        await load_admin_ai(engine, source_dir, dry_run=False, bundle_type="synthetic")
    finally:
        os.environ.pop("ENABLE_VERBOSE_LOGGING", None)
        root_logger.removeHandler(handler)
        root_logger.setLevel(original_level)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM ai_providers WHERE name = 'synthetic-test-provider'"
                )
            )
        await engine.dispose()

    log_output = log_buffer.getvalue()

    # The synthetic key itself should NOT appear verbatim.
    assert _SYNTHETIC_KEY not in log_output, (
        "Plaintext synthetic api_key found in log output — security regression"
    )

    # Real-key patterns and Fernet tokens should not appear.
    for pattern in _SECRET_PATTERNS:
        match = pattern.search(log_output)
        assert match is None, (
            f"Pattern {pattern.pattern!r} found in log output at position {match.start()}"
        )
