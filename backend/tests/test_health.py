"""
Tests for /health, /live and /ready health probe endpoints.

Slice:  P00-S02-T002 — Health live ready endpoints
Phase:  P00 Scaffold + Design System
Purpose: Verifies all three health probes using FastAPI TestClient (real ASGI
         stack). /ready tests use app.dependency_overrides to inject controlled
         DB/Redis fakes, exercising the real router/envelope logic without
         requiring live infra (unit-level isolation of external I/O only).

         Test #9 and #10 verify that ENABLE_VERBOSE_LOGGING controls log
         visibility: INFO appears when true, suppressed when false.

Deps:
  - fastapi.testclient.TestClient (real ASGI; no network mock).
  - app.main.app (FastAPI instance).
  - app.api.router: get_db_engine, get_redis_client (dependency factories).
  - sqlalchemy.exc.OperationalError (fake DB failure injection).
  - redis.exceptions.ConnectionError, TimeoutError (fake Redis failure injection).

Write-set note: part of canonical write_set for P00-S02-T002.
"""

import logging
import sys
import os
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy import exc as sa_exc
import redis.exceptions as redis_exc

# Ensure backend/ is on PYTHONPATH so `from app.main import app` resolves.
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from app.main import app  # noqa: E402
from app.api.router import get_db_engine, get_redis_client  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers — fake dependency factories
# ---------------------------------------------------------------------------

def _make_fake_engine_ok() -> Engine:
    """Return a fake Engine whose connect().execute() succeeds silently."""
    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)
    fake_engine = MagicMock(spec=Engine)
    fake_engine.connect.return_value = fake_conn
    return fake_engine


def _make_fake_engine_fail() -> Engine:
    """Return a fake Engine whose connect() raises OperationalError."""
    fake_engine = MagicMock(spec=Engine)
    fake_engine.connect.side_effect = sa_exc.OperationalError(
        "could not connect to server", None, Exception("connection refused")
    )
    return fake_engine


def _make_fake_redis_ok() -> Any:
    """Return a fake redis.Redis whose ping() returns True."""
    fake_redis = MagicMock()
    fake_redis.ping.return_value = True
    return fake_redis


def _make_fake_redis_conn_error() -> Any:
    """Return a fake redis.Redis whose ping() raises ConnectionError."""
    fake_redis = MagicMock()
    fake_redis.ping.side_effect = redis_exc.ConnectionError("Connection refused by server.")
    return fake_redis


def _make_fake_redis_timeout_error() -> Any:
    """Return a fake redis.Redis whose ping() raises TimeoutError."""
    fake_redis = MagicMock()
    fake_redis.ping.side_effect = redis_exc.TimeoutError("Timeout connecting to server.")
    return fake_redis


# ---------------------------------------------------------------------------
# Regression tests — T001 stub (must stay green)
# ---------------------------------------------------------------------------

def test_legacy_health_still_returns_200() -> None:
    """GET /health must return HTTP 200 — backward compat with T001 shape."""
    response = client.get("/health")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )


def test_health_envelope_shape() -> None:
    """Response envelope must match TECHNICAL_GUIDE §6.2: {data: {status: ...}}."""
    response = client.get("/health")
    body = response.json()
    assert "data" in body, f"Missing 'data' key in: {body}"
    assert body["data"]["status"] == "ok", f"Expected status='ok', got: {body['data']}"


# ---------------------------------------------------------------------------
# /live — liveness probe
# ---------------------------------------------------------------------------

def test_health_live_returns_200_ok() -> None:
    """GET /live must always return 200 with status=ok (no external deps)."""
    response = client.get("/live")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["data"]["status"] == "ok", f"Unexpected body: {body}"


# ---------------------------------------------------------------------------
# /ready — readiness probe (dependency-override pattern)
# ---------------------------------------------------------------------------

def test_health_ready_returns_200_when_all_ok() -> None:
    """GET /ready returns 200 with db=ok, redis=ok when both deps succeed."""
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_ok()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_ok()
    try:
        response = client.get("/ready")
        assert response.status_code == 200, f"Expected 200: {response.text}"
        body = response.json()
        assert body["data"]["db"]["status"] == "ok"
        assert body["data"]["redis"]["status"] == "ok"
        assert body["data"]["litellm"]["status"] == "unknown"
    finally:
        app.dependency_overrides.clear()


def test_health_ready_returns_503_when_db_degraded() -> None:
    """GET /ready returns 503 with db=error when DB raises OperationalError."""
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_fail()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_ok()
    try:
        response = client.get("/ready")
        assert response.status_code == 503, f"Expected 503: {response.text}"
        body = response.json()
        assert body["data"]["db"]["status"] == "error"
        assert body["data"]["redis"]["status"] == "ok"
    finally:
        app.dependency_overrides.clear()


def test_health_ready_returns_503_when_redis_connection_error() -> None:
    """GET /ready returns 503 with redis=error when Redis raises ConnectionError."""
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_ok()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_conn_error()
    try:
        response = client.get("/ready")
        assert response.status_code == 503, f"Expected 503: {response.text}"
        body = response.json()
        assert body["data"]["db"]["status"] == "ok"
        assert body["data"]["redis"]["status"] == "error"
    finally:
        app.dependency_overrides.clear()


def test_health_ready_returns_503_when_redis_timeout() -> None:
    """GET /ready returns 503 with redis=error when Redis raises TimeoutError."""
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_ok()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_timeout_error()
    try:
        response = client.get("/ready")
        assert response.status_code == 503, f"Expected 503: {response.text}"
        body = response.json()
        assert body["data"]["db"]["status"] == "ok"
        assert body["data"]["redis"]["status"] == "error"
    finally:
        app.dependency_overrides.clear()


def test_health_ready_returns_503_when_both_degraded() -> None:
    """GET /ready returns 503 when both DB and Redis are degraded."""
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_fail()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_conn_error()
    try:
        response = client.get("/ready")
        assert response.status_code == 503, f"Expected 503: {response.text}"
        body = response.json()
        assert body["data"]["db"]["status"] == "error"
        assert body["data"]["redis"]["status"] == "error"
    finally:
        app.dependency_overrides.clear()


def test_health_ready_body_includes_litellm_unknown() -> None:
    """GET /ready body always includes litellm.status=unknown (informational)."""
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_ok()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_ok()
    try:
        response = client.get("/ready")
        body = response.json()
        assert "litellm" in body["data"], f"litellm key missing from: {body}"
        assert body["data"]["litellm"]["status"] == "unknown"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Logging level tests
# ---------------------------------------------------------------------------

def test_logging_verbose_mode_logs_before_after(caplog: pytest.LogCaptureFixture) -> None:
    """
    With ENABLE_VERBOSE_LOGGING=true the router logger emits INFO records
    containing BEFORE (*.start) and AFTER (*.ok) markers.
    """
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_ok()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_ok()
    try:
        with caplog.at_level(logging.INFO, logger="app.api.router"):
            response = client.get("/ready")
        assert response.status_code == 200
        messages = [r.getMessage() for r in caplog.records]
        assert any("health.ready.start" in m for m in messages), (
            f"No BEFORE log found in: {messages}"
        )
        assert any("health.ready.ok" in m for m in messages), (
            f"No AFTER log found in: {messages}"
        )
    finally:
        app.dependency_overrides.clear()


def test_logging_quiet_mode_suppresses_info(caplog: pytest.LogCaptureFixture) -> None:
    """
    With logger set to WARNING level (ENABLE_VERBOSE_LOGGING=false equivalent),
    no INFO records appear for the router.
    """
    app.dependency_overrides[get_db_engine] = lambda: _make_fake_engine_ok()
    app.dependency_overrides[get_redis_client] = lambda: _make_fake_redis_ok()
    try:
        with caplog.at_level(logging.WARNING, logger="app.api.router"):
            response = client.get("/ready")
        assert response.status_code == 200
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 0, (
            f"Expected no INFO records in quiet mode but found: {[r.getMessage() for r in info_records]}"
        )
    finally:
        app.dependency_overrides.clear()
