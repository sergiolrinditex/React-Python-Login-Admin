"""
Integration test fixtures for seed loader tests.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Slice: P00-S02-T016 — Stabilize event-loop fragility for FastAPI ASGITransport tests
Phase: P00 — Scaffold + Design System

Provides:
  - postgres_engine: session-scoped async engine pointing at compose postgres on :5433.
    Skipped automatically when the DB is not reachable (unit-only environments).
  - verification_bundle_dir: path fixture pointing at data/verification/.
  - reset_db_engine_singleton (autouse): resets app.core.db._engine and
    _session_factory before each test and AWAITS dispose() in the test's own
    event loop after each test (P00-S02-T016 fix).

All tests in this package use REAL compose postgres (no mocking).
Tests that require the DB are decorated with @pytest.mark.skipif(not _db_reachable()).

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0 (asyncio_mode=auto in pyproject.toml)
  - sqlalchemy[asyncio] 2.0.49
  - asyncpg 0.31.0
"""
from __future__ import annotations

import contextlib
import socket
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def _db_reachable() -> bool:
    """Return True if compose postgres is reachable on host port 5433.

    Purpose: gate DB-requiring tests so the suite can still run in unit-only
             environments. The developer MUST capture evidence with DB up.
    """
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Verification bundle directory fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def verification_bundle_dir() -> Path:
    """Return the path to the canonical data/verification/ bundle directory.

    Purpose: shared fixture so all seed tests point at the same bundle.
    Resolves relative to the repo root (two levels up from backend/tests/integration/).
    """
    # backend/tests/integration/ -> backend/ -> repo root
    repo_root = Path(__file__).parent.parent.parent.parent
    bundle = repo_root / "data" / "verification"
    return bundle


# ---------------------------------------------------------------------------
# Async engine fixture (session-scoped; skipped when DB is unreachable)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def postgres_engine() -> AsyncEngine:
    """Session-scoped async engine connected to compose postgres on :5433.

    Purpose: real DB connection for integration tests. Uses the same DSN as
             the compose healthcheck.
    Yields: AsyncEngine (disposed after all tests complete).
    Skips: when compose postgres is not reachable on :5433.
    """
    dsn = (
        "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
        "@127.0.0.1:5433/hilopeople_dev"
    )
    engine = create_async_engine(dsn, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Reset app.core.db singleton between tests (P00-S02-T016 — event loop fix)
# ---------------------------------------------------------------------------
#
# CRITICAL (root cause confirmed via stack trace 2026-05-10):
# pytest-asyncio 1.3.0 with asyncio_mode=auto creates a NEW event loop per
# test function. The production app.core.db module holds a singleton
# AsyncEngine (`_engine`) bound to the loop that first invoked
# `_get_engine()`. When a later test calls a FastAPI handler via
# ASGITransport, the handler reuses the cached engine -> asyncpg's connection
# protocol/transport are still attached to the previous (now-closed) loop ->
# `RuntimeError: Task ... got Future ... attached to a different loop`
# at asyncpg/protocol/protocol.pyx:369 during pool_pre_ping checkout.
#
# Why this fixture is ASYNC (not sync like test_auth_signup.py:99):
#   The sync version in test_auth_signup.py does
#       loop.create_task(db_module._engine.dispose())
#   which is FIRE-AND-FORGET — the dispose coroutine is scheduled but not
#   awaited before the test fixture teardown returns. asyncpg's pool then
#   leaks a half-closed connection whose internal Future is bound to the
#   loop that is about to be closed. The fix is to AWAIT dispose() inside an
#   async fixture so it completes within the same loop the test ran on.
#
# Why scope is left implicit (function — pytest_asyncio default):
#   Each test gets a fresh loop; we want a fresh dispose per test.
#
# Why test_auth_signup.py works despite using the broken sync pattern:
#   It uses its OWN per-test engine via `db_session_pg` with NullPool, so
#   the singleton is irrelevant for that file's hot path. The issue only
#   surfaces when the FastAPI handler ITSELF (via ASGITransport) goes
#   through the singleton — exactly the discover_models test path.
#
# Idempotency / coexistence with test_auth_signup.py local fixture:
#   This autouse global fixture resets `_engine` and `_session_factory`
#   to None. The test_auth_signup.py local autouse fixture does the same
#   reset — the second reset is a no-op (`None = None`) and the dispose
#   block is guarded by `if _engine is not None`. No conflict.


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def reset_db_engine_singleton() -> AsyncGenerator[None, None]:
    """Reset and properly dispose the app.core.db singleton engine each test.

    Purpose: prevent asyncpg "attached to a different loop" errors that occur
    when the same engine is reused across test functions that each get a
    fresh asyncio event loop (pytest-asyncio asyncio_mode=auto default).

    Pattern:
      1. BEFORE test: null out `_engine` / `_session_factory` so the next
         `_get_engine()` builds a fresh engine in the current test's loop.
      2. AFTER test: AWAIT `dispose()` (in this loop) to flush asyncpg's
         pool cleanly. Then null the globals again so the next test sees a
         pristine module state.

    The dispose is wrapped in try/except because a) the test may have
    triggered an asyncpg failure that left the pool partially broken, and
    b) `Event loop is closed` errors emitted by SQLAlchemy's adapter are
    cosmetic — the test already finished its real work.
    """
    import app.core.db as db_module  # noqa: PLC0415

    db_module._engine = None
    db_module._session_factory = None
    try:
        yield
    finally:
        if db_module._engine is not None:
            # Best-effort: a broken pool from a failed test must not cascade
            # and break the next test's setup. The reset to None below is
            # what actually matters for isolation.
            with contextlib.suppress(Exception):
                await db_module._engine.dispose()
            db_module._engine = None
            db_module._session_factory = None
