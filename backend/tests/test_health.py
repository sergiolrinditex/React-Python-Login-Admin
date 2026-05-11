"""
Smoke tests for GET /health endpoint.

Slice: P00-S01-T001 — Repo scaffold + scripts + env.
Phase: P00 — Scaffold + Design System.

Tests use FastAPI TestClient (httpx-based) against the real app instance.
No mocks — behavior is verified against the real handler and middleware.

Covered acceptance criteria (task pack §Tests reales esperados):
  1. test_health_status_200       — /health returns HTTP 200
  2. test_health_shape            — response JSON has correct keys and types
  3. test_request_id_propagated   — X-Request-ID header round-trips correctly
"""

from __future__ import annotations

import logging
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Module-scoped TestClient so the app lifespan runs once per test module."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Status 200 and basic shape
# ---------------------------------------------------------------------------

def test_health_status_200(client: TestClient) -> None:
    """GET /health must return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200, (
        f"Expected 200 OK from /health, got {response.status_code}: {response.text}"
    )


def test_health_shape(client: TestClient) -> None:
    """GET /health JSON must have status='ok', version str, uptime number >= 0."""
    response = client.get("/health")
    data = response.json()

    assert data["status"] == "ok", f"status field should be 'ok', got: {data['status']!r}"
    assert isinstance(data["version"], str), (
        f"version field should be a string, got: {type(data['version'])}"
    )
    assert isinstance(data["uptime"], (int, float)), (
        f"uptime field should be a number, got: {type(data['uptime'])}"
    )
    assert data["uptime"] >= 0, f"uptime should be >= 0, got: {data['uptime']}"


# ---------------------------------------------------------------------------
# 2. X-Request-ID propagation
# ---------------------------------------------------------------------------

def test_request_id_propagated(client: TestClient) -> None:
    """X-Request-ID header sent in request must be echoed back in response."""
    custom_id = "test-request-id-abc-123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id, (
        f"Expected X-Request-ID={custom_id!r} in response headers, "
        f"got: {response.headers.get('X-Request-ID')!r}"
    )


def test_request_id_generated_when_missing(client: TestClient) -> None:
    """If no X-Request-ID is sent, the server must generate and return one."""
    response = client.get("/health")
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None, "Server should generate X-Request-ID when not provided"
    assert len(req_id) > 0, "Generated X-Request-ID should not be empty"


# ---------------------------------------------------------------------------
# 3. Logging BEFORE / AFTER (visible only in DEBUG mode)
# ---------------------------------------------------------------------------

def test_health_logs_before_and_after() -> None:
    """BEFORE and AFTER log messages must be emitted when verbose logging is on.

    Sets ENABLE_VERBOSE_LOGGING=true, sets the app.main logger level to DEBUG,
    and uses a list handler to capture records. Verifies that health.check.start
    and health.check.ok are both emitted. Restores environment afterwards.

    This approach avoids conflicts with pytest caplog and custom handler setup
    in _configure_logging() which clears root logger handlers.
    """
    import app.main as app_module

    captured_messages: list[str] = []

    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_messages.append(record.getMessage())

    app_logger = logging.getLogger("app.main")
    handler = ListHandler()
    handler.setLevel(logging.DEBUG)
    app_logger.addHandler(handler)
    original_level = app_logger.level
    app_logger.setLevel(logging.DEBUG)

    os.environ["ENABLE_VERBOSE_LOGGING"] = "true"
    try:
        app_module._configure_logging()

        with TestClient(app, raise_server_exceptions=True) as c:
            response = c.get("/health")

        assert response.status_code == 200

        assert any("health.check.start" in m for m in captured_messages), (
            f"Expected 'health.check.start' in log messages. Got: {captured_messages}"
        )
        assert any("health.check.ok" in m for m in captured_messages), (
            f"Expected 'health.check.ok' in log messages. Got: {captured_messages}"
        )
    finally:
        app_logger.removeHandler(handler)
        app_logger.setLevel(original_level)
        os.environ["ENABLE_VERBOSE_LOGGING"] = "false"
        app_module._configure_logging()
