"""
Regression tests: SQLAlchemy engine.echo must be False permanently (CWE-532).

Slice: P00-S02-T012 — Disable SQLAlchemy echo to prevent Fernet token exposure
Phase: P00 — Scaffold + Design System

Leak vector (closed by P00-S02-T012 / FU-20260510044529):
  When create_async_engine(..., echo=True) is in effect, SQLAlchemy internally sets
  the sqlalchemy.engine stdlib logger to INFO level, causing every executed SQL
  statement and its bind-parameter tuple to be emitted. For the admin_ai seed, this
  exposes the Fernet ciphertext stored in ai_provider_credentials.encrypted_secret
  (gAAAAA...) — bypassing the structlog redaction processor (TECHNICAL_GUIDE §10.5).

  This is the "fourth layer" of the CWE-532 defense chain:
    T002 -> dropped exc_info=True in _probe_db
    T004 -> RichTracebackFormatter(show_locals=False) + extended _REDACTED_KEYS
    T009 -> silenced httpx/httpcore stdlib loggers
    T012 -> set engine echo=False permanently to prevent SA from enabling its logger

Tests:
  T1  engine.echo is False (unit: engine attribute, no DB needed)
  T2  sqlalchemy.engine logger receives no INFO records from an echo=True engine
      executing a query with Fernet ciphertext — and echo=False engine emits none
      (requires DB + Fernet; validates the contrast between echo=True and echo=False)
  T3  subprocess seed CLI admin_ai with ENABLE_VERBOSE_LOGGING=true emits no gAAAAA
      (requires DB + Fernet + VERIFICATION_GEMINI_API_KEY for the productive bundle)

Dependencies:
  - backend/app/core/db.py (fix site)
  - backend/app/seeds/bootstrap_verification_data.py (CLI under test in T3)
  - data/verification/admin_ai/ (real productive bundle, requires VERIFICATION_GEMINI_API_KEY)
  - pytest-asyncio asyncio_mode=auto (pytest.ini [asyncio_mode = auto])
  - sqlalchemy[asyncio] 2.0.49, cryptography 48.0.0
"""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).parent.parent.parent
REPO_ROOT = BACKEND_DIR.parent
BUNDLE_DIR = REPO_ROOT / "data" / "verification"

# ---------------------------------------------------------------------------
# Reachability guards (same pattern as test_seed_admin_ai_loader.py)
# ---------------------------------------------------------------------------


def _db_reachable() -> bool:
    """Return True if compose postgres is accessible on host port 5433."""
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=2):
            return True
    except OSError:
        return False


def _fernet_key_valid() -> bool:
    """Return True if a valid 32-byte Fernet key is in the environment.

    The placeholder 'dev-encryption-key-placeholder' is NOT valid Fernet.
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
    """Return True if VERIFICATION_GEMINI_API_KEY is set (required by productive bundle)."""
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
    reason="No valid Fernet ENCRYPTION_KEY set (placeholder is not valid).",
)
SKIP_IF_NO_GEMINI = pytest.mark.skipif(
    not GEMINI_KEY_SET,
    reason="VERIFICATION_GEMINI_API_KEY not set — productive admin_ai bundle test skipped.",
)

# ---------------------------------------------------------------------------
# T1 — engine.echo attribute is False (unit, no DB needed)
# ---------------------------------------------------------------------------


def test_engine_echo_is_false() -> None:
    """T1: app.core.db._get_engine() creates an engine with echo=False.

    Regression guard for FU-20260510044529 / P00-S02-T012. If a future
    developer sets echo=settings.enable_verbose_logging again, this test
    will fail in CI when ENABLE_VERBOSE_LOGGING=true.

    Resets the engine singleton before and after to avoid interference.
    """
    import app.core.config as config_module
    import app.core.db as db_module

    # Save and reset singleton so we get a clean engine creation
    prev_engine = db_module._engine
    prev_factory = db_module._session_factory
    db_module._engine = None
    db_module._session_factory = None
    config_module._settings = None

    # Set verbose logging ON — this is the scenario that triggered the bug
    old_val = os.environ.get("ENABLE_VERBOSE_LOGGING")
    os.environ["ENABLE_VERBOSE_LOGGING"] = "true"
    try:
        engine = db_module._get_engine()
        assert engine.echo is False, (
            "engine.echo must be permanently False (CWE-532 / FU-20260510044529 / "
            "P00-S02-T012). Do not re-enable echo=settings.enable_verbose_logging."
        )
    finally:
        # Restore
        db_module._engine = None
        db_module._session_factory = None
        config_module._settings = None
        if old_val is None:
            os.environ.pop("ENABLE_VERBOSE_LOGGING", None)
        else:
            os.environ["ENABLE_VERBOSE_LOGGING"] = old_val
        # Restore original singleton if it was set
        if prev_engine is not None:
            db_module._engine = prev_engine
        if prev_factory is not None:
            db_module._session_factory = prev_factory


# ---------------------------------------------------------------------------
# T2 — echo=True engine leaks gAAAAA; echo=False engine does not
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
@pytest.mark.asyncio
async def test_echo_false_vs_echo_true_fernet_leak() -> None:
    """T2: echo=True leaks Fernet ciphertext; echo=False does not.

    Runs two queries with the same Fernet-token bind parameter:
      (a) echo=True  engine — expects gAAAAA to appear in the SA log records.
      (b) echo=False engine — expects gAAAAA to NOT appear.

    The contrast proves that the fix is causally effective:
      - The log channel is the SA echo path.
      - echo=False is sufficient to close it.

    SA sets the sqlalchemy.engine logger level to INFO internally when echo=True.
    We capture via a root-level handler scoped to sqlalchemy.engine propagation.
    """
    from cryptography.fernet import Fernet
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    _DSN = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"

    raw_key = (
        os.environ.get("ENCRYPTION_KEY", "") or os.environ.get("PROVIDER_ENCRYPTION_KEY", "")
    )
    fernet = Fernet(raw_key.encode())
    simulated_token = fernet.encrypt(b"sk-fake-api-key-do-not-log").decode()
    assert simulated_token.startswith("gAAAAA"), "Fernet token must start with gAAAAA"

    class _CapturingHandler(logging.Handler):
        """Collect all log messages emitted through this handler."""

        def __init__(self) -> None:
            super().__init__()
            self.records: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.records.append(record.getMessage())

    # ---- (a) echo=True: proves the leak exists via the SA echo path ----
    handler_a = _CapturingHandler()
    sa_logger = logging.getLogger("sqlalchemy.engine")
    sa_logger.addHandler(handler_a)
    engine_a = create_async_engine(_DSN, echo=True, poolclass=NullPool)
    try:
        async with engine_a.connect() as conn:
            await conn.execute(text("SELECT :token AS x"), {"token": simulated_token})
    finally:
        sa_logger.removeHandler(handler_a)
        await engine_a.dispose()

    all_a = "\n".join(handler_a.records)
    assert "gAAAAA" in all_a, (
        "echo=True should have leaked the Fernet token in SA logs, but it did not. "
        "The test setup may be broken — check that the handler is attached correctly."
    )

    # ---- (b) echo=False: proves the fix closes the leak ----
    handler_b = _CapturingHandler()
    sa_logger.addHandler(handler_b)
    engine_b = create_async_engine(_DSN, echo=False, poolclass=NullPool)
    try:
        async with engine_b.connect() as conn:
            await conn.execute(text("SELECT :token AS x"), {"token": simulated_token})
    finally:
        sa_logger.removeHandler(handler_b)
        await engine_b.dispose()

    all_b = "\n".join(handler_b.records)
    assert "gAAAAA" not in all_b, (
        f"Fernet token leaked in sqlalchemy.engine log with echo=False!\n"
        f"Captured records:\n{all_b}\n"
        "This means echo=False was not effective. "
        "Check db.py — echo must be False permanently (FU-20260510044529)."
    )


# ---------------------------------------------------------------------------
# T3 — subprocess seed CLI with ENABLE_VERBOSE_LOGGING=true emits no gAAAAA
# ---------------------------------------------------------------------------


@SKIP_IF_NO_DB
@SKIP_IF_NO_FERNET
@SKIP_IF_NO_GEMINI
def test_seed_cli_verbose_no_gaaaaa_in_output() -> None:
    """T3: seed CLI admin_ai with ENABLE_VERBOSE_LOGGING=true emits no gAAAAA.

    Invokes the admin_ai seed CLI as a subprocess with full verbose logging
    enabled. Captures stdout+stderr and asserts zero occurrences of gAAAAA.

    Gold-standard acceptance test matching TECHNICAL_GUIDE §6.5 J103 Verify:
    "Run seed CLI with ENABLE_VERBOSE_LOGGING=true; grep for gAAAAA -> 0 matches."

    Requires: compose postgres :5433 up, valid ENCRYPTION_KEY, VERIFICATION_GEMINI_API_KEY.
    Skipped in CI when VERIFICATION_GEMINI_API_KEY is absent (same guard as T010 T6).
    """
    raw_key = (
        os.environ.get("ENCRYPTION_KEY", "") or os.environ.get("PROVIDER_ENCRYPTION_KEY", "")
    )
    env = {
        **os.environ,
        "DATABASE_URL": (
            "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
        ),
        "ENABLE_VERBOSE_LOGGING": "true",
        "ENCRYPTION_KEY": raw_key,
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.seeds.bootstrap_verification_data",
            "--source",
            str(BUNDLE_DIR),
            "--only",
            "admin_ai",
        ],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined_output = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"Seed CLI exited with rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # The core acceptance check (Acceptance #1 / Verify #2 from task pack §11.3):
    # Zero occurrences of gAAAAA Fernet ciphertext in the combined output.
    gaaaaa_count = combined_output.count("gAAAAA")
    assert gaaaaa_count == 0, (
        f"Found {gaaaaa_count} occurrence(s) of 'gAAAAA' Fernet ciphertext in CLI "
        f"output with ENABLE_VERBOSE_LOGGING=true!\n"
        f"This indicates SQLAlchemy echo is emitting bind parameters.\n"
        f"Check db.py — echo must be False permanently (FU-20260510044529 / CWE-532).\n"
        f"First 2000 chars of combined output:\n{combined_output[:2000]}"
    )
