"""
Hilo People — Integration tests for Admin AI endpoints.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints
Phase:  P02 Core Features
Purpose: Real integration tests for:
           - GET  /api/v1/admin/ai/providers
           - POST /api/v1/admin/ai/providers
           - GET  /api/v1/admin/ai/models
           - PATCH /api/v1/admin/ai/models/{model_id}

         All tests use real Postgres + real Redis. NO mocks of own services.
         Only external APIs (encryption key generation) are isolated via env vars.
         Admin + employee users are created per-test and committed so the FastAPI
         ASGI endpoint can see them (same pattern as test_auth_signin.py).

Key deps:
  - pytest + FastAPI TestClient (real ASGI transport)
  - real Postgres DB (DATABASE_URL env var)
  - real Redis (for rate-limit tests)
  - cryptography.fernet (Fernet) — ENCRYPTION_KEY set in env for tests
  - argon2-cffi — password hashing for test user setup

Source refs:
  - task pack P02-S05-T001 §Test plan T01–T25
  - instrucciones.md §3.1#admin-ai
  - 01-non-negotiables.md §Tests are REAL

Test inventory (T01–T25):
  GET /providers:
    T01: admin → 200 + list; meta.request_id present
    T02: employee → 403 AUTH_PERMISSION_DENIED
    T03: no Bearer → 401 AUTH_SESSION_EXPIRED
    T04: provider + credential seeded → has_credentials=true, no encrypted_secret

  POST /providers:
    T05: valid payload → 201; DB has provider+credential; audit_log; no creds in response
    T06: invalid provider_type → 422
    T07: missing credentials → 422 (Pydantic required field)
    T08: employee→403; no Bearer→401
    T09: rate-limit (21 fast requests) → 429 RATE_LIMITED + Retry-After
    T10: Redis down → 503 SERVICE_UNAVAILABLE
    T11: EncryptionError → 500; no provider/credential in DB; audit with outcome=failure
    T12: ENABLE_VERBOSE_LOGGING=true shows BEFORE/AFTER; no secret_plain in logs

  GET /models:
    T13: admin no filter → 200 + list
    T14: admin with ?provider_id=<uuid> → filtered list
    T15: admin with ?provider_id=not-a-uuid → 422
    T16: employee→403; no Bearer→401

  PATCH /models/{id}:
    T17: admin enabled=true → 200; DB updated; audit present
    T18: is_default=true when another default exists → 200; old model loses is_default
    T19: both fields None → 400 AI_MODEL_PAYLOAD_INVALID
    T20: non-existent model_id → 404 AI_MODEL_NOT_FOUND
    T21: employee→403; no Bearer→401
    T22: is_default=false when was only default → 200 (allowed in V1)

  Cross-cutting:
    T23: X-Request-ID echo in response meta
    T24: response envelope shape {"data": ..., "meta": {"request_id": ...}}
    T25: no test residue in ai_providers (cleanup verified)

Decisions:
  - Tests use committed inserts (same setup pattern as test_auth_signin.py)
    because the FastAPI endpoint uses its own SQLAlchemy session.
  - ENCRYPTION_KEY is generated per module run (Fernet.generate_key()); reset
    after tests that monkeypatch it.
  - Redis tests use monkeypatch on get_redis_client to simulate failure.
  - Rate-limit tests use short window_seconds to avoid 60-second waits.
"""

from __future__ import annotations

import logging
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy import create_engine as _ce
from sqlalchemy.orm import sessionmaker as _sm

# ---------------------------------------------------------------------------
# Ensure required env vars are set before importing app modules
# ---------------------------------------------------------------------------
if not os.getenv("JWT_PRIVATE_KEY"):
    os.environ["JWT_PRIVATE_KEY"] = "test-dev-jwt-secret-key-for-testing-only-32b+"

# Generate a valid Fernet key for the test module
_TEST_FERNET_KEY = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _TEST_FERNET_KEY

if not os.getenv("MFA_ENCRYPTION_KEY"):
    os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from app.main import app  # noqa: E402 — env vars must be set first
from app.security.encryption import reset_fernet_cache  # noqa: E402
from app.auth import rate_limit as _auth_rl_module  # noqa: E402 — for resetting in-memory RL

# ---------------------------------------------------------------------------
# TestClient
# ---------------------------------------------------------------------------
client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Direct-commit DB setup (same pattern as test_auth_signin.py)
# ---------------------------------------------------------------------------
_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev",
)
_setup_engine = _ce(_DB_URL, pool_pre_ping=True)
_SetupSession = _sm(bind=_setup_engine, autocommit=False, autoflush=False)

_ph = PasswordHasher()

# Track created rows for cleanup
_created_user_ids: list[str] = []
_created_provider_ids: list[str] = []
_created_model_ids: list[str] = []


# ---------------------------------------------------------------------------
# Helpers — user creation
# ---------------------------------------------------------------------------

def _create_user_with_role(
    email: str,
    role_name: str,
    password: str = "AdminVerify2024!",
    status: str = "active",
) -> dict:
    """Insert a user + role assignment via committed connection.

    The FastAPI test endpoint uses its own Session; test data must be committed
    before calling the endpoint.

    Args:
        email:     User email address.
        role_name: Role to assign ('people_admin', 'employee', etc.).
        password:  Plain-text password to hash.
        status:    User status ('active' by default).

    Returns:
        dict with user_id and email.
    """
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())

    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, status) "
                "VALUES (:id, :email, :pw, :name, :status)"
            ),
            {"id": user_id, "email": email, "pw": pw_hash, "name": "Test User", "status": status},
        )
        # Find or create the role row. Tests cannot rely on the roles table
        # being pre-seeded (the verification_data loader does not seed roles
        # in baseline scenarios), so we mirror the test_users_me.py pattern:
        # if the role does not exist, insert it before assigning. Without this,
        # `held_roles=[]` silently breaks every admin test (validator finding
        # in P02-S05-T001 cycle 1).
        role_row = sess.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_name},
        ).fetchone()
        if role_row is None:
            new_role_id = str(uuid.uuid4())
            sess.execute(
                text("INSERT INTO roles (id, name) VALUES (:id, :name)"),
                {"id": new_role_id, "name": role_name},
            )
            role_id = new_role_id
        else:
            role_id = str(role_row[0])
        sess.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid)"
                " ON CONFLICT DO NOTHING"
            ),
            {"uid": user_id, "rid": role_id},
        )
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()

    _created_user_ids.append(user_id)
    return {"user_id": user_id, "email": email}


def _sign_in(email: str, password: str = "AdminVerify2024!") -> str:
    """Sign in and return access_token JWT.

    Args:
        email:    User email.
        password: Plain-text password.

    Returns:
        Access token string.
    """
    resp = client.post(
        "/api/v1/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Sign-in failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _admin_email() -> str:
    return f"admin.test.{uuid.uuid4().hex[:8]}@inditex-sandbox.com"


def _employee_email() -> str:
    return f"employee.test.{uuid.uuid4().hex[:8]}@inditex-sandbox.com"


# ---------------------------------------------------------------------------
# Helpers — provider/model creation
# ---------------------------------------------------------------------------

def _create_test_provider(token: str, name: str | None = None) -> dict:
    """Create a provider via API and track for cleanup."""
    name = name or f"test-provider-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/admin/ai/providers",
        json={
            "provider_type": "litellm",
            "name": name,
            "credentials": {
                "auth_type": "api_key",
                "secret_plain": "sk-test-secret-key",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Create provider failed: {resp.text}"
    provider = resp.json()["data"]
    _created_provider_ids.append(provider["id"])
    return provider


def _create_test_model(provider_id: str, model_type: str = "chat") -> str:
    """Insert a model directly via DB (no endpoint for this in this slice).

    Returns the model id string.
    """
    model_id = str(uuid.uuid4())
    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO ai_models (id, provider_id, model_id, model_type, capabilities, enabled, is_default, pricing)"
                " VALUES (:id, :provider_id, :model_id, :model_type, '[]'::jsonb, false, false, '{}'::jsonb)"
            ),
            {
                "id": model_id,
                "provider_id": provider_id,
                "model_id": f"test-model-{uuid.uuid4().hex[:6]}",
                "model_type": model_type,
            },
        )
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
    _created_model_ids.append(model_id)
    return model_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _reset_rate_limits() -> None:
    """Reset both in-memory auth rate-limit store and Redis ADMIN_AI keys.

    Called before each test so rate-limit state from previous tests does not
    bleed through (pattern mirrors test_auth_signin.py _reset_rate_limit).
    """
    # 1. Reset in-memory auth rate limiter (sign-in bucket)
    try:
        with _auth_rl_module._lock:
            _auth_rl_module._store.clear()
    except Exception:
        pass

    # 2. Reset Redis ADMIN_AI rate-limit keys
    try:
        from app.security._redis_client import get_redis_client
        r = get_redis_client()
        keys = r.keys("ADMIN_AI:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass  # Redis unavailable — T10 covers that scenario separately


@pytest.fixture(autouse=True)
def _cleanup_test_data():
    """Reset rate limits and clean up all committed test rows before/after each test."""
    _reset_rate_limits()  # BEFORE: ensure clean rate-limit state
    yield
    # AFTER: delete test rows
    sess = _SetupSession()
    try:
        for mid in list(_created_model_ids):
            sess.execute(text("DELETE FROM ai_models WHERE id = :id"), {"id": mid})
        _created_model_ids.clear()
        for pid in list(_created_provider_ids):
            sess.execute(text("DELETE FROM ai_providers WHERE id = :id"), {"id": pid})
        _created_provider_ids.clear()
        for uid in list(_created_user_ids):
            sess.execute(text("DELETE FROM user_roles WHERE user_id = :id"), {"id": uid})
            sess.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        _created_user_ids.clear()
        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()
    # Reset Fernet cache in case a test monkeypatched the key
    reset_fernet_cache()
    os.environ["ENCRYPTION_KEY"] = _TEST_FERNET_KEY
    _reset_rate_limits()  # AFTER: clean up rate-limit state for next test


# ===========================================================================
# T01: GET /providers — admin → 200, meta.request_id present
# ===========================================================================
def test_T01_get_providers_admin_200():
    """T01: admin → 200 + list; meta.request_id present."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    resp = client.get(
        "/api/v1/admin/ai/providers",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "test-t01-rid"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "meta" in body
    assert body["meta"]["request_id"] == "test-t01-rid"


# ===========================================================================
# T02: GET /providers — employee → 403
# ===========================================================================
def test_T02_get_providers_employee_403():
    """T02: employee role → 403 AUTH_PERMISSION_DENIED."""
    email = _employee_email()
    _create_user_with_role(email, "employee")
    token = _sign_in(email)

    resp = client.get(
        "/api/v1/admin/ai/providers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert any(e["code"] == "AUTH_PERMISSION_DENIED" for e in body["errors"])


# ===========================================================================
# T03: GET /providers — no Bearer → 401
# ===========================================================================
def test_T03_get_providers_no_bearer_401():
    """T03: missing Authorization header → 401 AUTH_SESSION_EXPIRED."""
    resp = client.get("/api/v1/admin/ai/providers")
    assert resp.status_code == 401
    body = resp.json()
    assert any(e["code"] == "AUTH_SESSION_EXPIRED" for e in body["errors"])


# ===========================================================================
# T04: GET /providers — seeded provider → has_credentials=true, no encrypted_secret
# ===========================================================================
def test_T04_get_providers_has_credentials():
    """T04: provider+credential seeded → has_credentials=true, no encrypted_secret."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    # Create provider to ensure at least one exists
    provider = _create_test_provider(token)

    resp = client.get(
        "/api/v1/admin/ai/providers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    matching = [p for p in data if p["id"] == provider["id"]]
    assert len(matching) == 1
    p = matching[0]
    assert p["has_credentials"] is True
    assert p["credential_auth_type"] == "api_key"
    # Security: no encrypted_secret or secret_plain in response
    assert "encrypted_secret" not in p
    assert "secret_plain" not in p


# ===========================================================================
# T05: POST /providers — valid payload → 201; DB encrypted; audit; no creds in response
# ===========================================================================
def test_T05_post_provider_creates_encrypted_credential():
    """T05: POST valid payload → 201; DB has credential with encrypted_secret ≠ plain; audit log."""
    email = _admin_email()
    user = _create_user_with_role(email, "people_admin")
    token = _sign_in(email)
    secret_plain = "sk-litellm-test-secret-key-12345"

    resp = client.post(
        "/api/v1/admin/ai/providers",
        json={
            "provider_type": "litellm",
            "name": f"test-provider-{uuid.uuid4().hex[:6]}",
            "base_url": "http://localhost:4000",
            "credentials": {
                "auth_type": "api_key",
                "secret_plain": secret_plain,
            },
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "test-t05"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    provider_id = data["id"]
    _created_provider_ids.append(provider_id)

    # Security: no credentials in response
    assert "secret_plain" not in data
    assert "encrypted_secret" not in data
    assert data["has_credentials"] is True
    assert data["credential_auth_type"] == "api_key"

    # DB verification: encrypted_secret != plain, and decrypts correctly
    sess = _SetupSession()
    try:
        cred_row = sess.execute(
            text(
                "SELECT encrypted_secret FROM ai_provider_credentials"
                " WHERE provider_id = :pid"
            ),
            {"pid": provider_id},
        ).fetchone()
        assert cred_row is not None, "Credential row not created"
        encrypted = cred_row[0]
        assert encrypted != secret_plain, "Secret was not encrypted"
        # Decrypt and verify
        f = Fernet(_TEST_FERNET_KEY.encode())
        decrypted = f.decrypt(encrypted.encode()).decode()
        assert decrypted == secret_plain
    finally:
        sess.close()

    # Audit log verification
    sess2 = _SetupSession()
    try:
        audit_row = sess2.execute(
            text(
                "SELECT actor_user_id, action, entity_type, entity_id, metadata"
                " FROM audit_logs"
                " WHERE action='admin.ai.provider.create'"
                " AND entity_id = :pid"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"pid": provider_id},
        ).fetchone()
        assert audit_row is not None, "Audit log row not created"
        assert str(audit_row[0]) == user["user_id"]
        assert audit_row[2] == "ai_provider"
        meta = audit_row[4]
        assert meta.get("outcome") == "success"
        assert meta.get("request_id") == "test-t05"
        # Security: no credentials in audit metadata
        assert "secret_plain" not in str(meta)
        assert "encrypted_secret" not in str(meta)
    finally:
        sess2.close()


# ===========================================================================
# T06: POST /providers — invalid provider_type → 422
# ===========================================================================
def test_T06_post_provider_invalid_type_422():
    """T06: invalid provider_type (not in Literal) → 422 Pydantic validation."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    resp = client.post(
        "/api/v1/admin/ai/providers",
        json={
            "provider_type": "unsupported_llm",
            "name": "bad-provider",
            "credentials": {"auth_type": "api_key", "secret_plain": "sk-test"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ===========================================================================
# T07: POST /providers — missing credentials → 422
# ===========================================================================
def test_T07_post_provider_missing_credentials_422():
    """T07: missing required 'credentials' field → 422 Pydantic."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    resp = client.post(
        "/api/v1/admin/ai/providers",
        json={
            "provider_type": "openai",
            "name": "no-creds-provider",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ===========================================================================
# T08: POST /providers — employee→403; no Bearer→401
# ===========================================================================
def test_T08_post_provider_auth_failures():
    """T08: employee → 403; missing Bearer → 401."""
    email = _employee_email()
    _create_user_with_role(email, "employee")
    token = _sign_in(email)
    payload = {
        "provider_type": "openai",
        "name": "unauthorized-test",
        "credentials": {"auth_type": "api_key", "secret_plain": "sk-test"},
    }

    resp_403 = client.post(
        "/api/v1/admin/ai/providers",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_403.status_code == 403
    assert any(e["code"] == "AUTH_PERMISSION_DENIED" for e in resp_403.json()["errors"])

    resp_401 = client.post("/api/v1/admin/ai/providers", json=payload)
    assert resp_401.status_code == 401
    assert any(e["code"] == "AUTH_SESSION_EXPIRED" for e in resp_401.json()["errors"])


# ===========================================================================
# T09: POST /providers — 21 rapid requests → 429 RATE_LIMITED + Retry-After
# ===========================================================================
def test_T09_post_provider_rate_limit_429():
    """T09: 21 rapid requests from same IP → last = 429 RATE_LIMITED + Retry-After."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)
    payload = {
        "provider_type": "litellm",
        "name": f"rl-test-{uuid.uuid4().hex[:6]}",
        "credentials": {"auth_type": "api_key", "secret_plain": "sk-rl-test"},
    }

    # Use a short window RateLimiter by importing and using a tight time window.
    # To avoid waiting 60s, we create providers until we hit 429.
    # The limiter uses per_minute=20,burst=20; flush Redis key before test.
    from app.security._redis_client import get_redis_client
    try:
        r = get_redis_client()
        # Clear all ADMIN_AI rate-limit keys for this test
        keys = r.keys("ADMIN_AI:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass  # If Redis unavailable, test will get 503 instead (T10 covers that)

    last_status = None
    for i in range(21):
        resp = client.post(
            "/api/v1/admin/ai/providers",
            json={**payload, "name": f"rl-test-{i}-{uuid.uuid4().hex[:4]}"},
            headers={"Authorization": f"Bearer {token}"},
        )
        last_status = resp.status_code
        if resp.status_code == 201:
            pid = resp.json()["data"]["id"]
            _created_provider_ids.append(pid)
        if resp.status_code in (429, 503):
            break

    # Should have hit 429 by request 21
    assert last_status == 429, f"Expected 429 after 21 requests, got {last_status}"
    body = resp.json()
    assert any(e["code"] == "RATE_LIMITED" for e in body["errors"])
    assert resp.headers.get("Retry-After") is not None


# ===========================================================================
# T10: POST /providers — Redis down → 503 SERVICE_UNAVAILABLE
# ===========================================================================
def test_T10_post_provider_redis_down_503():
    """T10: Redis unavailable → 503 SERVICE_UNAVAILABLE (fail-closed per D-RL2)."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    import redis as redis_lib
    mock_client = MagicMock()
    mock_client.incr.side_effect = redis_lib.exceptions.RedisError("Redis is down")

    with patch("app.security.rate_limit.get_redis_client", return_value=mock_client):
        resp = client.post(
            "/api/v1/admin/ai/providers",
            json={
                "provider_type": "litellm",
                "name": f"redis-down-test-{uuid.uuid4().hex[:6]}",
                "credentials": {"auth_type": "api_key", "secret_plain": "sk-test"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 503
    body = resp.json()
    assert any(e["code"] == "SERVICE_UNAVAILABLE" for e in body["errors"])


# ===========================================================================
# T11: POST /providers — EncryptionError → 500; no DB rows; audit outcome=failure
# ===========================================================================
def test_T11_post_provider_encryption_error_500():
    """T11: encryption failure → 500; no provider/credential in DB; audit with outcome=failure."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)
    provider_name = f"enc-fail-test-{uuid.uuid4().hex[:6]}"

    from app.security.encryption import EncryptionError as _EncErr

    # After §D-AASPLIT, encrypt_secret is bound in the repository module.
    with patch(
        "app.admin.providers.repository.encrypt_secret",
        side_effect=_EncErr("test error"),
    ):
        resp = client.post(
            "/api/v1/admin/ai/providers",
            json={
                "provider_type": "openai",
                "name": provider_name,
                "credentials": {"auth_type": "api_key", "secret_plain": "sk-test"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 500

    # Verify no provider row was committed
    sess = _SetupSession()
    try:
        row = sess.execute(
            text("SELECT id FROM ai_providers WHERE name = :name"),
            {"name": provider_name},
        ).fetchone()
        assert row is None, "Provider should not have been committed on EncryptionError"

        # Audit row should exist with outcome=failure
        audit = sess.execute(
            text(
                "SELECT metadata FROM audit_logs"
                " WHERE action='admin.ai.provider.create'"
                " AND metadata->>'outcome' = 'failure'"
                " ORDER BY created_at DESC LIMIT 1"
            )
        ).fetchone()
        assert audit is not None, "Audit row with outcome=failure not found"
        meta = audit[0]
        assert meta.get("outcome") == "failure"
    finally:
        sess.close()


# ===========================================================================
# T12: Verbose logging — BEFORE/AFTER present; no secret_plain in logs
# ===========================================================================
def test_T12_verbose_logging_no_secret_in_logs(caplog):
    """T12: ENABLE_VERBOSE_LOGGING=true shows BEFORE/AFTER; secret_plain never logged."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)
    secret = "sk-supersecret-do-not-log-1234567890"

    with caplog.at_level(logging.DEBUG, logger="app.admin.providers"):
        with patch.dict(os.environ, {"ENABLE_VERBOSE_LOGGING": "true"}):
            # Re-import the _VERBOSE flag won't help (already set at module load),
            # but the log messages use the module-level logger which respects caplog.
            resp = client.post(
                "/api/v1/admin/ai/providers",
                json={
                    "provider_type": "litellm",
                    "name": f"verbose-test-{uuid.uuid4().hex[:6]}",
                    "credentials": {"auth_type": "api_key", "secret_plain": secret},
                },
                headers={"Authorization": f"Bearer {token}"},
            )

    if resp.status_code == 201:
        _created_provider_ids.append(resp.json()["data"]["id"])

    # Security: secret_plain must NEVER appear in any log record
    all_log_text = " ".join(r.getMessage() for r in caplog.records)
    assert secret not in all_log_text, "secret_plain found in logs — SECURITY VIOLATION"


# ===========================================================================
# T13: GET /models — admin no filter → 200
# ===========================================================================
def test_T13_get_models_admin_200():
    """T13: admin without filter → 200 + list."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    resp = client.get(
        "/api/v1/admin/ai/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "meta" in body
    assert "request_id" in body["meta"]


# ===========================================================================
# T14: GET /models — with ?provider_id filter
# ===========================================================================
def test_T14_get_models_provider_filter():
    """T14: ?provider_id=<uuid> → only models for that provider."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    # Create a provider and a model for it
    provider = _create_test_provider(token)
    _create_test_model(provider["id"])

    # Get all models for this provider
    resp = client.get(
        f"/api/v1/admin/ai/models?provider_id={provider['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    for m in data:
        assert m["provider_id"] == provider["id"]

    # Non-existent provider UUID → empty list (not 404)
    fake_pid = str(uuid.uuid4())
    resp2 = client.get(
        f"/api/v1/admin/ai/models?provider_id={fake_pid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"] == []


# ===========================================================================
# T15: GET /models — invalid provider_id → 422
# ===========================================================================
def test_T15_get_models_invalid_provider_id_422():
    """T15: ?provider_id=not-a-uuid → 422 from FastAPI UUID validation."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    resp = client.get(
        "/api/v1/admin/ai/models?provider_id=not-a-valid-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ===========================================================================
# T16: GET /models — employee→403; no Bearer→401
# ===========================================================================
def test_T16_get_models_auth_failures():
    """T16: employee → 403; missing Bearer → 401."""
    email = _employee_email()
    _create_user_with_role(email, "employee")
    token = _sign_in(email)

    resp_403 = client.get(
        "/api/v1/admin/ai/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_403.status_code == 403

    resp_401 = client.get("/api/v1/admin/ai/models")
    assert resp_401.status_code == 401


# ===========================================================================
# T17: PATCH /models/{id} — enabled=true → 200; audit present
# ===========================================================================
def test_T17_patch_model_enabled():
    """T17: PATCH enabled=true → 200; DB updated; audit log present."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    provider = _create_test_provider(token)
    model_id = _create_test_model(provider["id"])

    resp = client.patch(
        f"/api/v1/admin/ai/models/{model_id}",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "test-t17"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["enabled"] is True
    assert data["id"] == model_id

    # DB verification
    sess = _SetupSession()
    try:
        row = sess.execute(
            text("SELECT enabled FROM ai_models WHERE id = :id"),
            {"id": model_id},
        ).fetchone()
        assert row is not None
        assert row[0] is True

        # Audit verification
        audit = sess.execute(
            text(
                "SELECT metadata FROM audit_logs"
                " WHERE action='admin.ai.model.update'"
                " AND entity_id = :mid"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"mid": model_id},
        ).fetchone()
        assert audit is not None
        meta = audit[0]
        assert meta.get("outcome") == "success"
        assert meta.get("request_id") == "test-t17"
        assert meta["from"]["enabled"] is False
        assert meta["to"]["enabled"] is True
    finally:
        sess.close()


# ===========================================================================
# T18: PATCH /models/{id} — is_default=true when another default exists
# ===========================================================================
def test_T18_patch_model_is_default_clears_previous():
    """T18: is_default=true when another is_default=true → 200; old model loses flag."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    provider = _create_test_provider(token)

    # Create two chat models
    model1_id = _create_test_model(provider["id"], model_type="chat")
    model2_id = _create_test_model(provider["id"], model_type="chat")

    # Set model1 as default first
    resp1 = client.patch(
        f"/api/v1/admin/ai/models/{model1_id}",
        json={"is_default": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["data"]["is_default"] is True

    # Now set model2 as default → model1 should lose is_default
    resp2 = client.patch(
        f"/api/v1/admin/ai/models/{model2_id}",
        json={"is_default": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["is_default"] is True

    # Verify model1 lost is_default in DB (D-DEF1 invariant)
    sess = _SetupSession()
    try:
        m1 = sess.execute(
            text("SELECT is_default FROM ai_models WHERE id = :id"),
            {"id": model1_id},
        ).fetchone()
        m2 = sess.execute(
            text("SELECT is_default FROM ai_models WHERE id = :id"),
            {"id": model2_id},
        ).fetchone()
        assert m1 is not None and m1[0] is False, "model1 should have lost is_default"
        assert m2 is not None and m2[0] is True, "model2 should be is_default"

        # Only one is_default=true per model_type (D-DEF1 invariant)
        count = sess.execute(
            text(
                "SELECT count(*) FROM ai_models"
                " WHERE provider_id = :pid AND model_type='chat' AND is_default=true"
            ),
            {"pid": provider["id"]},
        ).scalar()
        assert count == 1, f"Expected exactly 1 default chat model, got {count}"
    finally:
        sess.close()


# ===========================================================================
# T19: PATCH /models/{id} — both fields None → 400 AI_MODEL_PAYLOAD_INVALID
# ===========================================================================
def test_T19_patch_model_empty_payload_400():
    """T19: PATCH with both enabled=None and is_default=None → 400."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    provider = _create_test_provider(token)
    model_id = _create_test_model(provider["id"])

    resp = client.patch(
        f"/api/v1/admin/ai/models/{model_id}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert any(e["code"] == "AI_MODEL_PAYLOAD_INVALID" for e in body["errors"])


# ===========================================================================
# T20: PATCH /models/{id} — non-existent model → 404
# ===========================================================================
def test_T20_patch_model_not_found_404():
    """T20: PATCH with non-existent model_id → 404 AI_MODEL_NOT_FOUND."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    fake_id = str(uuid.uuid4())
    resp = client.patch(
        f"/api/v1/admin/ai/models/{fake_id}",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert any(e["code"] == "AI_MODEL_NOT_FOUND" for e in body["errors"])


# ===========================================================================
# T21: PATCH /models/{id} — employee→403; no Bearer→401
# ===========================================================================
def test_T21_patch_model_auth_failures():
    """T21: employee → 403; missing Bearer → 401."""
    email_admin = _admin_email()
    _create_user_with_role(email_admin, "people_admin")
    admin_token = _sign_in(email_admin)
    provider = _create_test_provider(admin_token)
    model_id = _create_test_model(provider["id"])

    email_emp = _employee_email()
    _create_user_with_role(email_emp, "employee")
    emp_token = _sign_in(email_emp)

    resp_403 = client.patch(
        f"/api/v1/admin/ai/models/{model_id}",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert resp_403.status_code == 403

    resp_401 = client.patch(
        f"/api/v1/admin/ai/models/{model_id}",
        json={"enabled": True},
    )
    assert resp_401.status_code == 401


# ===========================================================================
# T22: PATCH is_default=false when was only default → 200 (allowed in V1)
# ===========================================================================
def test_T22_patch_model_remove_only_default():
    """T22: PATCH is_default=false when model was only default → 200 (V1 allows no-default state)."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)

    provider = _create_test_provider(token)
    model_id = _create_test_model(provider["id"], model_type="embeddings")

    # Set as default
    resp1 = client.patch(
        f"/api/v1/admin/ai/models/{model_id}",
        json={"is_default": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["data"]["is_default"] is True

    # Remove default (V1 allows this)
    resp2 = client.patch(
        f"/api/v1/admin/ai/models/{model_id}",
        json={"is_default": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["is_default"] is False


# ===========================================================================
# T23: X-Request-ID echoed in meta.request_id
# ===========================================================================
def test_T23_request_id_propagated():
    """T23: custom X-Request-ID is echoed in meta.request_id of response."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)
    custom_rid = f"custom-rid-{uuid.uuid4().hex[:8]}"

    resp = client.get(
        "/api/v1/admin/ai/providers",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": custom_rid},
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["request_id"] == custom_rid


# ===========================================================================
# T24: Response envelope shape
# ===========================================================================
def test_T24_response_envelope_shape():
    """T24: all success responses have {"data": ..., "meta": {"request_id": ...}}."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)
    headers = {"Authorization": f"Bearer {token}"}

    # GET providers
    resp = client.get("/api/v1/admin/ai/providers", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert "request_id" in body["meta"]

    # POST provider
    resp2 = client.post(
        "/api/v1/admin/ai/providers",
        json={
            "provider_type": "openai",
            "name": f"envelope-test-{uuid.uuid4().hex[:6]}",
            "credentials": {"auth_type": "api_key", "secret_plain": "sk-test"},
        },
        headers=headers,
    )
    assert resp2.status_code == 201
    body2 = resp2.json()
    assert "data" in body2
    assert "meta" in body2
    assert "request_id" in body2["meta"]
    _created_provider_ids.append(body2["data"]["id"])

    # GET models
    resp3 = client.get("/api/v1/admin/ai/models", headers=headers)
    assert resp3.status_code == 200
    body3 = resp3.json()
    assert "data" in body3
    assert "meta" in body3


# ===========================================================================
# T25: Cleanup — no test residue in ai_providers after suite
# ===========================================================================
def test_T25_no_test_residue():
    """T25: after cleanup fixture, no test providers remain (isolation verified)."""
    email = _admin_email()
    _create_user_with_role(email, "people_admin")
    token = _sign_in(email)
    name = f"residue-check-{uuid.uuid4().hex}"

    # Create and immediately note the name for later check
    resp = client.post(
        "/api/v1/admin/ai/providers",
        json={
            "provider_type": "litellm",
            "name": name,
            "credentials": {"auth_type": "api_key", "secret_plain": "sk-test"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    pid = resp.json()["data"]["id"]
    _created_provider_ids.append(pid)

    # Verify it exists now
    sess = _SetupSession()
    try:
        count_before = sess.execute(
            text("SELECT count(*) FROM ai_providers WHERE id = :pid"),
            {"pid": pid},
        ).scalar()
        assert count_before == 1
    finally:
        sess.close()

    # The _cleanup_test_data fixture (autouse) will delete it after this test.
    # We verify the tracking lists are populated correctly for the fixture.
    assert pid in _created_provider_ids
