"""
Hilo People — Unit/integration tests for app.security primitives.

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: 18 tests for the three security primitives:
           - TestEncryption  (6 tests) — pure encryption/decryption + key validation
           - TestPermissions (6 tests) — FastAPI Depends guards with real JWT + DB
           - TestRateLimit   (6 tests) — Redis-backed rate limiter with real Redis

         Tests use REAL services:
           - Fernet: real key generated inline, no mocks
           - JWT: real jwt.encode with same algorithm + key as encode_access_token
           - DB:  real Postgres (TestClient → FastAPI → real DB via get_db_session)
           - Redis: real local Redis (REDIS_URL=redis://localhost:6379/0)

         R5 invariant: if Redis is unreachable, TestRateLimit is skipped
         (not failed) because it is an integration test. Redis should be UP
         in docker compose dev env.

Key deps:
  - pytest / pytest-asyncio
  - app.security.{encryption, permissions, rate_limit, errors}
  - PyJWT == real jwt.encode for token minting (same key as encode_access_token)
  - app.db.models.user.{User, Role, UserRole}
  - app.auth.password.hash_password
  - fastapi.testclient.TestClient

Source refs:
  - task pack P02-S02-T001 §R6 (18 test names + acceptance criteria)
  - 01-non-negotiables.md §Tests are REAL
  - conftest.py (pg_engine + pg_session fixtures)

Decisions:
  - D-T1: TestClient app is created once per class to avoid repeated startup.
  - D-T2: Rate-limit tests use unique per-test prefix (UUID hex) so concurrent
    runs don't collide and DEL cleans up only the test's keys.
  - D-T3: TestRateLimit uses real Redis. Skip if unreachable (R5 fallback).
  - D-T4: reset_fernet_cache() called in setup/teardown for ENCRYPTION_KEY tests.
  - D-T5: Tokens for permissions tests are minted directly via jwt.encode using
    the JWT_PRIVATE_KEY + JWT_ALGORITHM env vars (same as encode_access_token does
    internally). This avoids SQLAlchemy DetachedInstanceError when accessing
    lazy-loaded user_roles after session close.
  - D-T6: DB users are created with real Postgres + real Argon2 hashes. The
    API's get_current_user dependency loads them from DB — this is the real
    integration chain: JWT → DB lookup → user_roles → role check.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import jwt as _jwt_lib
import pytest
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.auth.password import hash_password
from app.db.models.user import Role, User, UserRole
from app.main import app
from app.security._redis_client import close_redis_client, get_redis_client
from app.security.encryption import decrypt_secret, encrypt_secret, reset_fernet_cache
from app.security.errors import EncryptionError, EncryptionKeyError
from app.security.permissions import require_admin, require_auditor, require_role
from app.security.rate_limit import RateLimiter

# ---------------------------------------------------------------------------
# Environment setup — JWT key/algorithm read LAZILY (per token mint).
# ---------------------------------------------------------------------------
# Why lazy: when pytest collects tests from different directories
# (e.g., `pytest backend/tests -k security`), the root
# `backend/tests/conftest.py` is processed before
# `backend/tests/unit/conftest.py` loads .env. Capturing the key at import
# time meant the JWT signing key was an empty string and every minted token
# was signed with an empty secret, so app.users.deps.get_current_user
# rejected them with invalid_token. Lazy lookup is robust to pytest's
# collection order. (Debugger cycle 1 — P02-S02-T001.)


def _get_jwt_key() -> str:
    """Return JWT_PRIVATE_KEY at call time (lazy; survives collection order).

    Falls back to a deterministic test-only secret if the env var is empty
    so the test module is self-sufficient in isolation. The fallback is
    written back into os.environ so app code (e.g. app.auth.tokens) that
    reads the same variable lazily sees the same value.

    Returns:
        Non-empty JWT signing key.

    Raises:
        AssertionError: If the key is empty after fallback (defensive guard).
    """
    key = os.getenv("JWT_PRIVATE_KEY", "")
    if not key:
        key = "test-dev-jwt-secret-key-for-testing-only-32b+"
        os.environ["JWT_PRIVATE_KEY"] = key
    assert key, "JWT_PRIVATE_KEY must be non-empty for token minting"
    return key


def _get_jwt_alg() -> str:
    """Return JWT_ALGORITHM at call time (lazy; defaults to HS256)."""
    return os.getenv("JWT_ALGORITHM", "HS256")

# ---------------------------------------------------------------------------
# DB session helpers (real Postgres, matches conftest.py pattern)
# ---------------------------------------------------------------------------
_DEFAULT_DB_URL = "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev"
_TEST_DB_URL = os.getenv("DATABASE_URL", _DEFAULT_DB_URL).replace(
    "postgresql+asyncpg://", "postgresql+psycopg://"
)

_engine = create_engine(_TEST_DB_URL, pool_pre_ping=True)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

# Track users created by tests for cleanup
_created_user_ids: list[str] = []


class UserData(NamedTuple):
    """Lightweight user record safe after session close."""
    id: uuid.UUID
    email: str
    roles: list[str]


def _create_test_user(
    *,
    status: str = "active",
    roles: list[str] | None = None,
) -> UserData:
    """Create a real test user in Postgres with optional roles.

    Args:
        status: Account status ('active', 'inactive').
        roles:  List of role names to assign. Creates Role rows if needed.

    Returns:
        UserData with user_id, email, and list of role names.
    """
    email = f"security-test-{uuid.uuid4().hex[:8]}@inditex-sandbox.com"
    pw_hash = hash_password("TestPass2024!")
    session: Session = _SessionLocal()
    assigned_roles: list[str] = []

    try:
        user = User(
            email=email,
            password_hash=pw_hash,
            full_name="Security Test User",
            status=status,
            preferred_language="es",
        )
        session.add(user)
        session.flush()
        user_id: uuid.UUID = user.id

        if roles:
            for role_name in roles:
                role_row = session.query(Role).filter_by(name=role_name).first()
                if role_row is None:
                    role_row = Role(name=role_name)
                    session.add(role_row)
                    session.flush()
                ur = UserRole(user_id=user_id, role_id=role_row.id)
                session.add(ur)
                assigned_roles.append(role_name)

        session.commit()
        _created_user_ids.append(str(user_id))
        return UserData(id=user_id, email=email, roles=assigned_roles)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _sync_app_jwt_key() -> None:
    """Ensure app.auth.tokens lazy key cache is primed with the current env.

    P02-S02-T002 migration note: the original implementation mutated
    `app.auth.tokens._JWT_KEY` directly (T001 debugger workaround). That
    attribute no longer exists — _JWT_KEY is now a lazy @lru_cache getter
    (_get_jwt_key). Instead, we clear the cache so the next call re-reads
    the env var, which is the idiomatic way to force re-evaluation.

    WRITE_SET_DRIFT (Option I.3.b): backend/tests/unit/test_security.py was
    not in P02-S02-T002 write_set but must be updated to avoid AttributeError
    on the removed _JWT_KEY module attribute. See handoff §I.2.
    """
    from app.auth.tokens import _clear_jwt_key_cache
    _clear_jwt_key_cache()


def _mint_token(user_data: UserData) -> str:
    """Mint a real JWT access token for a test user.

    Uses the same JWT_PRIVATE_KEY + JWT_ALGORITHM as encode_access_token.
    Direct jwt.encode call avoids SQLAlchemy DetachedInstanceError (D-T5).
    Calls _sync_app_jwt_key() to ensure the app-side lazy key cache is
    primed with the current env value before the request hits decode_token.

    Args:
        user_data: UserData record with id, email, and roles.

    Returns:
        Encoded JWT string (same format as encode_access_token produces).
    """
    _sync_app_jwt_key()
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_data.id),
        "email": user_data.email,
        "roles": user_data.roles or ["employee"],
        "preferred_language": "es",
        "employee_profile_id": None,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=1800),
    }
    return _jwt_lib.encode(payload, _get_jwt_key(), algorithm=_get_jwt_alg())


def _cleanup_users() -> None:
    """Delete all test users created during this session."""
    if not _created_user_ids:
        return
    session: Session = _SessionLocal()
    try:
        for uid in _created_user_ids:
            session.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
        _created_user_ids.clear()


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestEncryption:
    """6 tests for app.security.encryption.

    Uses a real Fernet key generated inline. No Redis, no DB needed.
    """

    def setup_method(self) -> None:
        """Provision a valid ENCRYPTION_KEY before each test."""
        valid_key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = valid_key
        reset_fernet_cache()

    def teardown_method(self) -> None:
        """Remove ENCRYPTION_KEY after each test to avoid cross-test contamination."""
        os.environ.pop("ENCRYPTION_KEY", None)
        reset_fernet_cache()

    def test_encrypt_decrypt_roundtrip_plain_text(self) -> None:
        """T01: decrypt(encrypt(x)) == x for a plain text string."""
        plaintext = "hello world"
        ciphertext = encrypt_secret(plaintext)
        recovered = decrypt_secret(ciphertext)
        assert recovered == plaintext

    def test_encrypt_produces_different_ciphertexts_for_same_plaintext(self) -> None:
        """T02: Fernet uses random IV — two encryptions of same plaintext differ."""
        plaintext = "same-input-value"
        c1 = encrypt_secret(plaintext)
        c2 = encrypt_secret(plaintext)
        assert c1 != c2
        # Both must still decrypt to the same value.
        assert decrypt_secret(c1) == plaintext
        assert decrypt_secret(c2) == plaintext

    def test_encrypt_ciphertext_is_not_plaintext(self) -> None:
        """T03: Sanity — ciphertext does not contain the plaintext."""
        plaintext = "my-secret-api-key"
        ciphertext = encrypt_secret(plaintext)
        assert plaintext not in ciphertext

    def test_encryption_key_missing_raises(self) -> None:
        """T04: Missing ENCRYPTION_KEY raises EncryptionKeyError with hint."""
        os.environ.pop("ENCRYPTION_KEY", None)
        reset_fernet_cache()

        with pytest.raises(EncryptionKeyError) as exc_info:
            encrypt_secret("x")

        msg = str(exc_info.value)
        assert "ENCRYPTION_KEY" in msg
        assert "Fernet.generate_key" in msg

    def test_encryption_key_placeholder_raises(self) -> None:
        """T05: Placeholder 'replace-with-dev-key' raises EncryptionKeyError."""
        os.environ["ENCRYPTION_KEY"] = "replace-with-dev-key"
        reset_fernet_cache()

        with pytest.raises(EncryptionKeyError) as exc_info:
            encrypt_secret("x")

        msg = str(exc_info.value)
        assert "ENCRYPTION_KEY" in msg

    def test_decrypt_invalid_token_raises_typed_error(self) -> None:
        """T06: Fernet InvalidToken → mapped to typed EncryptionError."""
        valid_ct = encrypt_secret("hello")
        corrupted = valid_ct[:-4] + "XXXX"

        with pytest.raises(EncryptionError):
            decrypt_secret(corrupted)


class TestPermissions:
    """6 tests for app.security.permissions guards.

    Mounts a tiny throwaway APIRouter with guarded endpoints and exercises
    them via TestClient → real ASGI → real DB (via get_current_user dep).
    """

    @classmethod
    def setup_class(cls) -> None:
        """Mount test-only guarded endpoints and initialize TestClient."""
        test_router = APIRouter()

        @test_router.get("/__test_permissions__/admin-only")
        async def admin_only(user=Depends(require_admin)):
            """Test endpoint requiring people_admin or super_admin."""
            if hasattr(user, "id"):
                return {"user_id": str(user.id), "ok": True}
            return user

        @test_router.get("/__test_permissions__/auditor-only")
        async def auditor_only(user=Depends(require_auditor)):
            """Test endpoint requiring people_auditor or super_admin."""
            if hasattr(user, "id"):
                return {"user_id": str(user.id), "ok": True}
            return user

        @test_router.get("/__test_permissions__/role-factory")
        async def role_factory_endpoint(user=Depends(require_role("people_auditor"))):
            """Test endpoint using require_role factory."""
            if hasattr(user, "id"):
                return {"user_id": str(user.id), "ok": True}
            return user

        app.include_router(test_router)
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def teardown_class(cls) -> None:
        """Clean up created test users after all tests in this class."""
        _cleanup_users()

    @staticmethod
    def _auth_header(user_data: UserData) -> dict:
        """Build Authorization header with a real JWT for the test user.

        Args:
            user_data: UserData with id, email, and roles list.

        Returns:
            Dict with Authorization Bearer header.
        """
        token = _mint_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_require_user_returns_401_when_no_bearer(self) -> None:
        """T01: No Authorization header → 401 AUTH_SESSION_EXPIRED."""
        resp = self.client.get("/__test_permissions__/admin-only")
        assert resp.status_code == 401
        body = resp.json()
        assert body["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    def test_require_role_returns_401_when_no_bearer(self) -> None:
        """T02: require_role short-circuits to 401 when no bearer token."""
        resp = self.client.get("/__test_permissions__/auditor-only")
        assert resp.status_code == 401
        body = resp.json()
        assert body["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    def test_require_admin_returns_403_when_authenticated_but_missing_role(self) -> None:
        """T03: Valid bearer for employee-only user → 403 AUTH_PERMISSION_DENIED."""
        user_data = _create_test_user(roles=["employee"])
        resp = self.client.get(
            "/__test_permissions__/admin-only",
            headers=self._auth_header(user_data),
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body["errors"][0]["code"] == "AUTH_PERMISSION_DENIED"

    def test_require_admin_returns_200_for_people_admin_user(self) -> None:
        """T04: User with people_admin role → 200."""
        user_data = _create_test_user(roles=["people_admin"])
        resp = self.client.get(
            "/__test_permissions__/admin-only",
            headers=self._auth_header(user_data),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

    def test_require_admin_also_grants_super_admin(self) -> None:
        """T05: super_admin is a superset — require_admin accepts super_admin user."""
        user_data = _create_test_user(roles=["super_admin"])
        resp = self.client.get(
            "/__test_permissions__/admin-only",
            headers=self._auth_header(user_data),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

    def test_require_role_factory_composes_multi_role_users(self) -> None:
        """T06: User with [people_admin, people_auditor] passes require_role(people_auditor)."""
        user_data = _create_test_user(roles=["people_admin", "people_auditor"])
        resp = self.client.get(
            "/__test_permissions__/role-factory",
            headers=self._auth_header(user_data),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True


# ---------------------------------------------------------------------------
# Redis availability check for TestRateLimit
# ---------------------------------------------------------------------------
def _redis_is_available() -> bool:
    """Probe Redis with PING; return False if unreachable."""
    try:
        close_redis_client()
        client = get_redis_client()
        client.ping()
        return True
    except Exception:
        return False


_REDIS_AVAILABLE = _redis_is_available()


@pytest.mark.skipif(
    not _REDIS_AVAILABLE,
    reason="Real Redis not reachable — TestRateLimit skipped (R5 fallback)",
)
class TestRateLimit:
    """6 tests for app.security.rate_limit.RateLimiter.

    Requires real Redis (REDIS_URL=redis://localhost:6379/0).
    Uses unique per-test key prefixes (UUID hex) to avoid collisions.
    Cleans up only specific test keys in teardown (no FLUSHDB).
    """

    def setup_method(self) -> None:
        """Generate a unique test prefix and track created keys."""
        self._prefix = f"TEST_{uuid.uuid4().hex}"
        self._keys_to_clean: list[str] = []

    def teardown_method(self) -> None:
        """Delete only the test keys created by this test method."""
        if not self._keys_to_clean:
            return
        try:
            client = get_redis_client()
            client.delete(*self._keys_to_clean)
        except Exception:
            pass  # Best-effort cleanup

    def _make_limiter(
        self,
        per_minute: int = 10,
        burst: int = 10,
        window_seconds: int = 60,
    ) -> RateLimiter:
        """Build a RateLimiter with the unique test prefix."""
        return RateLimiter(
            prefix=self._prefix,
            per_minute=per_minute,
            burst=burst,
            window_seconds=window_seconds,
        )

    def _call_limiter_sync(
        self,
        limiter: RateLimiter,
        ip: str = "1.2.3.4",
    ):
        """Call the async RateLimiter synchronously in a new event loop.

        Builds a minimal mock Request with the given IP.

        Args:
            limiter: RateLimiter to call.
            ip:      Simulated client IP.

        Returns:
            JSONResponse on rate-limit hit; None on allow.
        """
        import asyncio
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": ip}
        mock_request.client = None

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(limiter(mock_request))
        finally:
            loop.close()

    def _track_key(self, limiter: RateLimiter, ip: str) -> None:
        """Register the Redis key that will be created for cleanup."""
        bucket = int(time.time() / limiter.window_seconds)
        key = f"{limiter.prefix}:{ip}:{bucket}"
        if key not in self._keys_to_clean:
            self._keys_to_clean.append(key)

    def test_rate_limit_allows_under_burst(self) -> None:
        """T01: burst=10 — 10 consecutive requests all return None (allowed)."""
        limiter = self._make_limiter(per_minute=10, burst=10)
        ip = "10.0.0.1"
        self._track_key(limiter, ip)

        results = [self._call_limiter_sync(limiter, ip=ip) for _ in range(10)]
        assert all(r is None for r in results), (
            "Expected all 10 requests to be allowed, got: "
            f"{[r.status_code if r else None for r in results]}"
        )

    def test_rate_limit_blocks_when_burst_exhausted(self) -> None:
        """T02: 11th request after burst=10 returns 429 with Retry-After header."""
        import json as _json

        limiter = self._make_limiter(per_minute=10, burst=10)
        ip = "10.0.0.2"
        self._track_key(limiter, ip)

        # Exhaust the burst.
        for _ in range(10):
            self._call_limiter_sync(limiter, ip=ip)

        # 11th must be blocked.
        result = self._call_limiter_sync(limiter, ip=ip)
        assert result is not None
        assert result.status_code == 429

        parsed = _json.loads(result.body)
        assert parsed["errors"][0]["code"] == "RATE_LIMITED"
        assert "Retry-After" in result.headers

    def test_rate_limit_resets_after_window_expires(self) -> None:
        """T03: After window_seconds=2 and sleep(3), bucket resets → allowed again."""
        limiter = self._make_limiter(per_minute=3, burst=3, window_seconds=2)
        ip = "10.0.0.3"
        self._track_key(limiter, ip)

        # Exhaust the bucket.
        for _ in range(3):
            self._call_limiter_sync(limiter, ip=ip)

        # Verify it's blocked.
        blocked = self._call_limiter_sync(limiter, ip=ip)
        assert blocked is not None, "Expected 4th call to be blocked"

        # Wait for window to expire.
        time.sleep(3)
        self._track_key(limiter, ip)  # new bucket key after sleep

        # Should be allowed again.
        result = self._call_limiter_sync(limiter, ip=ip)
        assert result is None, (
            f"Expected None (allowed) after window reset, "
            f"got status={result.status_code if result else None}"
        )

    def test_rate_limit_per_ip_isolation(self) -> None:
        """T04: IP_A exhausting its bucket does not affect IP_B."""
        limiter = self._make_limiter(per_minute=3, burst=3)
        ip_a = "192.168.1.1"
        ip_b = "192.168.1.2"
        self._track_key(limiter, ip_a)
        self._track_key(limiter, ip_b)

        # Exhaust IP_A.
        for _ in range(3):
            self._call_limiter_sync(limiter, ip=ip_a)
        assert self._call_limiter_sync(limiter, ip=ip_a) is not None  # IP_A blocked

        # IP_B should be unaffected.
        result_b = self._call_limiter_sync(limiter, ip=ip_b)
        assert result_b is None, (
            "IP_B should not be rate-limited when only IP_A was exhausted"
        )

    def test_rate_limit_per_prefix_isolation(self) -> None:
        """T05: Exhausting PREFIX_A does not affect PREFIX_B for the same IP."""
        ip = "10.10.10.10"
        prefix_a = f"{self._prefix}_A"
        prefix_b = f"{self._prefix}_B"

        limiter_a = RateLimiter(prefix=prefix_a, per_minute=3, burst=3)
        limiter_b = RateLimiter(prefix=prefix_b, per_minute=3, burst=3)

        bucket = int(time.time() / 60)
        self._keys_to_clean.extend([
            f"{prefix_a}:{ip}:{bucket}",
            f"{prefix_b}:{ip}:{bucket}",
        ])

        # Exhaust PREFIX_A.
        for _ in range(3):
            self._call_limiter_sync(limiter_a, ip=ip)
        assert self._call_limiter_sync(limiter_a, ip=ip) is not None  # A blocked

        # PREFIX_B should be fine.
        result_b = self._call_limiter_sync(limiter_b, ip=ip)
        assert result_b is None, (
            "PREFIX_B should not be rate-limited when only PREFIX_A was exhausted"
        )

    def test_rate_limit_logs_warning_on_exceeded_and_debug_under_verbose(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """T06: WARNING logged on exceeded; DEBUG BEFORE/AFTER logged under verbose."""
        limiter = self._make_limiter(per_minute=2, burst=2, window_seconds=60)
        ip = "10.20.30.40"
        self._track_key(limiter, ip)

        import app.security.rate_limit as rl_mod

        original_verbose = rl_mod._VERBOSE
        rl_mod._VERBOSE = True

        try:
            with caplog.at_level(logging.DEBUG, logger="app.security.rate_limit"):
                # Exhaust.
                self._call_limiter_sync(limiter, ip=ip)
                self._call_limiter_sync(limiter, ip=ip)
                # Trigger exceeded (3rd > burst=2).
                self._call_limiter_sync(limiter, ip=ip)

            warning_records = [
                r for r in caplog.records
                if r.levelno == logging.WARNING and "exceeded" in r.message.lower()
            ]
            assert len(warning_records) >= 1, (
                f"Expected at least 1 WARNING 'exceeded' record, got: "
                f"{[(r.levelname, r.message) for r in caplog.records]}"
            )

            debug_records = [
                r for r in caplog.records
                if r.levelno == logging.DEBUG
            ]
            assert len(debug_records) >= 1, (
                "Expected at least 1 DEBUG record under ENABLE_VERBOSE_LOGGING=true"
            )
        finally:
            rl_mod._VERBOSE = original_verbose
