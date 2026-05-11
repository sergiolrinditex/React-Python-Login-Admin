"""
Smoke test for the /health stub endpoint.

Slice:  P00-S01-T001 — Repo scaffold + scripts + env
Phase:  P00 Scaffold + Design System
Purpose: Verifies that GET /health returns HTTP 200 with the correct JSON
         envelope ``{"data": {"status": "ok", ...}}``.
         Uses FastAPI's TestClient (real ASGI stack, no mocks).

Deps:
  - fastapi.testclient.TestClient (real ASGI; no network mock).
  - app.main.app (the FastAPI instance).

Write-set note (flagged for validator):
  ``backend/tests/`` is NOT explicitly listed in the task-pack write_set
  (which covers ``backend/app/main.py``, ``backend/pyproject.toml`` and
  ``backend/requirements*.txt``). This test is added because:
    1. The acceptance criterion "health route stub compiles" requires
       a repeatable automated check beyond a one-off python -c import.
    2. The verification command ``bash scripts/setup-from-scratch.sh --check``
       does not run pytest; but tester will independently run pytest against
       this file to confirm health works end-to-end.
    3. Accepting it here keeps the evidence traceable to the slice.
  If validator rejects the write-set extension, the file should be deferred
  to P00-S02-T002 (full health contract), which owns ``backend/tests/``.
"""

import sys
import os

import pytest
from fastapi.testclient import TestClient

# Ensure backend/ is on PYTHONPATH so `from app.main import app` resolves.
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_returns_200() -> None:
    """GET /health must return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )


def test_health_envelope_shape() -> None:
    """Response must follow TECHNICAL_GUIDE §6.2 envelope: {data: {status: ...}}."""
    response = client.get("/health")
    body = response.json()
    assert "data" in body, f"Missing 'data' key in: {body}"
    assert body["data"]["status"] == "ok", f"Expected status='ok', got: {body['data']}"


def test_health_verbose_logging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling /health with ENABLE_VERBOSE_LOGGING=true must not raise."""
    monkeypatch.setenv("ENABLE_VERBOSE_LOGGING", "true")
    response = client.get("/health")
    assert response.status_code == 200


def test_health_silent_logging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling /health with ENABLE_VERBOSE_LOGGING=false must not raise."""
    monkeypatch.setenv("ENABLE_VERBOSE_LOGGING", "false")
    response = client.get("/health")
    assert response.status_code == 200
