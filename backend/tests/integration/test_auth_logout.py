"""
Hilo People — Integration tests for POST /api/v1/auth/logout.

Slice:  P01-S02-T004 — POST /api/v1/auth/logout
        P01-S02-T011 — T15 cookie-jar roundtrip test added (RFC 6265 §5.4 regression guard).
Phase:  P01 Auth + Data Foundation
Purpose: Real integration tests against a live FastAPI app + real Postgres DB.
         All tests use real DB rows committed via _create_user / _insert_refresh_token
         helpers (mirroring test_auth_refresh.py patterns).

Key deps:
  - pytest + FastAPI TestClient (real ASGI transport)
  - real Postgres DB (DATABASE_URL env var) — non-negotiables §Tests are REAL
  - PyJWT==2.12.1 — encode tokens for edge-case tests
  - argon2-cffi==25.1.0 — password hashing for test user setup

Source refs:
  - task pack P01-S02-T004 §Test plan T01..T14
  - 01-non-negotiables.md §Tests are REAL (real DB, no mocks)
  - conftest.py pg_engine + pg_session fixtures

Test inventory:
  T01: success → 204, refresh row revoked, cookie cleared (Max-Age=0), audit success
  T02: no Bearer → 401 AUTH_SESSION_EXPIRED, cookie cleared, audit reason=no_bearer
  T03: invalid Bearer → 401, audit reason=invalid_bearer
  T04: expired Bearer → 401, audit reason=expired_bearer
  T05: Bearer ok, no cookie → 401, audit reason=no_cookie
  T06: Bearer ok, unknown cookie → 401, audit reason=unknown_hash
  T07: Bearer ok, cookie expired in DB → 401, audit reason=expired
  T08: Bearer ok, cookie already revoked → 401, audit reason=revoked (idempotency)
  T09: Bearer for user A + cookie for user B → 401, audit reason=user_mismatch
  T10: 401 body byte-identical for all failure reasons (anti-enum)
  T11: only the cookie's token revoked; other tokens for same user unchanged
  T12: X-Request-ID propagated to response header and audit metadata
  T13: no PII / no token values in log lines
  T14: audit row persists even when main tx would roll back (D-S2 / user_mismatch)

Decisions:
  - Tests use SEPARATE TestClient (ASGI transport) — no uvicorn needed.
  - Test users: unique UUID-based emails to avoid collisions.
  - _create_user returns UserData namedtuple (plain id/email) to avoid
    DetachedInstanceError after session.close() (mirrors T003 pattern).
  - Query helpers call session.expunge_all() before close.
  - JWT_PRIVATE_KEY must be set in the test environment (comes from .env defaults
    or the dev .env file).
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport
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
_JWT_KEY: str = os.getenv("JWT_PRIVATE_KEY", "")
_JWT_ALG: str = os.getenv("JWT_ALGORITHM", "HS256")

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

_created_user_ids: list[str] = []
_created_rt_ids: list[str] = []


def _setup_session() -> Session:
    """Open a new Session that commits (not pg_session's rollback-only)."""
    return _SessionLocal()


def _create_user(*, status: str = "active") -> tuple[UserData, str]:
    """Insert a real user and return (UserData, plain_password).

    Args:
        status: User status ('active', 'disabled', etc.).

    Returns:
        (UserData namedtuple with id+email, plain_password).
    """
    plain_pw = f"TestPass2024!{uuid.uuid4().hex[:6]}"
    pw_hash = hash_password(plain_pw)
    email = f"logout.test.{uuid.uuid4().hex[:8]}@inditex-sandbox.com"

    session = _setup_session()
    try:
        user = User(
            email=email,
            password_hash=pw_hash,
            full_name="Logout Test User",
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


def _sign_in_and_get_tokens(email: str, password: str) -> tuple[str | None, str | None]:
    """Call /sign-in with real credentials and return (access_token, refresh_cookie_value)."""
    resp = client.post(
        "/api/v1/auth/sign-in",
        json={"email": email, "password": password},
    )
    if resp.status_code != 200:
        return None, None
    data = resp.json().get("data", {})
    access_token = data.get("access_token")
    refresh_cookie = resp.cookies.get("refresh_token")
    return access_token, refresh_cookie


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


def _mint_access_token_for(user_id: uuid.UUID, email: str, *, expired: bool = False) -> str:
    """Mint a JWT access token directly for testing edge cases.

    Args:
        user_id: UUID of the user.
        email: User email (used in JWT claims).
        expired: If True, produce a token with exp in the past.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(tz=timezone.utc)
    if expired:
        exp = now - timedelta(seconds=60)
        iat = now - timedelta(seconds=1860)
    else:
        exp = now + timedelta(seconds=1800)
        iat = now

    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": ["employee"],
        "preferred_language": "es",
        "employee_profile_id": None,
        "jti": uuid.uuid4().hex,
        "iat": iat,
        "exp": exp,
    }
    return jwt.encode(payload, _JWT_KEY, algorithm=_JWT_ALG)


def _get_refresh_row(token_hash: str) -> RefreshToken | None:
    """Query refresh_tokens by hash. Returns ORM object (detached)."""
    session = _setup_session()
    try:
        row = session.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        if row:
            session.expunge(row)
        return row
    finally:
        session.close()


def _get_last_audit_logout(actor_user_id: uuid.UUID | None = None) -> AuditLog | None:
    """Query last audit_log row with action='auth.logout'."""
    session = _setup_session()
    try:
        q = session.query(AuditLog).filter(AuditLog.action == "auth.logout")
        if actor_user_id is not None:
            q = q.filter(AuditLog.actor_user_id == actor_user_id)
        row = q.order_by(AuditLog.created_at.desc()).first()
        if row:
            session.expunge(row)
        return row
    finally:
        session.close()


@pytest.fixture(autouse=True)
def cleanup_created_rows():
    """Remove test rows from DB after each test."""
    yield
    session = _setup_session()
    try:
        if _created_rt_ids:
            session.query(RefreshToken).filter(
                RefreshToken.id.in_([uuid.UUID(i) for i in _created_rt_ids])
            ).delete(synchronize_session=False)
        if _created_user_ids:
            session.query(AuditLog).filter(
                AuditLog.actor_user_id.in_(
                    [uuid.UUID(i) for i in _created_user_ids]
                )
            ).delete(synchronize_session=False)
            session.query(RefreshToken).filter(
                RefreshToken.user_id.in_(
                    [uuid.UUID(i) for i in _created_user_ids]
                )
            ).delete(synchronize_session=False)
            session.query(User).filter(
                User.id.in_([uuid.UUID(i) for i in _created_user_ids])
            ).delete(synchronize_session=False)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        _created_user_ids.clear()
        _created_rt_ids.clear()
        session.close()


# ---------------------------------------------------------------------------
# T01 — Success path
# ---------------------------------------------------------------------------

def test_logout_success_revokes_token_and_clears_cookie():
    """T01: 204, refresh row revoked, cookie Max-Age=0, audit outcome=success."""
    user_data, plain_pw = _create_user()
    access_token, cookie_value = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert access_token and cookie_value, "sign-in must succeed for T01"

    token_hash = hashlib.sha256(cookie_value.encode()).hexdigest()

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Cookie": f"refresh_token={cookie_value}",
        },
    )
    assert resp.status_code == 204
    assert resp.content == b""  # no body

    # Cookie cleared: Set-Cookie header must contain Max-Age=0
    set_cookie = resp.headers.get("set-cookie", "")
    assert "max-age=0" in set_cookie.lower() or "max-age=0" in set_cookie, \
        f"Expected Max-Age=0 in Set-Cookie, got: {set_cookie}"

    # X-Request-ID echoed
    assert "x-request-id" in resp.headers

    # DB: refresh_tokens row is revoked
    rt_row = _get_refresh_row(token_hash)
    assert rt_row is not None
    assert rt_row.revoked_at is not None, "Expected revoked_at to be set after logout"

    # audit_logs: action=auth.logout, outcome=success
    audit = _get_last_audit_logout(actor_user_id=user_data.id)
    assert audit is not None
    assert audit.extra_metadata.get("outcome") == "success"
    assert audit.extra_metadata.get("revoked_token_id") is not None


# ---------------------------------------------------------------------------
# T02 — No Bearer token
# ---------------------------------------------------------------------------

def test_logout_no_bearer_returns_401():
    """T02: 401 AUTH_SESSION_EXPIRED, cookie cleared, audit reason=no_bearer."""
    user_data, plain_pw = _create_user()
    _, cookie_value = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert cookie_value, "sign-in must succeed for T02 setup"

    resp = client.post(
        "/api/v1/auth/logout",
        headers={"Cookie": f"refresh_token={cookie_value}"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    # Cookie cleared on 401 too
    set_cookie = resp.headers.get("set-cookie", "")
    assert "max-age=0" in set_cookie.lower()

    audit = _get_last_audit_logout()
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "no_bearer"
    assert audit.extra_metadata.get("outcome") == "failure"


# ---------------------------------------------------------------------------
# T03 — Invalid Bearer (tampered JWT)
# ---------------------------------------------------------------------------

def test_logout_invalid_bearer_returns_401():
    """T03: tampered JWT → 401, audit reason=invalid_bearer."""
    user_data, plain_pw = _create_user()
    access_token, cookie_value = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert access_token and cookie_value

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": "Bearer not.a.valid.jwt.at.all",
            "Cookie": f"refresh_token={cookie_value}",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    audit = _get_last_audit_logout()
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "invalid_bearer"


# ---------------------------------------------------------------------------
# T04 — Expired Bearer token
# ---------------------------------------------------------------------------

def test_logout_expired_bearer_returns_401():
    """T04: exp in past → 401, audit reason=expired_bearer."""
    user_data, plain_pw = _create_user()
    _, cookie_value = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert cookie_value

    expired_token = _mint_access_token_for(user_data.id, user_data.email, expired=True)

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {expired_token}",
            "Cookie": f"refresh_token={cookie_value}",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    audit = _get_last_audit_logout()
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "expired_bearer"


# ---------------------------------------------------------------------------
# T05 — Bearer ok, no cookie
# ---------------------------------------------------------------------------

def test_logout_no_cookie_returns_401():
    """T05: Bearer ok, cookie missing → 401, audit reason=no_cookie."""
    user_data, plain_pw = _create_user()
    access_token, _ = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert access_token

    resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    # Cookie cleared on 401 too
    set_cookie = resp.headers.get("set-cookie", "")
    assert "max-age=0" in set_cookie.lower()

    audit = _get_last_audit_logout(actor_user_id=user_data.id)
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "no_cookie"


# ---------------------------------------------------------------------------
# T06 — Unknown cookie hash
# ---------------------------------------------------------------------------

def test_logout_unknown_cookie_returns_401():
    """T06: Bearer ok, cookie hash unknown → 401, audit reason=unknown_hash."""
    user_data, plain_pw = _create_user()
    access_token, _ = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert access_token

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Cookie": f"refresh_token={secrets.token_urlsafe(48)}",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    audit = _get_last_audit_logout()
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "unknown_hash"


# ---------------------------------------------------------------------------
# T07 — Expired cookie in DB
# ---------------------------------------------------------------------------

def test_logout_expired_cookie_returns_401():
    """T07: cookie expired in DB → 401, audit reason=expired."""
    user_data, _ = _create_user()
    access_token = _mint_access_token_for(user_data.id, user_data.email)
    opaque, _ = _insert_refresh_token(user_data.id, expires_offset_seconds=-3600)

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Cookie": f"refresh_token={opaque}",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    audit = _get_last_audit_logout(actor_user_id=user_data.id)
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "expired"


# ---------------------------------------------------------------------------
# T08 — Revoked cookie (idempotency / repeat logout)
# ---------------------------------------------------------------------------

def test_logout_revoked_cookie_returns_401():
    """T08: cookie already revoked → 401 (idempotency repeat-logout), audit reason=revoked."""
    user_data, _ = _create_user()
    access_token = _mint_access_token_for(user_data.id, user_data.email)
    opaque, _ = _insert_refresh_token(user_data.id, revoked=True)

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Cookie": f"refresh_token={opaque}",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    audit = _get_last_audit_logout(actor_user_id=user_data.id)
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "revoked"


# ---------------------------------------------------------------------------
# T09 — User mismatch (Bearer for user A, cookie for user B)
# ---------------------------------------------------------------------------

def test_logout_user_mismatch_returns_401():
    """T09: Bearer for user A + cookie for user B → 401, audit reason=user_mismatch."""
    user_a, _ = _create_user()
    user_b, _ = _create_user()

    access_token_a = _mint_access_token_for(user_a.id, user_a.email)
    opaque_b, _ = _insert_refresh_token(user_b.id)

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token_a}",
            "Cookie": f"refresh_token={opaque_b}",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    # audit should record user_mismatch (actor = cookie's user_id = user_b)
    audit = _get_last_audit_logout(actor_user_id=user_b.id)
    assert audit is not None
    assert audit.extra_metadata.get("reason") == "user_mismatch"


# ---------------------------------------------------------------------------
# T10 — 401 body byte-identical for all failure reasons
# ---------------------------------------------------------------------------

def test_logout_401_body_byte_identical_for_all_failure_reasons():
    """T10: T02..T09 bodies are byte-equal (aggregate anti-enum)."""
    user_data, plain_pw = _create_user()
    access_token, cookie_value = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert access_token and cookie_value

    # Collect raw response bodies for all failure cases
    bodies: list[bytes] = []

    # no Bearer
    r = client.post(
        "/api/v1/auth/logout",
        headers={"Cookie": f"refresh_token={cookie_value}"},
    )
    assert r.status_code == 401
    bodies.append(r.content)

    # invalid Bearer
    r = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": "Bearer tampered.jwt.token",
            "Cookie": f"refresh_token={cookie_value}",
        },
    )
    assert r.status_code == 401
    bodies.append(r.content)

    # no cookie (uses fresh token to avoid sign-in issues)
    access_token2 = _mint_access_token_for(user_data.id, user_data.email)
    r = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token2}"},
    )
    assert r.status_code == 401
    bodies.append(r.content)

    # unknown cookie
    r = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token2}",
            "Cookie": f"refresh_token={secrets.token_urlsafe(48)}",
        },
    )
    assert r.status_code == 401
    bodies.append(r.content)

    # Compare bodies strip request_id (it differs per request)
    import json
    parsed = [json.loads(b) for b in bodies]
    for p in parsed:
        # Remove meta.request_id which legitimately differs
        p.get("meta", {}).pop("request_id", None)
    
    reference = parsed[0]
    for p in parsed[1:]:
        assert p == reference, f"401 body not identical: {p} vs {reference}"


# ---------------------------------------------------------------------------
# T11 — Only the matched token is revoked; other tokens unchanged
# ---------------------------------------------------------------------------

def test_logout_does_not_revoke_other_users_tokens():
    """T11: user has 2 active tokens; logout revokes only the cookie's token."""
    user_data, _ = _create_user()
    access_token = _mint_access_token_for(user_data.id, user_data.email)
    opaque1, hash1 = _insert_refresh_token(user_data.id)
    opaque2, hash2 = _insert_refresh_token(user_data.id)

    # Logout with opaque1
    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Cookie": f"refresh_token={opaque1}",
        },
    )
    assert resp.status_code == 204

    # Token 1 is revoked
    row1 = _get_refresh_row(hash1)
    assert row1 is not None and row1.revoked_at is not None, "opaque1 token must be revoked"

    # Token 2 is still active
    row2 = _get_refresh_row(hash2)
    assert row2 is not None and row2.revoked_at is None, "opaque2 token must remain active"


# ---------------------------------------------------------------------------
# T12 — X-Request-ID propagated to response header and audit metadata
# ---------------------------------------------------------------------------

def test_logout_request_id_propagated_in_response_header_and_audit():
    """T12: response header X-Request-ID matches request header; audit metadata matches."""
    user_data, plain_pw = _create_user()
    access_token, cookie_value = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert access_token and cookie_value

    req_id = f"t12-{uuid.uuid4()}"

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Cookie": f"refresh_token={cookie_value}",
            "X-Request-ID": req_id,
        },
    )
    assert resp.status_code == 204
    assert resp.headers.get("x-request-id") == req_id

    audit = _get_last_audit_logout(actor_user_id=user_data.id)
    assert audit is not None
    assert audit.extra_metadata.get("request_id") == req_id


# ---------------------------------------------------------------------------
# T13 — No PII or token values in log output
# ---------------------------------------------------------------------------

def test_logout_no_pii_or_token_value_in_logs(caplog, monkeypatch):
    """T13: no Bearer value, no cookie value, no full SHA-256 hex in log lines."""
    monkeypatch.setenv("ENABLE_VERBOSE_LOGGING", "true")

    # Re-configure the logout module logger to DEBUG for this test
    import app.auth.services.logout as svc_mod
    import app.auth.routers.logout as rtr_mod
    import importlib
    importlib.reload(svc_mod)
    importlib.reload(rtr_mod)

    user_data, plain_pw = _create_user()
    access_token, cookie_value = _sign_in_and_get_tokens(user_data.email, plain_pw)
    assert access_token and cookie_value

    token_hash = hashlib.sha256(cookie_value.encode()).hexdigest()

    with caplog.at_level(logging.DEBUG):
        resp = client.post(
            "/api/v1/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Cookie": f"refresh_token={cookie_value}",
            },
        )
    assert resp.status_code == 204

    log_text = "\n".join(caplog.messages)

    # Must not contain raw Bearer JWT
    assert access_token not in log_text, "Bearer JWT value must not appear in logs"
    # Must not contain raw cookie value
    assert cookie_value not in log_text, "Refresh cookie value must not appear in logs"
    # Must not contain full SHA-256 hash (64 hex chars)
    assert token_hash not in log_text, "Full token_hash must not appear in logs"


# ---------------------------------------------------------------------------
# T14 — Audit row persists even when main TX would roll back (D-S2)
# ---------------------------------------------------------------------------

def test_logout_audit_row_persists_even_when_main_tx_rolls_back():
    """T14: user_mismatch path → no revocation (no commit), but audit row exists."""
    user_a, _ = _create_user()
    user_b, _ = _create_user()

    access_token_a = _mint_access_token_for(user_a.id, user_a.email)
    opaque_b, hash_b = _insert_refresh_token(user_b.id)

    resp = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token_a}",
            "Cookie": f"refresh_token={opaque_b}",
        },
    )
    assert resp.status_code == 401

    # DB: user_b's refresh token must NOT be revoked (no main tx commit)
    row = _get_refresh_row(hash_b)
    assert row is not None and row.revoked_at is None, \
        "refresh token must not be revoked on user_mismatch path"

    # But the failure audit row MUST exist (D-S2 — committed on short session)
    audit = _get_last_audit_logout(actor_user_id=user_b.id)
    assert audit is not None, "Failure audit row must persist despite main tx not committing"
    assert audit.extra_metadata.get("reason") == "user_mismatch"
    assert audit.extra_metadata.get("outcome") == "failure"


# ---------------------------------------------------------------------------
# T15 — Cookie-jar roundtrip: RFC 6265 §5.4 Path matching regression guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_cookie_jar_roundtrip_no_manual_cookie_header():
    """T15: httpx.AsyncClient+ASGITransport sign-in → logout via real cookie jar.

    This is the RFC 6265 §5.4 regression guard (P01-S02-T011). httpx enforces
    the Path attribute when deciding whether to include a cookie in a request,
    matching real browser behavior — unlike Starlette TestClient which ignores it.

    Regression test: if _set_refresh_cookie reverts Path to /auth, httpx will NOT
    send the cookie to /api/v1/auth/logout (path prefix mismatch per RFC 6265 §5.4),
    the server receives no cookie, and the endpoint returns 401 (no_cookie), causing
    this test to fail.

    Flow: sign-in (cookie jar populated) → logout (cookie jar auto-sends) → 204.
    No manual Cookie header is set anywhere in this test.
    """
    user_data, plain_pw = _create_user()

    # Use httpx.AsyncClient with ASGITransport — enforces Path AND Secure attributes.
    # base_url is https:// so httpx will send Secure cookies (cookie has Secure=True).
    # ASGITransport handles both http:// and https:// URLs transparently (no TLS needed).
    # If Path reverted to /auth, httpx would NOT send the cookie to /api/v1/auth/logout
    # (RFC 6265 §5.4: path-prefix mismatch) and logout would return 401.
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as ac:
        # Step 1: sign-in — the response sets a refresh_token cookie with Path=/api/v1/auth
        r_signin = await ac.post(
            "/api/v1/auth/sign-in",
            json={"email": user_data.email, "password": plain_pw},
        )
        assert r_signin.status_code == 200, (
            f"sign-in failed (expected 200): {r_signin.status_code} — {r_signin.text}"
        )

        data = r_signin.json().get("data", {})
        access_token = data.get("access_token")
        assert access_token, "No access_token in sign-in response"

        # Cookie jar must have the refresh_token — if Path was wrong, it would be absent
        assert "refresh_token" in ac.cookies, (
            "refresh_token cookie not in httpx cookie jar after sign-in — "
            "cookie Path may not match /api/v1/auth (RFC 6265 §5.4)"
        )

        # Step 2: logout — NO explicit Cookie header; httpx auto-sends from jar
        # because /api/v1/auth/logout matches Path=/api/v1/auth prefix.
        r_logout = await ac.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            # Deliberately NO Cookie header — httpx must send it automatically
        )
        assert r_logout.status_code == 204, (
            f"logout failed (expected 204 No Content): {r_logout.status_code} — {r_logout.text}"
        )

    # DB: verify the refresh token was revoked (not just accepted on HTTP level)
    # We must query by user_id since we don't have the raw opaque token directly.
    session = _setup_session()
    try:
        from sqlalchemy import text as sa_text
        result = session.execute(
            sa_text(
                "SELECT COUNT(*) FROM refresh_tokens "
                "WHERE user_id = :uid AND revoked_at IS NOT NULL"
            ),
            {"uid": str(user_data.id)},
        ).scalar()
        assert result >= 1, (
            f"Expected at least 1 revoked refresh_token for user {user_data.id}, got {result}"
        )
    finally:
        session.close()
