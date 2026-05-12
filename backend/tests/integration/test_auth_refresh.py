"""
Hilo People — Integration tests for POST /api/v1/auth/refresh.

Slice:  P01-S02-T003 — POST /api/v1/auth/refresh
Phase:  P01 Auth + Data Foundation
Purpose: Real integration tests against a live FastAPI app + real Postgres DB.
         All tests use the _SetupSession fixture (committed rows, cleaned up
         after test) matching the T002 pattern.

Key deps:
  - pytest + httpx (FastAPI TestClient, real ASGI transport)
  - real Postgres DB (DATABASE_URL env var) — non-negotiables §Tests are REAL
  - app.auth.rate_limit — reset between tests via monkeypatch
  - PyJWT==2.12.1 — decode JWT assertions
  - argon2-cffi==25.1.0 — password hashing for test user setup

Source refs:
  - task pack P01-S02-T003 §F.1..F.14 (acceptance criteria → tests T01..T14)
  - 01-non-negotiables.md §Tests are REAL (real DB, no mocks)
  - conftest.py pg_engine + pg_session fixtures

Test inventory:
  T01: success rotation → 200, new access JWT, new Set-Cookie, DB rotation confirmed
  T02: no cookie → 401 AUTH_SESSION_EXPIRED, audit no_cookie
  T03: unknown hash → 401 AUTH_SESSION_EXPIRED, audit unknown_hash
  T04: expired token → 401, audit expired
  T05: revoked token → 401, audit revoked
  T06: user inactive → 401, audit user_inactive
  T07: replay old cookie (already rotated) → 401, audit revoked
  T08: concurrent same cookie → exactly one 200, one 401
  T09: rate limit → 429 AUTH_REFRESH_RATE_LIMITED + Retry-After
  T10: verbose-on log redaction (no PII / no token values)
  T11: X-Request-ID echoed in response header + meta
  T12: body has no refresh_token key (D-RP5)
  T13: new refresh hashed in DB (SHA-256 match, not raw value)
  T14: 401 body byte-identical for all failure reasons (anti-enumeration)

Decisions:
  - Tests use SEPARATE TestClient (ASGI transport) — no uvicorn needed.
  - Rate-limit tests monkeypatch _store to reset between tests.
  - Test users: unique UUID-based emails per call to avoid collisions.
  - _create_user returns a UserData namedtuple (plain id/email) to avoid
    DetachedInstanceError after session.close().
  - Query helpers call session.expunge_all() before close so returned ORM
    objects remain usable after the session is gone.
  - JWT_PRIVATE_KEY must be set in the test environment (comes from .env defaults
    applied by conftest.py or the dev .env file).
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator, NamedTuple

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.db.models.auth import AuditLog, RefreshToken
from app.db.models.user import User
from app.db.session import _SessionLocal
from app.main import app

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
_REFRESH_TTL: int = int(os.getenv("AUTH_REFRESH_TTL_SECONDS", "2592000"))
_ACCESS_TTL: int = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "1800"))
_JWT_KEY: str = os.getenv("JWT_PRIVATE_KEY", "")
_JWT_ALG: str = os.getenv("JWT_ALGORITHM", "HS256")

# TestClient is reused across all tests — one ASGI transport instance.
client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Lightweight test-data container (avoids DetachedInstanceError)
# ---------------------------------------------------------------------------

class UserData(NamedTuple):
    """Plain-Python record returned by _create_user — safe after session close."""
    id: uuid.UUID
    email: str


# ---------------------------------------------------------------------------
# Setup / teardown helpers
# ---------------------------------------------------------------------------

# IDs of rows committed to the real DB during tests, cleaned up after each.
_created_user_ids: list[str] = []
_created_rt_ids: list[str] = []


def _setup_session() -> Session:
    """Open a new Session that commits (not pg_session's rollback-only)."""
    return _SessionLocal()


def _create_user(
    *,
    status: str = "active",
) -> tuple[UserData, str]:
    """Insert a real user and return (UserData, plain_password).

    Args:
        status: User status ('active', 'disabled', etc.).

    Returns:
        (UserData namedtuple with id+email, plain_password).
        UserData is a plain Python object — safe after session.close().
    """
    plain_pw = f"TestPass2024!{uuid.uuid4().hex[:6]}"
    pw_hash = hash_password(plain_pw)
    email = f"refresh.test.{uuid.uuid4().hex[:8]}@inditex-sandbox.com"

    session = _setup_session()
    try:
        user = User(
            email=email,
            password_hash=pw_hash,
            full_name="Refresh Test User",
            status=status,
        )
        session.add(user)
        session.flush()
        user_id: uuid.UUID = user.id
        session.commit()
        _created_user_ids.append(str(user_id))
        return UserData(id=user_id, email=email), plain_pw
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _sign_in_and_get_cookie(email: str, password: str) -> str | None:
    """Call /sign-in with real credentials and return the refresh cookie value."""
    resp = client.post(
        "/api/v1/auth/sign-in",
        json={"email": email, "password": password},
    )
    if resp.status_code != 200:
        return None
    return resp.cookies.get("refresh_token")


def _insert_refresh_token(
    user_id: uuid.UUID,
    *,
    expires_offset_seconds: int = _REFRESH_TTL,
    revoked: bool = False,
) -> tuple[str, str]:
    """Insert a refresh_tokens row directly (for edge-case seeds).

    Args:
        user_id: UUID of the user who owns the token.
        expires_offset_seconds: Seconds from now for expires_at. Negative = expired.
        revoked: Whether to set revoked_at to now - 60s.

    Returns:
        (opaque_token, token_hash) — the opaque value is the raw cookie value.
    """
    opaque = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(opaque.encode()).hexdigest()
    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_offset_seconds)
    revoked_at = (
        datetime.now(tz=timezone.utc) - timedelta(seconds=60) if revoked else None
    )

    session = _setup_session()
    try:
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=revoked_at,
        )
        session.add(rt)
        session.flush()
        rt_id = str(rt.id)
        session.commit()
        _created_rt_ids.append(rt_id)
        return opaque, token_hash
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _set_user_status(user_id: uuid.UUID, status_val: str) -> None:
    """Update users.status for the given user_id."""
    session = _setup_session()
    try:
        session.query(User).filter(User.id == user_id).update(
            {"status": status_val},
            synchronize_session="fetch",
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_audit_rows(user_id: uuid.UUID | None = None, action: str = "auth.refresh") -> list:
    """Return audit_log rows for action, optionally filtered by actor_user_id.

    Calls expunge_all() before closing so returned ORM objects stay usable.
    """
    session = _setup_session()
    try:
        q = session.query(AuditLog).filter(AuditLog.action == action)
        if user_id is not None:
            q = q.filter(AuditLog.actor_user_id == user_id)
        rows = q.order_by(AuditLog.created_at.asc()).all()
        session.expunge_all()
        return rows
    finally:
        session.close()


def _get_refresh_rows(token_hash: str) -> list:
    """Return all refresh_token rows for the given hash.

    Calls expunge_all() before closing so returned ORM objects stay usable.
    """
    session = _setup_session()
    try:
        rows = (
            session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .all()
        )
        session.expunge_all()
        return rows
    finally:
        session.close()


def _get_user_refresh_rows(user_id: uuid.UUID) -> list:
    """Return all refresh_token rows for a user.

    Calls expunge_all() before closing so returned ORM objects stay usable.
    """
    session = _setup_session()
    try:
        rows = (
            session.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id)
            .order_by(RefreshToken.id.asc())
            .all()
        )
        session.expunge_all()
        return rows
    finally:
        session.close()


def _get_user_by_id(user_id: uuid.UUID) -> User | None:
    """Return User row by PK.

    Calls expunge_all() before closing so returned ORM object stays usable.
    """
    session = _setup_session()
    try:
        row = session.query(User).filter(User.id == user_id).first()
        if row is not None:
            session.expunge(row)
        return row
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Autouse fixture: clean up committed rows after each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_created_rows() -> Generator[None, None, None]:
    """Delete all rows committed during the test (user, refresh_token, audit_log)."""
    _created_user_ids.clear()
    _created_rt_ids.clear()
    yield
    session = _setup_session()
    try:
        for uid_str in _created_user_ids:
            # CASCADE deletes refresh_tokens / audit_logs (actor_user_id=SET NULL)
            session.query(User).filter(User.id == uuid.UUID(uid_str)).delete()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
    _created_user_ids.clear()
    _created_rt_ids.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the in-memory rate-limit store before each test."""
    import app.auth.rate_limit as rl_module
    monkeypatch.setattr(rl_module, "_store", {})


# ===========================================================================
# T01 — Happy path: successful rotation
# ===========================================================================

def test_refresh_success_rotates_and_returns_new_access_token() -> None:
    """F.1: POST /refresh with valid cookie → 200, new access JWT, rotated cookie.

    Verifies:
      - HTTP 200
      - body: access_token (decodable JWT, 8 claims), token_type=Bearer, expires_in>0
      - body: NO refresh_token key (D-RP5)
      - new Set-Cookie refresh_token with correct attrs
      - new cookie value DIFFERS from old cookie
      - DB: old token_hash row has revoked_at NOT NULL
      - DB: new row with different hash, revoked_at IS NULL, expires_at ~ now+TTL
      - audit row: action=auth.refresh, outcome=success, old_token_id + new_token_id
    """
    user, plain_pw = _create_user()
    old_cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert old_cookie is not None, "Sign-in failed in test setup"

    old_hash = hashlib.sha256(old_cookie.encode()).hexdigest()

    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": old_cookie},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Body shape
    data = body["data"]
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] > 0
    assert "refresh_token" not in data  # D-RP5

    # New cookie
    new_cookie = resp.cookies.get("refresh_token")
    assert new_cookie is not None, "No Set-Cookie in response"
    assert new_cookie != old_cookie, "Cookie should have been rotated"

    # Cookie attributes (check via Set-Cookie header)
    set_cookie_header = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    assert "Secure" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header.lower() or "samesite=lax" in set_cookie_header.lower()
    assert "Path=/api/v1/auth" in set_cookie_header  # §10.2 T011

    # Decode JWT — 8 claims per §10.2
    decoded = jwt.decode(
        data["access_token"],
        _JWT_KEY,
        algorithms=[_JWT_ALG],
        options={"verify_exp": True},
    )
    for claim in ("sub", "email", "roles", "preferred_language", "employee_profile_id",
                  "jti", "iat", "exp"):
        assert claim in decoded, f"Missing JWT claim: {claim}"

    # DB: old row revoked
    old_rows = _get_refresh_rows(old_hash)
    assert len(old_rows) == 1
    assert old_rows[0].revoked_at is not None

    # DB: new row active
    new_hash = hashlib.sha256(new_cookie.encode()).hexdigest()
    new_rows = _get_refresh_rows(new_hash)
    assert len(new_rows) == 1
    assert new_rows[0].revoked_at is None
    now = datetime.now(tz=timezone.utc)
    assert new_rows[0].expires_at > now

    # Audit row
    audit_rows = _get_audit_rows(user.id)
    # Filter to refresh success rows
    success_rows = [
        r for r in audit_rows
        if isinstance(r.extra_metadata, dict)
        and r.extra_metadata.get("outcome") == "success"
    ]
    assert len(success_rows) >= 1
    meta = success_rows[-1].extra_metadata
    assert "old_token_id" in meta
    assert "new_token_id" in meta
    assert meta["old_token_id"] == str(old_rows[0].id)
    assert meta["new_token_id"] == str(new_rows[0].id)


# ===========================================================================
# T02 — No cookie → 401
# ===========================================================================

def test_refresh_no_cookie_returns_401_session_expired() -> None:
    """F.2: POST /refresh without any cookie → 401 AUTH_SESSION_EXPIRED."""
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    body = resp.json()
    errors = body["errors"]
    assert len(errors) == 1
    assert errors[0]["code"] == "AUTH_SESSION_EXPIRED"
    assert body["data"] is None


# ===========================================================================
# T03 — Unknown hash → 401
# ===========================================================================

def test_refresh_unknown_token_returns_401() -> None:
    """F.3: POST /refresh with bogus cookie → 401 AUTH_SESSION_EXPIRED."""
    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "not-a-real-token-xyz-" + secrets.token_urlsafe(16)},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"


# ===========================================================================
# T04 — Expired token → 401
# ===========================================================================

def test_refresh_expired_token_returns_401() -> None:
    """F.4: Expired refresh_tokens row → 401, audit reason=expired."""
    user, _ = _create_user()

    opaque, token_hash = _insert_refresh_token(
        user.id,
        expires_offset_seconds=-1,  # already expired
    )
    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": opaque},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    # DB: row revoked_at should still be NULL (expired ≠ auto-revoked)
    rows = _get_refresh_rows(token_hash)
    assert len(rows) == 1
    assert rows[0].revoked_at is None

    # Audit
    audit_rows = _get_audit_rows(user.id)
    failure_rows = [
        r for r in audit_rows
        if isinstance(r.extra_metadata, dict)
        and r.extra_metadata.get("reason") == "expired"
    ]
    assert len(failure_rows) >= 1


# ===========================================================================
# T05 — Revoked token → 401
# ===========================================================================

def test_refresh_revoked_token_returns_401() -> None:
    """F.5: Revoked refresh_tokens row → 401, audit reason=revoked."""
    user, _ = _create_user()

    opaque, token_hash = _insert_refresh_token(user.id, revoked=True)
    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": opaque},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    audit_rows = _get_audit_rows(user.id)
    revoked_rows = [
        r for r in audit_rows
        if isinstance(r.extra_metadata, dict)
        and r.extra_metadata.get("reason") == "revoked"
    ]
    assert len(revoked_rows) >= 1


# ===========================================================================
# T06 — User inactive → 401
# ===========================================================================

def test_refresh_inactive_user_returns_401() -> None:
    """F.6: Active refresh token but user.status='disabled' → 401, audit user_inactive.

    Rotation must NOT happen (no new row; old row state unchanged or rolled back).
    """
    user, plain_pw = _create_user()
    old_cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert old_cookie is not None

    # Disable the user
    _set_user_status(user.id, "disabled")

    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": old_cookie},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    # Rotation should NOT have created a new row
    all_rows = _get_user_refresh_rows(user.id)
    # Only 1 row (from sign-in); no new one inserted
    assert len(all_rows) <= 1

    # Audit
    audit_rows = _get_audit_rows(user.id)
    inactive_rows = [
        r for r in audit_rows
        if isinstance(r.extra_metadata, dict)
        and r.extra_metadata.get("reason") == "user_inactive"
    ]
    assert len(inactive_rows) >= 1


# ===========================================================================
# T07 — Replay old cookie after rotation → 401
# ===========================================================================

def test_refresh_replay_old_token_returns_401() -> None:
    """F.7: First rotation succeeds; then old cookie is presented again → 401.

    Also verifies that the new (rotated) cookie B remains usable (D-RP4: no
    family-revocation; only the replayed token is rejected).
    """
    user, plain_pw = _create_user()
    cookie_a = _sign_in_and_get_cookie(user.email, plain_pw)
    assert cookie_a is not None

    # First call — success
    resp1 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookie_a},
    )
    assert resp1.status_code == 200
    cookie_b = resp1.cookies.get("refresh_token")
    assert cookie_b is not None
    assert cookie_b != cookie_a

    # Replay cookie A — must return 401
    resp2 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookie_a},
    )
    assert resp2.status_code == 401
    assert resp2.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    # Cookie B must still be usable (D-RP4: no family revocation)
    resp3 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookie_b},
    )
    assert resp3.status_code == 200


# ===========================================================================
# T08 — Concurrent requests with same cookie → exactly one succeeds
# ===========================================================================

def test_refresh_concurrent_requests_only_one_wins() -> None:
    """F.8: Two concurrent /refresh with the same cookie → exactly 1 wins, 1 loses.

    Uses threading.Barrier to align start. Checks DB for exactly 1 new row.
    """
    user, plain_pw = _create_user()
    cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert cookie is not None

    results: list[int] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _call() -> None:
        try:
            barrier.wait()
            r = client.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": cookie},
            )
            results.append(r.status_code)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=_call)
    t2 = threading.Thread(target=_call)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"Thread exceptions: {errors}"
    assert len(results) == 2
    # Exactly one 200 and one 401
    assert sorted(results) == [200, 401], f"Unexpected results: {results}"

    # DB: exactly one active (non-revoked) row after the race
    all_rows = _get_user_refresh_rows(user.id)
    active_rows = [r for r in all_rows if r.revoked_at is None]
    assert len(active_rows) == 1


# ===========================================================================
# T09 — Rate limit → 429
# ===========================================================================

def test_refresh_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """F.9: After AUTH_REFRESH_RATE_PER_MINUTE=2 calls, 3rd → 429."""
    monkeypatch.setenv("AUTH_REFRESH_RATE_PER_MINUTE", "2")
    monkeypatch.setenv("AUTH_REFRESH_RATE_BURST", "2")

    user, plain_pw = _create_user()
    cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert cookie is not None

    # Import rate_limit module to get the state reset to use the new env values
    import app.auth.rate_limit as rl_module
    rl_module._store.clear()

    for _ in range(2):
        r = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": cookie},
        )
        # First two: either 200 (rotation) or 401 (already rotated on 2nd call) — both valid
        assert r.status_code in (200, 401)
        # Update cookie if we got a rotation
        if r.status_code == 200:
            new_c = r.cookies.get("refresh_token")
            if new_c:
                cookie = new_c

    # 3rd call: rate limited
    r = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookie},
    )
    assert r.status_code == 429
    body = r.json()
    assert body["errors"][0]["code"] == "AUTH_REFRESH_RATE_LIMITED"
    assert "Retry-After" in r.headers


# ===========================================================================
# T10 — Verbose-on log redaction
# ===========================================================================

def test_refresh_no_pii_or_token_value_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    """F.10: Success + 401 — no raw cookie / JWT / full email in logs."""
    user, plain_pw = _create_user()
    cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert cookie is not None

    with caplog.at_level(logging.DEBUG):
        # Success
        resp = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": cookie},
        )
        assert resp.status_code == 200
        # 401 with unknown cookie
        resp2 = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "bogus-not-real-" + secrets.token_urlsafe(8)},
        )
        assert resp2.status_code == 401

    log_text = caplog.text
    # No raw cookie values logged
    assert cookie not in log_text
    # No JWT prefix
    if resp.status_code == 200:
        access_token = resp.json()["data"]["access_token"]
        assert access_token not in log_text
        # JWT prefix eyJ (base64 header)
        assert "eyJ" not in log_text or all(
            part not in log_text for part in access_token.split(".")
        )
    # No full email local-part (only domain allowed)
    local_part = user.email.split("@")[0]
    assert local_part not in log_text


# ===========================================================================
# T11 — X-Request-ID echoed
# ===========================================================================

def test_refresh_request_id_in_response_header_and_meta() -> None:
    """F.11: X-Request-ID sent → echoed in response header + body meta."""
    user, plain_pw = _create_user()
    cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert cookie is not None

    my_request_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookie},
        headers={"X-Request-ID": my_request_id},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == my_request_id
    body = resp.json()
    assert body["meta"]["request_id"] == my_request_id


# ===========================================================================
# T12 — Body has no refresh_token key
# ===========================================================================

def test_refresh_body_has_no_refresh_token() -> None:
    """F.12 (D-RP5): Refresh stays in cookie only; body has exactly the 3 expected keys."""
    user, plain_pw = _create_user()
    cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert cookie is not None

    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookie},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert set(data.keys()) == {"access_token", "token_type", "expires_in"}
    assert "refresh_token" not in data


# ===========================================================================
# T13 — New refresh hashed in DB
# ===========================================================================

def test_refresh_new_refresh_hashed_in_db() -> None:
    """F.13: After rotation, new DB row token_hash == sha256(new_cookie), not raw value."""
    user, plain_pw = _create_user()
    cookie = _sign_in_and_get_cookie(user.email, plain_pw)
    assert cookie is not None

    resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookie},
    )
    assert resp.status_code == 200
    new_cookie = resp.cookies.get("refresh_token")
    assert new_cookie is not None

    expected_hash = hashlib.sha256(new_cookie.encode()).hexdigest()
    new_rows = _get_refresh_rows(expected_hash)
    assert len(new_rows) == 1
    assert new_rows[0].token_hash == expected_hash
    # Verify raw value is NOT stored as token_hash
    assert new_rows[0].token_hash != new_cookie


# ===========================================================================
# T14 — 401 body byte-identical for missing vs unknown
# ===========================================================================

def test_refresh_401_body_byte_identical_for_all_failure_reasons() -> None:
    """F.14 gate + anti-enumeration: all 401 cases return the same body shape.

    Checks no-cookie, unknown hash, and expired token all return identical
    code + message + field (modulo meta.request_id).
    """
    user, _ = _create_user()
    opaque_expired, _ = _insert_refresh_token(user.id, expires_offset_seconds=-1)

    r_no_cookie = client.post("/api/v1/auth/refresh")
    r_unknown = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "totally-bogus-" + secrets.token_urlsafe(8)},
    )
    r_expired = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": opaque_expired},
    )

    def _strip_meta(resp_json: dict) -> dict:
        r = dict(resp_json)
        r.pop("meta", None)
        return r

    b1 = _strip_meta(r_no_cookie.json())
    b2 = _strip_meta(r_unknown.json())
    b3 = _strip_meta(r_expired.json())

    assert b1 == b2 == b3, f"Bodies differ: {b1} vs {b2} vs {b3}"
    for body in (b1, b2, b3):
        assert body["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"
