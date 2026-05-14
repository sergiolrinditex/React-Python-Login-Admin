"""
Integration sentinel for GET /ready — real-Postgres coverage + engine-type regression guard.

Slice:  P02-S03-T005 — Fix /ready 500 — _ping_db engine type sentinel + real-DB integration test
Phase:  P02 Core Features
Purpose: Closes FU-20260513201144 acceptance gaps:
           - TEST-1: Happy-path with real Postgres (no dependency_overrides) asserts 200 +
             correct envelope. Proves the endpoint works against a live DB, not just mocks.
           - TEST-2: DB-down path with real psycopg3 driver (not MagicMock) asserts 503 +
             db.status == "error". Exercises the actual `except sa_exc.OperationalError` branch
             under real driver semantics.
           - TEST-3 (SENTINEL): `get_db_engine()` must return a sync `sqlalchemy.engine.Engine`
             and must NOT return an `AsyncEngine`. This is the regression guard for the original
             FU premise: if anyone swaps `create_engine` for `create_async_engine`, this test
             fails immediately.
           - TEST-4: Verbose logging contract over the real engine path. Uses
             `caplog.at_level(INFO)` approach (Option A per §4.1 decision) because `_VERBOSE`
             is resolved at module import time — the logger level is what matters at runtime.

         Does NOT duplicate the 10 existing unit-style tests in `backend/tests/test_health.py`
         (MagicMock dependency_overrides). These tests complement by verifying real I/O behavior.

Decision §K-T005-LOG-APPROACH: Approach A (caplog.at_level) chosen for verbose/quiet tests.
  `_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", ...) == "true"` is evaluated once on import;
  `monkeypatch.setenv` after import does not retroactively flip `_LOG_LEVEL` in the router module.
  Approach A observes what the live logger actually emits at INFO level — matching the existing
  `test_logging_verbose_mode_logs_before_after` pattern in `test_health.py`. Approach B
  (importlib.reload) was discarded (KISS, risk of breaking singleton state, no extra coverage gain).

Key deps:
  - pytest + fastapi.testclient.TestClient (real ASGI, no uvicorn)
  - sqlalchemy 2.0: create_engine, Engine, AsyncEngine
  - psycopg[binary] 3.3.3: real dialect for TEST-2 broken-DSN path
  - app.main.app — full FastAPI instance (same boot as prod, R2 accepted)
  - app.api.router: get_db_engine, get_redis_client (FastAPI dependency factories)
  - Real Postgres at DATABASE_URL (defaults to hilo:hilo@localhost:5432/hilo_dev)

Source refs:
  - TASK_PACK P02-S03-T005 §4, §11 (WRITE_SET_DRIFT anchors), §10.3 (contracts verified)
  - 01-non-negotiables.md §Tests are REAL (real DB, no mocks for owned services)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR; ENABLE_VERBOSE_LOGGING contract)
  - TECHNICAL_GUIDE §6.2 GET /ready envelope shape
  - official-doc-notes/P00-S02-T002-sqlalchemy-sync-ping-2026-05-11.md (RESOLVED)

WRITE_SET_DRIFT note: registry write_set declared `backend/tests/integration/test_health.py`;
actual file is `test_health_ready.py` per §D-T005-TEST-PATH-FIX (avoids collision with existing
unit-style `backend/tests/test_health.py` and matches sibling naming convention).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

# ---------------------------------------------------------------------------
# PYTHONPATH — ensure `from app.*` resolves even when invoked from repo root.
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.main import app  # noqa: E402
from app.api.router import get_db_engine  # noqa: E402

# ---------------------------------------------------------------------------
# Module-level client — reuses a single ASGI test transport (matches test_health.py).
# ---------------------------------------------------------------------------
_client = TestClient(app)

# ---------------------------------------------------------------------------
# Constants — expected envelope shape from TECHNICAL_GUIDE §6.2.
# Real probe: litellm always "unknown" (no httpx call, per §U2 resolution).
# ---------------------------------------------------------------------------
_EXPECTED_ENVELOPE_KEYS = {"db", "redis", "litellm"}
_LITELLM_STATUS = "unknown"

# Logger name for caplog assertions (must match `logging.getLogger(__name__)` in router.py).
_ROUTER_LOGGER = "app.api.router"


# ===========================================================================
# TEST-1 — Real-Postgres happy path (no dependency_overrides)
# ===========================================================================


class TestReadyRealDbHappyPath:
    """GET /ready against real Postgres + real Redis — no mocks, no overrides.

    Acceptance (1): GET /ready returns 200 under happy path (real DB up).
    This class contains the true integration proof: it does not touch
    `app.dependency_overrides`, so `get_db_engine()` creates a live
    `create_engine(postgresql+psycopg://...)` and pings the real DB.
    """

    def test_returns_200_ok(self) -> None:
        """Real Postgres up → GET /ready must return HTTP 200.

        BEFORE: request dispatched with real DB engine.
        AFTER: asserts 200 status code.
        ERROR: fails loudly if Postgres is not reachable — stack must be UP.
        """
        response = _client.get("/ready")
        assert response.status_code == 200, (
            f"Expected 200 from real DB, got {response.status_code}: {response.text}"
        )

    def test_envelope_has_data_key(self) -> None:
        """Response body must have top-level 'data' key per TECHNICAL_GUIDE §6.2."""
        response = _client.get("/ready")
        body = response.json()
        assert "data" in body, f"Missing 'data' key in envelope: {body}"

    def test_envelope_data_has_required_keys(self) -> None:
        """data must contain db, redis and litellm keys."""
        response = _client.get("/ready")
        body = response.json()
        data: dict[str, Any] = body["data"]
        missing = _EXPECTED_ENVELOPE_KEYS - set(data.keys())
        assert not missing, f"Missing envelope keys {missing} in: {data}"

    def test_db_status_ok_with_real_postgres(self) -> None:
        """data.db.status must be 'ok' when Postgres is reachable."""
        response = _client.get("/ready")
        body = response.json()
        assert body["data"]["db"]["status"] == "ok", (
            f"Expected db.status='ok' with live Postgres, got: {body['data']['db']}"
        )

    def test_redis_status_ok_with_real_redis(self) -> None:
        """data.redis.status must be 'ok' when Redis is reachable."""
        response = _client.get("/ready")
        body = response.json()
        assert body["data"]["redis"]["status"] == "ok", (
            f"Expected redis.status='ok' with live Redis, got: {body['data']['redis']}"
        )

    def test_litellm_status_always_unknown(self) -> None:
        """data.litellm.status must be 'unknown' — no HTTP ping per §U2 resolution."""
        response = _client.get("/ready")
        body = response.json()
        assert body["data"]["litellm"]["status"] == _LITELLM_STATUS, (
            f"Expected litellm.status='{_LITELLM_STATUS}', got: {body['data']['litellm']}"
        )


# ===========================================================================
# TEST-2 — Real psycopg3 driver DB-down → 503
# ===========================================================================


class TestReadyRealDriverDbDown:
    """GET /ready with a broken DSN → real psycopg3 OperationalError → 503.

    Acceptance (2): integration test asserts /ready 503 when DB is unreachable.
    Uses Pattern A (dependency_override with a real create_engine on an
    unreachable DSN) so the actual `except sa_exc.OperationalError` branch
    in `_ping_db` fires under a real driver exception — not a MagicMock.

    Design choices:
      - DSN points to localhost:1 (no listener) so connect fails fast.
      - `pool_pre_ping=False` avoids pool-level pre-ping (we want the connect()
        in _ping_db to raise, not a pool check).
      - `connect_args={"connect_timeout": 2}` bounds the test to ~2s max (R3).
      - Redis is NOT overridden — real Redis remains to prove only db degrades.
    """

    @pytest.fixture(autouse=True)
    def _inject_broken_db_engine(self) -> Any:
        """Override get_db_engine with a real engine on unreachable DSN.

        BEFORE: override installed pointing at 127.0.0.1:1 (refused).
        AFTER: override cleared in finally block (test isolation).
        """
        broken_engine = create_engine(
            "postgresql+psycopg://invalid:invalid@127.0.0.1:1/nope",
            pool_pre_ping=False,
            connect_args={"connect_timeout": 2},
        )
        app.dependency_overrides[get_db_engine] = lambda: broken_engine
        yield broken_engine
        app.dependency_overrides.pop(get_db_engine, None)
        broken_engine.dispose()

    def test_returns_503_when_db_unreachable(self) -> None:
        """Broken DB DSN → GET /ready must return HTTP 503.

        BEFORE: request sent with real broken engine injected.
        AFTER: asserts 503 status code.
        ERROR: if 200 returned, the OperationalError catch branch is broken.
        """
        response = _client.get("/ready")
        assert response.status_code == 503, (
            f"Expected 503 with unreachable DB, got {response.status_code}: {response.text}"
        )

    def test_db_status_error_on_connection_failure(self) -> None:
        """data.db.status must be 'error' when real psycopg3 raises OperationalError."""
        response = _client.get("/ready")
        body = response.json()
        assert body["data"]["db"]["status"] == "error", (
            f"Expected db.status='error', got: {body['data']['db']}"
        )

    def test_redis_status_still_ok_when_only_db_down(self) -> None:
        """Redis must remain 'ok' when only DB is broken (Redis is not overridden)."""
        response = _client.get("/ready")
        body = response.json()
        assert body["data"]["redis"]["status"] == "ok", (
            f"Expected redis.status='ok' (only DB broken), got: {body['data']['redis']}"
        )

    def test_envelope_shape_preserved_on_503(self) -> None:
        """503 response must still include data.db + data.redis + data.litellm keys."""
        response = _client.get("/ready")
        body = response.json()
        assert "data" in body, f"Missing 'data' key on 503: {body}"
        missing = _EXPECTED_ENVELOPE_KEYS - set(body["data"].keys())
        assert not missing, f"Missing keys {missing} in 503 body: {body['data']}"


# ===========================================================================
# TEST-3 — SENTINEL: engine type contract (regression guard)
# ===========================================================================


class TestGetDbEngineSentinel:
    """ENGINE TYPE SENTINEL — the primary artifact of slice P02-S03-T005.

    The original FU (FU-20260513201144) feared that `_ping_db` was called on
    an `AsyncEngine`, causing `MissingGreenlet`. HEAD already uses a sync
    `Engine` and the bug does not reproduce. This sentinel pins the contract:
    if any future contributor replaces `create_engine` with `create_async_engine`
    in `get_db_engine()`, this test class fails the suite immediately.

    Assertion: `get_db_engine()` MUST return a `sqlalchemy.engine.Engine`
                and MUST NOT return a `sqlalchemy.ext.asyncio.AsyncEngine`.
    """

    def test_get_db_engine_returns_sync_engine(self) -> None:
        """get_db_engine() must return a sync sqlalchemy.engine.Engine.

        BEFORE: call get_db_engine() directly (no request context needed).
        AFTER: assert isinstance(engine, Engine).
        ERROR: if AsyncEngine is returned, _ping_db(engine).connect() raises
               MissingGreenlet in a sync context (the original FU premise).
        """
        engine = get_db_engine()
        assert isinstance(engine, Engine), (
            f"get_db_engine() must return sqlalchemy.engine.Engine, got {type(engine)}"
        )

    def test_get_db_engine_is_not_async_engine(self) -> None:
        """get_db_engine() must NOT return AsyncEngine — regression sentinel.

        This is the explicit forward-regression signal for FU-20260513201144:
        swapping to `create_async_engine` breaks `_ping_db`'s sync `engine.connect()`.
        """
        engine = get_db_engine()
        assert not isinstance(engine, AsyncEngine), (
            "REGRESSION: get_db_engine() returned AsyncEngine. "
            "_ping_db uses sync engine.connect() which raises MissingGreenlet on AsyncEngine. "
            "See FU-20260513201144 and task-pack P02-S03-T005 §D-T005-SENTINEL."
        )

    def test_engine_uses_psycopg_dialect(self) -> None:
        """Engine dialect must be psycopg (sync) — not asyncpg.

        Extra guard: even if isinstance check somehow passes, the dialect name
        must be 'psycopg' confirming sync driver is in use.
        """
        engine = get_db_engine()
        dialect_name = engine.dialect.name
        assert dialect_name == "postgresql", (
            f"Expected postgresql dialect, got: {dialect_name}"
        )
        driver_name = engine.dialect.driver
        assert driver_name == "psycopg", (
            f"Expected psycopg driver (sync), got: {driver_name}. "
            "asyncpg would break sync engine.connect() in _ping_db."
        )


# ===========================================================================
# TEST-4 — Verbose logging contract over real engine path
# ===========================================================================


class TestReadyVerboseLoggingContract:
    """Logging level contract for GET /ready over the real engine path.

    Acceptance (3): tests run with both ENABLE_VERBOSE_LOGGING=true and =false.

    Decision §K-T005-LOG-APPROACH: Approach A (caplog.at_level).
      `_VERBOSE` in `router.py` is read once at module import. After import,
      `monkeypatch.setenv("ENABLE_VERBOSE_LOGGING", ...)` does NOT retroactively
      change `_LOG_LEVEL` on the logger singleton. Approach A uses
      `caplog.at_level(INFO|WARNING, logger=_ROUTER_LOGGER)` to observe what
      the live logger actually emits — matching the existing pattern in
      `test_logging_verbose_mode_logs_before_after` and `test_logging_quiet_mode_*`
      in `backend/tests/test_health.py`. Approach B (importlib.reload) discarded
      (risk of breaking singleton state, no extra coverage gain — KISS).

    These tests use the real engine (no dependency_overrides), so the verbose
    log markers are emitted from the actual `_ping_db` / `_ping_redis` paths
    rather than from MagicMock stubs. This closes the integration-level gap
    noted in §3.3 point 4 of the task pack.
    """

    def test_verbose_mode_logs_ready_start_marker(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """With caplog at INFO, health.ready.start must appear in log records.

        BEFORE: caplog set to INFO level for the router logger.
        AFTER: assert 'health.ready.start' appears in captured messages.
        """
        with caplog.at_level(logging.INFO, logger=_ROUTER_LOGGER):
            response = _client.get("/ready")
        assert response.status_code == 200, (
            f"Precondition failed (DB must be up): got {response.status_code}"
        )
        messages = [r.getMessage() for r in caplog.records]
        assert any("health.ready.start" in m for m in messages), (
            f"BEFORE log 'health.ready.start' not found. Got: {messages}"
        )

    def test_verbose_mode_logs_db_ping_start_marker(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """With caplog at INFO, health.ready.db.ping.start must appear.

        Proves _ping_db BEFORE log fires over real engine path.
        """
        with caplog.at_level(logging.INFO, logger=_ROUTER_LOGGER):
            response = _client.get("/ready")
        assert response.status_code == 200
        messages = [r.getMessage() for r in caplog.records]
        assert any("health.ready.db.ping.start" in m for m in messages), (
            f"BEFORE log 'health.ready.db.ping.start' not found. Got: {messages}"
        )

    def test_verbose_mode_logs_db_ping_ok_marker(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """With caplog at INFO, health.ready.db.ping.ok must appear on success.

        Proves _ping_db AFTER log fires over real engine + real SELECT 1.
        """
        with caplog.at_level(logging.INFO, logger=_ROUTER_LOGGER):
            response = _client.get("/ready")
        assert response.status_code == 200
        messages = [r.getMessage() for r in caplog.records]
        assert any("health.ready.db.ping.ok" in m for m in messages), (
            f"AFTER log 'health.ready.db.ping.ok' not found. Got: {messages}"
        )

    def test_verbose_mode_logs_ready_ok_marker(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """With caplog at INFO, health.ready.ok must appear on successful probe.

        Proves the final AFTER log fires when all deps are healthy.
        """
        with caplog.at_level(logging.INFO, logger=_ROUTER_LOGGER):
            response = _client.get("/ready")
        assert response.status_code == 200
        messages = [r.getMessage() for r in caplog.records]
        assert any("health.ready.ok" in m for m in messages), (
            f"AFTER log 'health.ready.ok' not found. Got: {messages}"
        )

    def test_quiet_mode_suppresses_info_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """With caplog at WARNING, no INFO records must appear for the router.

        Mirrors `test_logging_quiet_mode_suppresses_info` in test_health.py
        but over the real engine path (no dependency_overrides).

        BEFORE: caplog set to WARNING — INFO records invisible.
        AFTER: assert zero INFO records for app.api.router.
        """
        with caplog.at_level(logging.WARNING, logger=_ROUTER_LOGGER):
            response = _client.get("/ready")
        assert response.status_code == 200
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 0, (
            "Expected no INFO records in quiet mode (caplog.at_level=WARNING) "
            f"but found: {[r.getMessage() for r in info_records]}"
        )
