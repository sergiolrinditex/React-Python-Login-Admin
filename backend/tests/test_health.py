"""
Health endpoint integration tests.

Slice: P00-S02-T002 — Health live ready endpoints
Phase: P00 — Scaffold + Design System

Tests covered (9 total):
  1. test_health_returns_flat_shape_and_200 — /health flat shape and 200 status.
  2. test_live_returns_200_without_db — /live returns 200 and never touches DB.
  3. test_ready_returns_200_when_db_ok — /ready 200 when DB probe succeeds.
  4. test_ready_returns_503_when_db_fails — /ready 503 when DB probe raises.
  5. test_request_id_echoed_when_provided — custom X-Request-ID echoed on response.
  6. test_request_id_generated_when_missing — uuid4 hex generated when header absent.
  7. test_logs_redact_secrets_under_verbose — query params with sensitive names
     are not leaked into structured log fields.
  8. test_health_uptime_increases — two sequential /health calls prove uptime grows.
  9. test_ready_db_down_does_not_leak_dsn_in_logs — regression for verify-slice
     finding #1 (CWE-532): DB-down log output must not leak DSN / password /
     host / port / DSN via structlog Rich traceback frame locals.

Rules (01-non-negotiables.md §"Tests are REAL"):
  - No mocking of business logic.
  - Engine DI (monkeypatch on get_engine) is the only mock — this is infra code
    controlled by us, tested via its failure contract path.
  - httpx.AsyncClient uses ASGITransport(app=app) — httpx 0.28 idiom (not app=).

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0 (asyncio_mode=auto in pyproject.toml)
  - httpx 0.28.1
  - sqlalchemy 2.0.49
"""
from __future__ import annotations

import asyncio
import re
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> httpx.AsyncClient:
    """Return an async HTTPX client backed by the in-process FastAPI app.

    Uses ASGITransport — the httpx 0.28+ idiom.  The deprecated `app=` kwarg
    is intentionally avoided.
    """
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _postgres_reachable() -> bool:
    """Return True if the compose postgres is reachable on host port 5433.

    Purpose: gate the real-DB branch of test_ready_returns_200_when_db_ok so
    the suite can run in unit-only environments (no compose up).
    The test is NOT skipped when compose is up — the developer MUST run it once
    with real DB and capture evidence per the slice acceptance criteria.
    """

    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Test 1 — /health flat shape
# ---------------------------------------------------------------------------


async def test_health_returns_flat_shape_and_200() -> None:
    """GET /health returns 200 with flat shape {status, version, uptime}.

    Validates Discrepancy D1: flat shape is preserved for T001 compose compat.
    """
    async with _make_client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert set(body.keys()) == {"status", "version", "uptime"}, (
        f"Expected exactly {{status, version, uptime}}, got: {set(body.keys())}"
    )
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)
    assert isinstance(body["uptime"], float | int)
    assert body["uptime"] >= 0


# ---------------------------------------------------------------------------
# Test 2 — /live never touches DB
# ---------------------------------------------------------------------------


async def test_live_returns_200_without_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /live returns 200 and never calls get_engine().

    Monkeypatches get_engine in the router module to raise — proves /live
    ignores the engine entirely.
    """

    def _raise(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("get_engine should NOT be called by /live")

    monkeypatch.setattr("app.api.router.get_engine", _raise)

    async with _make_client() as client:
        response = await client.get("/live")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["status"] == "alive"
    assert set(body.keys()) == {"status", "version", "uptime"}
    assert isinstance(body["uptime"], float | int)
    assert body["uptime"] >= 0


# ---------------------------------------------------------------------------
# Test 3 — /ready 200 when DB up
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _postgres_reachable(), reason="compose postgres not reachable on :5433")
async def test_ready_returns_200_when_db_ok() -> None:
    """GET /ready returns 200 with checks.db.status=="ok" when DB is up.

    Runs only when compose postgres is reachable.  The developer MUST capture
    evidence in evidence/test-ready-db-up.log with compose up per acceptance.
    """
    async with _make_client() as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "not_implemented"
    assert body["checks"]["litellm"]["status"] == "not_implemented"


# ---------------------------------------------------------------------------
# Test 4 — /ready 503 when DB down
# ---------------------------------------------------------------------------


async def test_ready_returns_503_when_db_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /ready returns 503 with checks.db.status=="fail" when DB probe raises.

    Monkeypatches get_engine to return an engine whose connect() raises
    SQLAlchemyError.  Validates:
      - HTTP status 503
      - body.status == "not_ready"
      - body.reason == "db"
      - checks.db.status == "fail"
      - detail string is non-empty
      - detail does NOT leak DATABASE_URL or credentials
    """
    # Build a mock engine whose .connect() returns an async context manager
    # that raises on __aenter__.
    mock_conn_cm = AsyncMock()
    mock_conn_cm.__aenter__.side_effect = OperationalError(
        "simulated connection failure", None, Exception("connection refused")
    )
    mock_conn_cm.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn_cm

    monkeypatch.setattr("app.api.router.get_engine", lambda: mock_engine)

    async with _make_client() as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    body: dict[str, Any] = response.json()
    assert body["status"] == "not_ready"
    assert body["reason"] == "db"
    assert body["checks"]["db"]["status"] == "fail"
    detail: str = body["checks"]["db"].get("detail", "")
    assert detail, "detail must be a non-empty string"
    # Security: DSN components must not leak into the detail field.
    assert "postgresql" not in detail.lower(), "DSN scheme leaked in detail"
    assert "change-me" not in detail.lower(), "Credential leaked in detail"
    # Not-implemented placeholders still present.
    assert body["checks"]["redis"]["status"] == "not_implemented"
    assert body["checks"]["litellm"]["status"] == "not_implemented"


# ---------------------------------------------------------------------------
# Test 5 — X-Request-ID echoed when provided
# ---------------------------------------------------------------------------


async def test_request_id_echoed_when_provided() -> None:
    """Response X-Request-ID equals the value sent in the request."""
    custom_id = "planner-smoke-1"
    async with _make_client() as client:
        response = await client.get("/health", headers={"X-Request-ID": custom_id})

    assert response.headers.get("x-request-id") == custom_id


# ---------------------------------------------------------------------------
# Test 6 — X-Request-ID generated when missing
# ---------------------------------------------------------------------------


async def test_request_id_generated_when_missing() -> None:
    """Response X-Request-ID is a valid uuid4 hex when not provided by client."""
    async with _make_client() as client:
        response = await client.get("/health")

    request_id = response.headers.get("x-request-id", "")
    assert request_id, "X-Request-ID must be present in response"
    assert re.match(r"^[0-9a-f]{32}$", request_id), (
        f"Expected uuid4 hex (32 lower-hex chars), got: {request_id!r}"
    )


# ---------------------------------------------------------------------------
# Test 7 — Log redaction under verbose (query params with sensitive names)
# ---------------------------------------------------------------------------


async def test_logs_redact_secrets_under_verbose(capsys: pytest.CaptureFixture[str]) -> None:
    """Sensitive key values do not appear in structured log output.

    Sends a request with ?password=hunter2.  Validates that "hunter2" does NOT
    appear in any captured log output.

    Note: the redaction processor operates on structlog event_dict KEYS, not on
    raw URL query strings.  This test is a belt-and-suspenders check: health
    handlers do not log the URL or query params, so the string can never appear
    in a log event dict field.  If a future handler starts logging request.url,
    this test will catch the regression.
    """
    from app.core.logging import configure_logging

    # Re-run in verbose mode to capture DEBUG output.
    configure_logging(verbose=True)  # idempotent guard handles repeated calls

    async with _make_client() as client:
        await client.get("/health", params={"password": "hunter2"})

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "hunter2" not in combined, (
        "Sensitive value 'hunter2' leaked into log output"
    )


# ---------------------------------------------------------------------------
# Test 8 — Uptime increases between sequential calls
# ---------------------------------------------------------------------------


async def test_health_uptime_increases() -> None:
    """Two sequential /health calls return increasing uptime values.

    Proves that _START_TIME is module-level (not per-request), so uptime
    accumulates correctly.
    """
    async with _make_client() as client:
        r1 = await client.get("/health")
        # Tiny sleep to guarantee a measurable time delta.
        await asyncio.sleep(0.05)
        r2 = await client.get("/health")

    uptime1: float = r1.json()["uptime"]
    uptime2: float = r2.json()["uptime"]
    assert uptime2 > uptime1, (
        f"Expected uptime to increase: {uptime1} → {uptime2}"
    )


# ---------------------------------------------------------------------------
# Test 9 — DB-down logs DO NOT leak DSN/credentials via traceback frame locals
# ---------------------------------------------------------------------------
#
# Regression for verify-slice finding #1 on P00-S02-T002 (CWE-532).
# Before the fix, _probe_db's except branches called
#   _logger.error("...", error_class=..., exc_info=True)
# which in verbose mode is rendered by structlog's ConsoleRenderer +
# RichTracebackFormatter.  The default Rich traceback formatter renders frame
# locals — so if the failing connect() frame holds the DSN, password, host or
# port as locals, those leak to stdout/stderr.  asyncpg/SQLAlchemy DO bind
# cparams = {host, user, password, port, database} as a local in their
# connect() path, so this leak triggered on a real DB-down event.
#
# Fix: drop exc_info=True from both except branches in _probe_db (and from the
# defensive request_id middleware path).  The structured fields error_class
# and db_detail (sanitized) remain — they are the safe production signal.
#
# This test exercises the failure path with a function that holds a deliberate
# fake DSN+password as a local before raising, and asserts the captured log
# output does NOT contain them.
# ---------------------------------------------------------------------------


async def test_ready_db_down_does_not_leak_dsn_in_logs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """GET /ready DB-down branch must not leak DSN, password, host or port.

    Reproduces verify-slice finding #1 (CWE-532).  In verbose mode, structlog's
    ConsoleRenderer + RichTracebackFormatter renders frame locals when
    exc_info=True is passed.  This test:
      1. Switches logging to verbose to enable the rendering pipeline.
      2. Monkeypatches get_engine() to return a fake engine whose connect()
         is a function with deliberate DSN+secret values as local variables,
         which raises an OperationalError.
      3. Calls /ready and captures stdout/stderr.
      4. Asserts that the password value, host name, port and full DSN do
         NOT appear anywhere in the captured log output.

    Before the fix, the password and DSN appeared in the log output (rendered
    via Rich traceback frame locals).  After the fix, exc_info=True is dropped
    so no traceback is rendered, and the structured fields contain only
    error_class + sanitized db_detail.

    Tracked: handoff §verify-slice finding #1 + FU-20260509044829-disable-
    structlog-rich-traceback-show-locals-glo (out-of-scope global fix).
    """
    from app.core import logging as core_logging

    # Verbose mode is required to trigger ConsoleRenderer + RichTracebackFormatter.
    # configure_logging() is idempotent on first-call, so we must force a
    # reconfigure by clearing the module-level guard.  Restoring the previous
    # state at the end keeps other tests deterministic.
    prev_configured = core_logging._configured
    core_logging._configured = False
    try:
        core_logging.configure_logging(verbose=True)

        # Deliberate values chosen so they cannot collide with anything else
        # logged (uvicorn access lines, sqlalchemy banners, structlog meta).
        secret_password = "topsecret_pwd_xyz_8f3c1"
        secret_host = "hostxyz-debugger-fix"
        secret_port = "54399"
        secret_database = "dbxyz_debugger_fix"
        secret_user = "userxyz_debugger_fix"
        fake_dsn = (
            f"postgresql+asyncpg://{secret_user}:{secret_password}"
            f"@{secret_host}:{secret_port}/{secret_database}"
        )

        class _FakeAsyncConn:
            """Async context manager whose __aenter__ raises with secret-bearing locals.

            The secrets are intentionally bound ONLY as frame locals (via the
            cparams dict and self attributes) and NEVER included in the
            exception message itself.  This mirrors the real
            asyncpg/SQLAlchemy behavior: the OperationalError message is
            generic ("connection refused"), but the connect() frame's locals
            hold cparams = {host, user, password, port, database} verbatim.
            The leak vector is structlog rendering those frame locals when
            exc_info=True is on.
            """

            def __init__(self, cparams: dict[str, str], dsn: str) -> None:
                # cparams mirrors asyncpg's internal naming.  This dict ends
                # up as frame locals in __aenter__ below; if structlog's Rich
                # traceback formatter runs with show_locals=True, every
                # key+value in cparams will be printed verbatim to stdout.
                self.cparams = cparams
                self.dsn = dsn

            async def __aenter__(self) -> _FakeAsyncConn:
                # The locals of THIS frame contain self (with .cparams +
                # .dsn) — exactly what RichTracebackFormatter renders by
                # default.
                cparams = self.cparams  # noqa: F841 — bound as local on purpose
                dsn = self.dsn  # noqa: F841 — bound as local on purpose
                # Generic message — no secrets in the str(exc) representation.
                # Only the frame locals carry the secrets.
                raise OperationalError(
                    "connection refused",
                    None,
                    Exception("Errno 61 ConnectionRefusedError"),
                )

            async def __aexit__(self, *args: Any) -> bool:
                return False

        cparams = {
            "host": secret_host,
            "port": secret_port,
            "user": secret_user,
            "password": secret_password,
            "database": secret_database,
        }

        class _FakeEngine:
            """Engine whose .connect() returns a context manager that raises."""

            def connect(self) -> _FakeAsyncConn:
                return _FakeAsyncConn(cparams, fake_dsn)

        monkeypatch.setattr("app.api.router.get_engine", _FakeEngine)

        async with _make_client() as client:
            response = await client.get("/ready")

        captured = capsys.readouterr()
        combined = captured.out + captured.err

        # 1. Response contract is unchanged: 503, sanitized body.
        assert response.status_code == 503, (
            f"Expected 503 from /ready when DB probe fails, got "
            f"{response.status_code}"
        )
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["db"]["status"] == "fail"

        # 2. Logs must NOT contain password, host, port or full DSN.
        #    These assertions FAIL if exc_info=True is reintroduced into
        #    _probe_db while structlog's ConsoleRenderer +
        #    RichTracebackFormatter remain on their show_locals=True default.
        leaks: list[str] = []
        for needle, label in (
            (secret_password, "password"),
            (secret_host, "host"),
            (secret_port, "port"),
            (secret_user, "user"),
            (secret_database, "database"),
            (fake_dsn, "full DSN"),
        ):
            if needle in combined:
                leaks.append(f"{label} ({needle!r})")
        assert not leaks, (
            "DB-down log output leaked sensitive values via traceback frame "
            f"locals — CWE-532. Leaked: {', '.join(leaks)}.\n"
            f"Captured output:\n{combined}"
        )

        # 3. The response body itself must also stay sanitized.
        #    Since this test deliberately keeps secrets out of the exception
        #    message and only embeds them in frame locals, the body never
        #    carries them either; we still assert that DSN scheme + secret
        #    are absent so a future regression in _sanitize_db_error is
        #    caught.
        detail = body["checks"]["db"].get("detail", "")
        assert secret_password not in detail
        assert secret_host not in detail
        assert "postgresql" not in detail.lower()
    finally:
        # Restore the configure_logging idempotent guard so other tests run
        # against the original (non-verbose) configuration.
        core_logging._configured = prev_configured
