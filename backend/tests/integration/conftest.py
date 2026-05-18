"""
Hilo People — pytest conftest for backend/tests/integration/.

Slice:  P04-S01-T010 — Test isolation: migrations downgrade pollutes RAG/MCP
Phase:  P04 Harden
Purpose: Session-scoped safety net that guarantees the integration test suite
         begins and ends with `alembic upgrade head`. Defends against future
         tests that leave the DB in `base` or an intermediate state (the original
         bug from test_migrations_0001_auth.py::reset_migrations teardown, now
         fixed in that file; this conftest provides defense-in-depth).

         This fixture is ADDITIVE — individual tests may downgrade locally
         within their own scope provided their teardown restores head. The
         session-scope here means only 2 alembic calls per full pytest session,
         not 1 per test, so overhead is negligible (~3-5 s total).

Key deps:
  - alembic==1.18.4 (CLI binary, located via _find_alembic())
  - DATABASE_URL env var (postgresql+psycopg://...)
  - Python 3.12 subprocess (stdlib)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §9.1
  - 01-non-negotiables.md §Tests are REAL, §Logging
  - FU-20260517220254-test-isolation-test-migrations-downgrade-pollute
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import pytest

_LOG = logging.getLogger(__name__)

# backend/ directory — two levels up from this file (integration/conftest.py → tests/ → backend/).
_BACKEND_DIR = Path(__file__).resolve().parents[2]

_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("true", "1", "yes")


def _find_alembic() -> str:
    """Locate the alembic binary, preferring user-level Python 3.11 install.

    Searches common install locations in priority order. Falls back to
    bare 'alembic' assuming it is on PATH.

    Returns:
        Absolute path string to alembic binary (or 'alembic' as fallback).
    """
    candidates = [
        Path.home() / "Library" / "Python" / "3.11" / "bin" / "alembic",
        Path.home() / "Library" / "Python" / "3.12" / "bin" / "alembic",
        Path("/opt/homebrew/bin/alembic"),
        Path("/usr/local/bin/alembic"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "alembic"


def _run_alembic_upgrade_head() -> None:
    """Run `alembic upgrade head` from the backend directory.

    Logs BEFORE/AFTER under ENABLE_VERBOSE_LOGGING. Always logs WARNING on
    non-zero exit code (regardless of verbose flag).

    Raises:
        subprocess.CalledProcessError: If alembic exits with non-zero (check=True).
    """
    db_url = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev"
    )
    alembic_bin = _find_alembic()
    cmd = [alembic_bin, "upgrade", "head"]

    if _VERBOSE:
        _LOG.info(
            "[integration/conftest] BEFORE alembic upgrade head | cwd=%s | db=%s",
            _BACKEND_DIR,
            db_url.split("@")[-1],  # host/db only — no credentials in logs
        )

    result = subprocess.run(
        cmd,
        cwd=str(_BACKEND_DIR),
        env={**os.environ, "DATABASE_URL": db_url},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    if result.returncode != 0:
        _LOG.warning(
            "[integration/conftest] alembic upgrade head FAILED (rc=%d): %s",
            result.returncode,
            result.stderr.strip(),
        )
        # Re-raise as CalledProcessError so the fixture fails visibly.
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )

    if _VERBOSE:
        _LOG.info(
            "[integration/conftest] AFTER alembic upgrade head | rc=0 | stdout=%s",
            result.stdout.strip() or "(no output)",
        )


@pytest.fixture(scope="session", autouse=True)
def _integration_schema_head() -> None:  # type: ignore[return]
    """Guarantee DB is at alembic head BEFORE and AFTER the integration session.

    Session-scoped: runs exactly twice per full pytest invocation of
    backend/tests/integration (setup + teardown). This is a safety net —
    the primary fix lives in test_migrations_0001_auth.py::reset_migrations.

    Yields:
        None (setup/teardown only fixture).

    Raises:
        subprocess.CalledProcessError: If alembic upgrade head fails on setup.
            Teardown failure is logged as WARNING but does not re-raise.
    """
    # BEFORE: ensure schema is ready for all integration tests.
    _run_alembic_upgrade_head()

    yield

    # AFTER: restore head in case any test left DB in degraded state.
    # Teardown uses check=False via direct call to avoid aborting on post-suite errors.
    db_url = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev"
    )
    alembic_bin = _find_alembic()
    result = subprocess.run(
        [alembic_bin, "upgrade", "head"],
        cwd=str(_BACKEND_DIR),
        env={**os.environ, "DATABASE_URL": db_url},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        _LOG.warning(
            "[integration/conftest] post-session alembic upgrade head FAILED (rc=%d): %s",
            result.returncode,
            result.stderr.strip(),
        )
    elif _VERBOSE:
        _LOG.info(
            "[integration/conftest] post-session alembic upgrade head OK | rc=0",
        )
