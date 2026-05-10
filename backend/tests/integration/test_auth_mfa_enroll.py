"""
Integration tests for POST /api/v1/auth/2fa/enroll.

Slice: P01-S02-T009 — POST /api/v1/auth/2fa/enroll
Phase: P01 — Auth + Base Capabilities

All tests use REAL Postgres at 127.0.0.1:5433 and the REAL FastAPI app.
No mocking of business logic, repositories, or the DB.

Test inventory (task-pack §8):
  T1 — Happy path: fresh user sign-up → enroll → 201 with valid otpauth_url + QR PNG.
  T2 — Re-auth fail: wrong password → 401 AUTH_INVALID_CREDENTIALS (generic).
  T3 — Re-auth fail: unknown email → 401 AUTH_INVALID_CREDENTIALS (same as T2).
  T4 — Idempotency (rotation): enroll twice → 201 both times; second has new secret.
  T5 — Decrypt-roundtrip: secret in DB decrypts to same value as in otpauth_url.
  T6 — Logging contract: secret_b32 and otpauth_url NEVER appear in stdout.
  T7 — Payload malformed: missing password field → 422.

Fixture strategy:
  - autouse `reset_db_engine_singleton` resets app.core.db singleton before each test
    (critical for pytest-asyncio asyncio_mode=auto event-loop-per-test — MEMORY.md).
  - `db_session` provides a NullPool async session with per-test rollback.
  - `http` provides an AsyncClient via ASGITransport (non-deprecated httpx pattern).
  - Each test creates a unique email via UUID to avoid cross-test conflicts.

Dependencies:
  - pytest 9.0.3, pytest-asyncio 1.3.0 (asyncio_mode=auto)
  - httpx 0.28.1 (AsyncClient + ASGITransport)
  - sqlalchemy[asyncio] 2.0.49, asyncpg 0.31.0
  - pyotp 2.9.0 (TOTP smoke verification in T1, T4, T5)
  - app.main:app (ASGI app)
  - app.core.security.decrypt_secret (Fernet roundtrip in T5)
"""
from __future__ import annotations

import base64
import re
import socket
import uuid
from collections.abc import AsyncGenerator

import pyotp
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

# Test credentials — strong password satisfying T001 policy.
_TEST_PASSWORD = "Enroll$Secure1Aa!"


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


def _fresh_email() -> str:
    """Return a unique test email to avoid cross-test conflicts."""
    return f"mfa-enroll-test+{uuid.uuid4().hex[:8]}@gmail.com"


# ---------------------------------------------------------------------------
# Engine singleton reset autouse fixture (MEMORY.md critical pattern)
# ---------------------------------------------------------------------------
# pytest-asyncio asyncio_mode=auto creates a NEW event loop per test.
# The production app.core.db module holds a singleton AsyncEngine (_engine)
# bound to the creating event loop. Reusing it across tests causes
# "Future attached to a different loop" — fix: reset before each test.


@pytest.fixture(autouse=True)
def reset_db_engine_singleton() -> None:
    """Reset the app.core.db singleton engine before each test.

    Prevents asyncpg 'attached to a different loop' errors across tests.
    Pattern from MEMORY.md P01-S02-T001 entry (pytest-asyncio asyncio_mode=auto).
    """
    import app.core.db as db_module  # noqa: PLC0415

    db_module._engine = None
    db_module._session_factory = None
    yield
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
# Per-test DB session fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session with NullPool + per-test rollback.

    NullPool prevents asyncpg from recycling connections across event loops.
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
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def http() -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient using ASGITransport against the real FastAPI app.

    Uses httpx.AsyncClient with ASGITransport (not the deprecated `app=` form).
    """
    from app.main import app  # noqa: PLC0415

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helper: create a fresh user via sign-up endpoint
# ---------------------------------------------------------------------------


async def _signup_user(http: AsyncClient, email: str) -> None:
    """Create a fresh user via POST /api/v1/auth/sign-up."""
    resp = await http.post(
        "/api/v1/auth/sign-up",
        json={
            "email": email,
            "password": _TEST_PASSWORD,
            "full_name": "MFA Enroll Tester",
            "legal_acceptance": True,
        },
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp.status_code == 201, f"sign-up failed: {resp.text}"


# ---------------------------------------------------------------------------
# T1 — Happy path: fresh sign-up → enroll → 201 with valid otpauth_url + QR PNG
# ---------------------------------------------------------------------------


@_skip_no_db
async def test_t1_happy_path(http: AsyncClient, db_session: AsyncSession) -> None:
    """T1: Fresh user enrolls MFA → 201 with valid data + DB row + audit log.

    Assertions:
    - 201 response with otpauth_url starting with 'otpauth://totp/Hilo%20People:'
    - qr_png_base64 decodes to PNG (magic bytes \\x89PNG)
    - mfa_totp_secrets row exists with enabled=false and non-null secret_encrypted
    - decrypt_secret(secret_encrypted) yields 32-char base32 matching otpauth secret
    - pyotp.TOTP(decrypted).verify(pyotp.TOTP(decrypted).now()) is True (A4)
    - audit_logs has 1 row with action='auth.2fa_enroll' for this user
    - rotation=False in audit metadata (fresh enroll)
    - secret_b32 does NOT appear in captured stdout (D6 log hygiene — see T6)
    """
    email = _fresh_email()
    await _signup_user(http, email)

    resp = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": email, "password": _TEST_PASSWORD},
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "data" in body, f"Missing 'data' key: {body}"
    data = body["data"]

    # A1 — otpauth_url format
    assert "otpauth_url" in data
    assert data["otpauth_url"].startswith(
        "otpauth://totp/Hilo%20People:"
    ), f"Unexpected otpauth_url prefix: {data['otpauth_url'][:50]}"

    # A1 — qr_png_base64 is a valid PNG
    assert "qr_png_base64" in data
    raw = base64.b64decode(data["qr_png_base64"])
    assert raw[:4] == b"\x89PNG", "qr_png_base64 does not decode to a PNG"

    # Extract user_id from sign-up response (we need it to query DB)
    # Re-query via db_session to find the mfa_totp_secrets row
    result = await db_session.execute(
        text(
            "SELECT user_id, secret_encrypted, enabled "
            "FROM mfa_totp_secrets "
            "WHERE user_id = (SELECT id FROM users WHERE email = :email)"
        ),
        {"email": email},
    )
    row = result.fetchone()
    assert row is not None, "No mfa_totp_secrets row found for fresh user"

    user_id = row[0]
    secret_encrypted = row[1]
    enabled = row[2]

    # A2 — row shape
    assert secret_encrypted is not None and len(secret_encrypted) > 50, (
        f"secret_encrypted too short: {len(secret_encrypted)}"
    )
    assert enabled is False, f"enabled should be False, got {enabled}"

    # A3 + A4 — decrypt roundtrip + TOTP smoke
    from app.core.security import decrypt_secret  # noqa: PLC0415

    decrypted = decrypt_secret(secret_encrypted)
    assert re.match(r"^[A-Z2-7]{32}$", decrypted), (
        f"Decrypted secret is not 32-char base32: '{decrypted}'"
    )

    totp = pyotp.TOTP(decrypted)
    code = totp.now()
    assert totp.verify(code), "pyotp.TOTP(decrypted).verify(code) should be True"

    # A5 — audit_log row
    audit_result = await db_session.execute(
        text(
            "SELECT action, resource, request_id, metadata "
            "FROM audit_logs "
            "WHERE actor_user_id = :uid AND action = 'auth.2fa_enroll' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"uid": user_id},
    )
    audit_row = audit_result.fetchone()
    assert audit_row is not None, "No audit_log row with action='auth.2fa_enroll'"
    assert audit_row[0] == "auth.2fa_enroll"
    assert audit_row[1] == "POST /api/v1/auth/2fa/enroll"
    assert audit_row[2] is not None, "request_id should be non-NULL in audit_log"

    # A6 — enabled=false
    # (already checked above)

    # A7 (fresh enroll) — rotation=false in metadata
    metadata = audit_row[3]
    assert metadata.get("rotation") is False, f"Unexpected rotation in audit: {metadata}"


# ---------------------------------------------------------------------------
# T2 — Re-auth fail: wrong password → 401
# ---------------------------------------------------------------------------


@_skip_no_db
async def test_t2_wrong_password(http: AsyncClient) -> None:
    """T2: Wrong password → 401 AUTH_INVALID_CREDENTIALS (generic message)."""
    email = _fresh_email()
    await _signup_user(http, email)

    resp = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": email, "password": "WrongPassword99!Aa"},
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "errors" in body
    assert body["errors"][0]["code"] == "AUTH_INVALID_CREDENTIALS"
    # Generic message — must NOT say "user not found" vs "password mismatch"
    msg = body["errors"][0]["message"].lower()
    assert "user not found" not in msg
    assert "not found" not in msg
    assert "password" not in msg


# ---------------------------------------------------------------------------
# T3 — Re-auth fail: unknown email → same 401 as T2
# ---------------------------------------------------------------------------


@_skip_no_db
async def test_t3_unknown_email(http: AsyncClient) -> None:
    """T3: Unknown email → 401 AUTH_INVALID_CREDENTIALS (same as wrong password T2).

    Time-constant response prevents user enumeration via timing (task-pack §8).
    """
    resp = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={
            "email": f"unknown-{uuid.uuid4().hex}@nonexistent.example",
            "password": _TEST_PASSWORD,
        },
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "errors" in body
    assert body["errors"][0]["code"] == "AUTH_INVALID_CREDENTIALS"


# ---------------------------------------------------------------------------
# T4 — Idempotency (rotation): enroll twice → second has new secret + 2 audit rows
# ---------------------------------------------------------------------------


@_skip_no_db
async def test_t4_idempotency_rotation(
    http: AsyncClient, db_session: AsyncSession
) -> None:
    """T4: Re-enroll rotates secret + resets enabled=false + adds audit_log entry.

    Assertions per A7 (D2, task-pack §9 D2):
    - Both enrollments return 201.
    - mfa_totp_secrets has same user_id (PK) but different secret_encrypted after 2nd.
    - 2 audit_log rows with action='auth.2fa_enroll' for this user.
    - 2nd audit metadata.rotation = True.
    """
    email = _fresh_email()
    await _signup_user(http, email)

    # First enroll
    resp1 = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": email, "password": _TEST_PASSWORD},
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp1.status_code == 201, f"First enroll failed: {resp1.text}"

    # Fetch first secret_encrypted from DB
    result1 = await db_session.execute(
        text(
            "SELECT secret_encrypted FROM mfa_totp_secrets "
            "WHERE user_id = (SELECT id FROM users WHERE email = :email)"
        ),
        {"email": email},
    )
    first_encrypted = result1.scalar_one()

    # Second enroll (rotation)
    resp2 = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": email, "password": _TEST_PASSWORD},
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp2.status_code == 201, f"Second enroll failed: {resp2.text}"

    # Fetch updated secret_encrypted
    # Need a fresh execution to see committed data; the app commits inside get_session.
    # Because our db_session is rollback_only, we check via a direct new query.
    result2 = await db_session.execute(
        text(
            "SELECT secret_encrypted, enabled FROM mfa_totp_secrets "
            "WHERE user_id = (SELECT id FROM users WHERE email = :email)"
        ),
        {"email": email},
    )
    row2 = result2.fetchone()
    second_encrypted = row2[0]
    enabled_after_rotation = row2[1]

    # Secret must change on rotation
    assert first_encrypted != second_encrypted, (
        "secret_encrypted should change on re-enroll (rotation)"
    )
    assert enabled_after_rotation is False, "enabled must remain False after rotation"

    # 2 audit_log rows for this user
    audit_count_result = await db_session.execute(
        text(
            "SELECT COUNT(*), "
            "MAX(CASE WHEN metadata->>'rotation' = 'true' THEN 1 ELSE 0 END) "
            "FROM audit_logs "
            "WHERE actor_user_id = (SELECT id FROM users WHERE email = :email) "
            "AND action = 'auth.2fa_enroll'"
        ),
        {"email": email},
    )
    count_row = audit_count_result.fetchone()
    assert count_row[0] == 2, f"Expected 2 audit_log rows, got {count_row[0]}"
    assert count_row[1] == 1, "Second audit_log should have rotation=true"


# ---------------------------------------------------------------------------
# T5 — Decrypt-roundtrip: secret in DB == secret in otpauth_url
# ---------------------------------------------------------------------------


@_skip_no_db
async def test_t5_decrypt_roundtrip(
    http: AsyncClient, db_session: AsyncSession
) -> None:
    """T5: decrypt_secret(DB secret_encrypted) == secret in otpauth_url ?secret= param.

    Verifies A3: the Fernet-encrypted value in mfa_totp_secrets decrypts to the same
    base32 secret that was embedded in the otpauth_url response.
    """
    email = _fresh_email()
    await _signup_user(http, email)

    resp = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": email, "password": _TEST_PASSWORD},
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp.status_code == 201

    otpauth_url = resp.json()["data"]["otpauth_url"]

    # Extract secret from ?secret=<value>& in the URL
    match = re.search(r"[?&]secret=([A-Z2-7]+)", otpauth_url)
    assert match, f"Could not extract ?secret= from otpauth_url: {otpauth_url[:80]}"
    secret_in_url = match.group(1)

    # Decrypt from DB
    result = await db_session.execute(
        text(
            "SELECT secret_encrypted FROM mfa_totp_secrets "
            "WHERE user_id = (SELECT id FROM users WHERE email = :email)"
        ),
        {"email": email},
    )
    secret_encrypted = result.scalar_one()

    from app.core.security import decrypt_secret  # noqa: PLC0415

    decrypted = decrypt_secret(secret_encrypted)

    assert decrypted == secret_in_url, (
        f"DB decrypted secret '{decrypted}' != URL secret '{secret_in_url}'"
    )


# ---------------------------------------------------------------------------
# T6 — Logging contract: secret and otpauth_url NEVER in stdout (CWE-532 D6)
# ---------------------------------------------------------------------------


@_skip_no_db
async def test_t6_log_hygiene(http: AsyncClient, capsys: pytest.CaptureFixture) -> None:
    """T6: Logging contract — secret_b32 and otpauth_url NEVER appear in stdout.

    Dual-mode check:
    verbose=true  → BEFORE/AFTER events visible; secret/otpauth ABSENT.
    verbose=false → 0 INFO lines from enroll flow; warnings only if any.

    CWE-532 D6: neither the base32 secret (32 uppercase alphanum chars) nor
    the otpauth:// URL should appear anywhere in captured output.
    """
    from app.core.logging import configure_logging  # noqa: PLC0415

    # --- Verbose=true pass ---
    configure_logging(verbose=True)
    email = _fresh_email()
    await _signup_user(http, email)

    resp = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": email, "password": _TEST_PASSWORD},
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp.status_code == 201

    # Extract the actual secret from the response to grep for it
    otpauth_url = resp.json()["data"]["otpauth_url"]
    match = re.search(r"[?&]secret=([A-Z2-7]+)", otpauth_url)
    assert match, "Could not extract secret from otpauth_url"
    secret_b32 = match.group(1)

    captured_verbose = capsys.readouterr()
    verbose_out = captured_verbose.out + captured_verbose.err

    # D6: base32 secret MUST NOT appear in any log line
    assert secret_b32 not in verbose_out, (
        "CWE-532 violation: secret_b32 found in verbose stdout"
    )
    # D6: full otpauth_url MUST NOT appear in any log line
    assert "otpauth://" not in verbose_out, (
        "CWE-532 violation: otpauth:// found in verbose stdout"
    )

    # --- Verbose=false pass ---
    configure_logging(verbose=False)
    email2 = _fresh_email()
    await _signup_user(http, email2)

    resp2 = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": email2, "password": _TEST_PASSWORD},
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp2.status_code == 201

    captured_quiet = capsys.readouterr()
    quiet_out = captured_quiet.out + captured_quiet.err

    # verbose=false: no INFO lines from enroll BEFORE/AFTER events
    # (check by looking for our event names — they should not appear)
    assert "auth.mfa.enroll.start" not in quiet_out, (
        "INFO log 'auth.mfa.enroll.start' leaked in verbose=false mode"
    )
    assert "auth.mfa.enroll.secret_generated" not in quiet_out, (
        "INFO log 'auth.mfa.enroll.secret_generated' leaked in verbose=false mode"
    )


# ---------------------------------------------------------------------------
# T7 — Payload malformed: missing password → 422
# ---------------------------------------------------------------------------


@_skip_no_db
async def test_t7_missing_password(http: AsyncClient) -> None:
    """T7: Malformed payload (missing password) → 422.

    Note (task-pack §5.3 R3): T012 pending for unified envelope shape.
    This test accepts both FastAPI default {detail} and project envelope {errors}
    as valid shapes while T012 is not implemented.
    """
    resp = await http.post(
        "/api/v1/auth/2fa/enroll",
        json={"email": "test@example.com"},  # missing 'password'
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    body = resp.json()
    # Accept either FastAPI default shape OR project envelope (T012 pending)
    assert "detail" in body or "errors" in body, (
        f"Unexpected 422 body shape: {body}"
    )
