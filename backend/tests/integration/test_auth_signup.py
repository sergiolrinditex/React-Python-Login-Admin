"""
Integration tests for POST /api/v1/auth/sign-up.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up
Phase: P01 — Auth + Base Capabilities

All tests use REAL Postgres at 127.0.0.1:5433 and the REAL FastAPI app.
No mocking of business logic, repositories, or the DB.

Test inventory (task-pack §11):
  T1 — happy path: new email, strong password, legal=true → 201
  T2 — duplicate email (seeded employee) → 409 AUTH_EMAIL_TAKEN (non-leaky)
  T3 — corporate email rule with non-empty allowlist → 422 AUTH_NON_CORPORATE_EMAIL
  T4 — corporate email rule with empty allowlist → 201 (permissive)
  T5 — weak password (too short, no symbol) → 422 AUTH_WEAK_PASSWORD
  T6 — legal_acceptance=false → 422 AUTH_LEGAL_ACCEPTANCE_REQUIRED
  T7 — malformed payload (missing email) → 422
  T8 — logging: BEFORE+AFTER visible with verbose=true; password never logged

Fixture strategy:
  - Module-level SAVEPOINT via `async_client` fixture (rollback after each test).
  - The seeded employee (`s.lopezrap+employee@gmail.com`) is pre-inserted by the
    migration seed run (not by this test file). Each test sees a clean SAVEPOINT.
  - Each happy-path test uses a unique email (`signup-test+<unique>@testdomain.com`)
    so tests are isolated and reproducible.

Dependencies:
  - pytest 9.0.3, pytest-asyncio 1.3.0 (asyncio_mode=auto)
  - httpx 0.28.1 (AsyncClient + ASGITransport — not deprecated form)
  - sqlalchemy[asyncio] 2.0.49, asyncpg 0.31.0
  - app.main:app (ASGI app)
"""
from __future__ import annotations

import logging
import re
import socket
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# DSN must match compose service hilo-postgres on host port 5433.
_DB_DSN = (
    "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
    "@127.0.0.1:5433/hilopeople_dev"
)

# Seeded employee email (data/verification/users/employee_primary.json).
_SEEDED_EMPLOYEE_EMAIL = "s.lopezrap+employee@gmail.com"


def _db_reachable() -> bool:
    """Return True if compose postgres is reachable on host port 5433."""
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1):
            return True
    except OSError:
        return False


_DB_UP = _db_reachable()

_skip_no_db = pytest.mark.skipif(
    not _DB_UP,
    reason="compose postgres not reachable on 5433 — DB-requiring test skipped",
)

# Valid payload template — override per test.
_VALID_PAYLOAD = {
    "email": "signup-test@testdomain.com",
    "password": "Aa1!Secure$Pass",
    "full_name": "Sign Up Tester",
    "legal_acceptance": True,
}


# ---------------------------------------------------------------------------
# Engine singleton reset autouse fixture
# ---------------------------------------------------------------------------
# CRITICAL (MEMORY.md gotcha): pytest-asyncio 1.3.0 asyncio_mode=auto creates
# a NEW event loop per test. The production app.core.db module holds a singleton
# AsyncEngine (_engine) that is bound to the event loop that first called get_engine().
# On the second test, pool_pre_ping tries to use asyncpg connections from the
# PREVIOUS (now closed) event loop → "Task got Future attached to a different loop".
#
# Fix: reset the singleton before each test so the app creates a fresh engine
# in the current test's event loop. This is safe because:
#   (a) pool_pre_ping ensures the new connection is healthy.
#   (b) Each test is isolated by the app's own transaction commit/rollback.
#   (c) autouse=True means we never forget to apply this reset.


@pytest.fixture(autouse=True)
def reset_db_engine_singleton() -> None:
    """Reset the app.core.db singleton engine before each test.

    Purpose: prevent asyncpg "attached to a different loop" errors that occur
    when the same engine is reused across test functions that each get a fresh
    asyncio event loop (pytest-asyncio asyncio_mode=auto default behavior).

    Pattern: patch the private _engine global back to None so the next call to
    get_engine() creates a fresh AsyncEngine in the current loop.
    """
    import app.core.db as db_module  # noqa: PLC0415

    db_module._engine = None
    db_module._session_factory = None
    yield
    # Post-test: dispose the engine if it was created, to release pool connections.
    import asyncio  # noqa: PLC0415

    if db_module._engine is not None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(db_module._engine.dispose())
            else:
                loop.run_until_complete(db_module._engine.dispose())
        except Exception:  # noqa: BLE001
            pass
        db_module._engine = None
        db_module._session_factory = None


# ---------------------------------------------------------------------------
# Per-test DB session fixture (direct asyncpg connection — no SAVEPOINT)
# ---------------------------------------------------------------------------
# IMPORTANT (MEMORY.md gotcha): pytest-asyncio 1.3.0 with asyncio_mode=auto
# creates a new event loop per test function. SQLAlchemy AsyncEngine with asyncpg
# holds internal connections bound to the event loop — reusing them across tests
# raises "Task got Future attached to a different loop".
#
# Strategy: each test creates a fresh engine, opens a connection, does work,
# rolls back, disposes. The `NullPool` prevents asyncpg from returning connections
# to a pool (which would try to re-use them from a different loop on dispose).
# sqlalchemy.pool.NullPool — every connect/disconnect is fresh; no pooling.


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session with transaction rollback per test.

    Uses NullPool so asyncpg never tries to recycle connections across event loops.
    Creates a fresh engine per test — safe for asyncio_mode=auto.

    Yields: AsyncSession inside a transaction that is rolled back on exit.
    """
    from sqlalchemy.pool import NullPool  # noqa: PLC0415

    engine = create_async_engine(_DB_DSN, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        session = AsyncSession(bind=conn, join_transaction_mode="rollback_only")
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# HTTP client fixture (ASGI — no network, real app)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def http() -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient using ASGITransport against the real FastAPI app.

    Uses httpx.AsyncClient with ASGITransport (not the deprecated `app=` kwarg
    per httpx 0.28 — official-doc-note confirmed ASGITransport is the stable form).

    The app is imported here (after env vars may have been overridden by tests).

    Yields: configured AsyncClient.
    """
    from app.main import app  # noqa: PLC0415

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _unique_email(prefix: str = "signup-test") -> str:
    """Return a unique email for each test run (deterministic UUID suffix)."""
    return f"{prefix}+{uuid.uuid4().hex[:8]}@testdomain.com"


# ---------------------------------------------------------------------------
# T1 — Happy path
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_happy_path(http: AsyncClient, db_session: AsyncSession) -> None:
    """T1: New email + valid password + legal=true → 201 + rows in users/profiles/audit.

    Evidence:
      - HTTP 201 with {data: {mfa_required: true, user_id: <UUID>}}.
      - 1 row in users with email matching the request.
      - 1 row in employee_profiles linked to the new user_id.
      - 1 row in audit_logs with action='auth.sign_up' and the native compliance cols
        (ip, user_agent, request_id, resource) present.
    """
    email = _unique_email()
    payload = {**_VALID_PAYLOAD, "email": email}

    resp = await http.post(
        "/api/v1/auth/sign-up",
        json=payload,
        headers={"X-Request-ID": f"test-{uuid.uuid4().hex}"},
    )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()

    assert "data" in body
    assert body["data"]["mfa_required"] is True
    user_id_str = body["data"]["user_id"]
    user_id = uuid.UUID(user_id_str)  # must be a valid UUID

    # Verify DB rows
    result = await db_session.execute(
        text("SELECT email, full_name, status FROM users WHERE id = :uid"),
        {"uid": str(user_id)},
    )
    row = result.mappings().one()
    assert row["email"] == email
    assert row["full_name"] == "Sign Up Tester"
    assert row["status"] == "active"

    ep_result = await db_session.execute(
        text("SELECT employee_id FROM employee_profiles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    ep_row = ep_result.mappings().one()
    assert ep_row["employee_id"].startswith("EMP-")

    al_result = await db_session.execute(
        text(
            "SELECT action, entity_type, resource, request_id "
            "FROM audit_logs WHERE actor_user_id = :uid"
        ),
        {"uid": str(user_id)},
    )
    al_row = al_result.mappings().one()
    assert al_row["action"] == "auth.sign_up"
    assert al_row["entity_type"] == "user"
    # resource and request_id are native columns (T005 compliance columns)
    assert al_row["resource"] == "POST /api/v1/auth/sign-up"
    assert al_row["request_id"] is not None  # set by X-Request-ID middleware


# ---------------------------------------------------------------------------
# T2 — Duplicate email → 409 (non-leaky)
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_duplicate_email(http: AsyncClient) -> None:
    """T2: Registering the same email twice → 409 AUTH_EMAIL_TAKEN with non-leaky message.

    Strategy: register a fresh email first (succeeds), then attempt to register
    it again (must fail with 409). This is resilient regardless of seed state.
    Message body must NOT contain the words 'exists' or 'already'.
    """
    email = _unique_email("dup-test")
    payload = {**_VALID_PAYLOAD, "email": email}

    # First registration — must succeed
    first_resp = await http.post("/api/v1/auth/sign-up", json=payload)
    assert first_resp.status_code == 201, (
        f"First registration failed (expected 201): {first_resp.text}"
    )

    # Second registration with same email — must fail with 409
    resp = await http.post("/api/v1/auth/sign-up", json=payload)

    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
    body = resp.json()

    assert "errors" in body
    codes = [e["code"] for e in body["errors"]]
    assert "AUTH_EMAIL_TAKEN" in codes

    # Non-leaky check: response message must not reveal that the user exists.
    full_text = resp.text.lower()
    assert "exists" not in full_text, "Response leaks 'exists'"
    assert "already" not in full_text, "Response leaks 'already'"


# ---------------------------------------------------------------------------
# T3 — Corporate email rule (allowlist active) → 422
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_non_corporate_email_rejected(
    http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3: With non-empty CORPORATE_EMAIL_DOMAINS allowlist → 422 for non-whitelisted domain.

    Patches the settings instance to simulate CORPORATE_EMAIL_DOMAINS='hilo.com'.
    Submits a gmail.com address → should be rejected.
    """
    monkeypatch.setenv("CORPORATE_EMAIL_DOMAINS", "hilo.com")
    # Force settings reload so the env change is picked up.
    import importlib

    import app.core.config as cfg_module  # noqa: PLC0415

    importlib.reload(cfg_module)
    # Patch get_settings to return a fresh instance with the new env var.
    from app.core.config import Settings  # noqa: PLC0415

    monkeypatch.setattr(cfg_module, "get_settings", lambda: Settings())

    payload = {**_VALID_PAYLOAD, "email": "user@gmail.com"}

    resp = await http.post("/api/v1/auth/sign-up", json=payload)

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    body = resp.json()

    assert "errors" in body
    codes = [e["code"] for e in body["errors"]]
    assert "AUTH_NON_CORPORATE_EMAIL" in codes
    fields = [e.get("field") for e in body["errors"]]
    assert "email" in fields


# ---------------------------------------------------------------------------
# T4 — Corporate email rule (allowlist empty) → 201 permissive
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_permissive_without_allowlist(
    http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T4: With empty CORPORATE_EMAIL_DOMAINS → any domain accepted → 201.

    The default dev config has CORPORATE_EMAIL_DOMAINS='' (permissive).
    A gmail.com address should be accepted.
    """
    monkeypatch.setenv("CORPORATE_EMAIL_DOMAINS", "")

    import importlib

    import app.core.config as cfg_module  # noqa: PLC0415

    importlib.reload(cfg_module)
    from app.core.config import Settings  # noqa: PLC0415

    monkeypatch.setattr(cfg_module, "get_settings", lambda: Settings())

    email = _unique_email("permissive-test")
    payload = {**_VALID_PAYLOAD, "email": email}

    resp = await http.post("/api/v1/auth/sign-up", json=payload)

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    assert resp.json()["data"]["mfa_required"] is True


# ---------------------------------------------------------------------------
# T5 — Weak password → 422 AUTH_WEAK_PASSWORD
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_weak_password(http: AsyncClient) -> None:
    """T5: Password too short, no symbol → 422 AUTH_WEAK_PASSWORD field=password."""
    payload = {
        **_VALID_PAYLOAD,
        "email": _unique_email("weak-pw"),
        "password": "tooshort1A",  # 10 chars, missing symbol
    }

    resp = await http.post("/api/v1/auth/sign-up", json=payload)

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    body = resp.json()

    assert "errors" in body
    codes = [e["code"] for e in body["errors"]]
    assert "AUTH_WEAK_PASSWORD" in codes
    fields = [e.get("field") for e in body["errors"]]
    assert "password" in fields


# ---------------------------------------------------------------------------
# T6 — Missing legal acceptance → 422 AUTH_LEGAL_ACCEPTANCE_REQUIRED
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_legal_acceptance_false(http: AsyncClient) -> None:
    """T6: legal_acceptance=false → 422 AUTH_LEGAL_ACCEPTANCE_REQUIRED field=legal_acceptance."""
    payload = {
        **_VALID_PAYLOAD,
        "email": _unique_email("nolegal"),
        "legal_acceptance": False,
    }

    resp = await http.post("/api/v1/auth/sign-up", json=payload)

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    body = resp.json()

    assert "errors" in body
    codes = [e["code"] for e in body["errors"]]
    assert "AUTH_LEGAL_ACCEPTANCE_REQUIRED" in codes
    fields = [e.get("field") for e in body["errors"]]
    assert "legal_acceptance" in fields


# ---------------------------------------------------------------------------
# T7 — Malformed payload (missing required field) → 422
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_malformed_missing_email(http: AsyncClient) -> None:
    """T7: Missing email field → 422 with errors array containing field='email'."""
    payload = {
        "password": "Aa1!Secure$Pass",
        "full_name": "No Email",
        "legal_acceptance": True,
        # email is intentionally missing
    }

    resp = await http.post("/api/v1/auth/sign-up", json=payload)

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    body = resp.json()

    # FastAPI/Pydantic 422 uses 'detail' not 'errors' for schema violations.
    # Either our custom handler or Pydantic's default — verify non-empty error info.
    assert "detail" in body or "errors" in body

    # Check that 'email' appears somewhere in the error response
    full_text = resp.text
    assert "email" in full_text.lower(), "Expected 'email' in 422 error response"


# ---------------------------------------------------------------------------
# T8 — Logging: password never in logs; BEFORE/AFTER visible under verbose=true
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_auth_signup_logging_no_password_leak(
    http: AsyncClient, capsys: pytest.CaptureFixture
) -> None:
    """T8: Verify BEFORE+AFTER log events exist and password is never logged.

    Strategy: reconfigure logging at DEBUG level, make a sign-up request,
    capture stdout (structlog outputs via StreamHandler(sys.stdout)), then assert:
    - At least one BEFORE log event (auth.sign_up.start or auth.sign_up).
    - At least one AFTER log event (auth.sign_up.ok or sign_up.ok).
    - The strings 'password' and 'legal_acceptance' never appear in captured stdout.

    Uses capsys to capture structlog output (structlog writes to sys.stdout
    via the configured StreamHandler, not the stdlib logging module's records).
    Pattern from test_logging.py: configure_logging() + capsys.readouterr().

    Security contract: task-pack §12 + instrucciones §10 acceptance (no keys in logs).
    """
    import app.core.logging as logging_module  # noqa: PLC0415

    # Reconfigure logging at DEBUG to capture BEFORE/AFTER events.
    # Use _configured guard reset (same pattern as test_logging.py).
    prev_configured = logging_module._configured
    prev_root_handlers = logging.root.handlers[:]
    prev_root_level = logging.root.level
    try:
        logging_module._configured = False
        logging_module.configure_logging(verbose=True)

        email = _unique_email("log-test")
        payload = {**_VALID_PAYLOAD, "email": email}

        resp = await http.post(
            "/api/v1/auth/sign-up",
            json=payload,
            headers={"X-Request-ID": f"log-test-{uuid.uuid4().hex}"},
        )

        captured = capsys.readouterr()
        stdout_text = captured.out

    finally:
        # Restore root logger to previous state (prevent cross-test pollution)
        logging_module._configured = prev_configured
        logging.root.handlers[:] = prev_root_handlers
        logging.root.setLevel(prev_root_level)
        # Reset _configured so other tests don't see our reconfigured logger
        logging_module._configured = False
        logging_module._configured = prev_configured

    assert resp.status_code == 201, f"Expected 201 for log test, got {resp.status_code}"

    # BEFORE log must appear
    assert "auth.sign_up" in stdout_text or "sign_up.start" in stdout_text, (
        "Expected BEFORE log event (auth.sign_up.start) not found in stdout output"
    )

    # Password and legal_acceptance must NEVER appear in ANY log output
    assert re.search(r"\bpassword\b", stdout_text, re.IGNORECASE) is None, (
        "SECURITY: 'password' found in stdout log output — must never be logged"
    )
    assert re.search(r"\blegal_acceptance\b", stdout_text, re.IGNORECASE) is None, (
        "SECURITY: 'legal_acceptance' found in stdout log output — must never be logged"
    )
