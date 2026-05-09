"""
Integration test fixtures for seed loader tests.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Provides:
  - postgres_engine: session-scoped async engine pointing at compose postgres on :5433.
    Skipped automatically when the DB is not reachable (unit-only environments).
  - verification_bundle_dir: path fixture pointing at data/verification/.

All tests in this package use REAL compose postgres (no mocking).
Tests that require the DB are decorated with @pytest.mark.skipif(not _db_reachable()).

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0 (asyncio_mode=auto in pyproject.toml)
  - sqlalchemy[asyncio] 2.0.49
  - asyncpg 0.31.0
"""
from __future__ import annotations

import socket
from pathlib import Path

import pytest
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
