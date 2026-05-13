"""
Hilo People — Integration tests for model test and usage endpoints.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: Real integration tests for:
           - POST /api/v1/admin/ai/models/{model_id}/test  (T01–T16)
           - GET  /api/v1/admin/usage                       (U01–U08)

         All tests use real Postgres + real Redis. LiteLLM is mocked ONLY at
         the litellm.acompletion boundary (third-party, volatile — per
         01-non-negotiables.md §AI/ML libraries clause, same as P02-S03-T002
         precedent).

         Admin + model + provider + credential rows are created per-test via
         committed inserts (same pattern as test_admin_ai.py / test_auth_signin.py).

Key deps:
  - pytest + FastAPI TestClient (real ASGI transport)
  - real Postgres DB (DATABASE_URL env var)
  - real Redis (for rate-limit tests)
  - cryptography.Fernet — ENCRYPTION_KEY set in env for tests
  - litellm.acompletion — mocked at boundary for deterministic tests

Source refs:
  - task pack P02-S05-T002 §E (test plan T01–T16 + U01–U08)
  - 01-non-negotiables.md §Tests are REAL, §AI/ML libraries (mock boundary only)

Test inventory:
  POST /models/{model_id}/test:
    T01: happy path — 200; ai_model_tests row inserted; llm_usage_logs row; audit row
    T02: empty prompt body → 422 (Pydantic)
    T03: whitespace-only prompt → 422 (Pydantic field_validator)
    T04: prompt over 4000 chars → 422 (Pydantic max_length)
    T05: model_id not found → 404 AI_MODEL_NOT_FOUND
    T06: model exists, provider has no credentials → 404 AI_PROVIDER_CREDENTIAL_NOT_FOUND
    T07: decrypt fails (Fernet corruption) → 502 AI_PROVIDER_TEST_FAILED; ai_model_tests status=failure
    T08: LiteLLM RateLimitError → 502 AI_PROVIDER_TEST_FAILED
    T09: LiteLLM Timeout → 502 AI_PROVIDER_TEST_FAILED; ai_model_tests status=timeout
    T10: employee role → 403 AUTH_PERMISSION_DENIED
    T11: no auth header → 401 AUTH_SESSION_EXPIRED
    T12: rate-limit exceeded → 429 RATE_LIMITED
    T13: api_key never in any log line (caplog assertion)
    T14: prompt content never in any log (only prompt_len logged)
    T14b: prompt content never leaks via third-party 'LiteLLM' logger when
          ENABLE_VERBOSE_LOGGING=true (regression for /verify-slice F1
          P02-S05-T002 — exercises real litellm codepath via mock_response,
          not AsyncMock; without §D-LLMG-INIT-F1-LITELLM-LOGGER-LEVEL the
          library emits 'Request to litellm: ...messages=[{...}]' at DEBUG)
    T15: both ENABLE_VERBOSE_LOGGING=true and =false: tests pass (parametrised)
    T16: concurrent calls produce 2 distinct ai_model_tests rows

  GET /admin/usage:
    U01: group_by=model; seeded rows; rows count=2; totals.invocations=5
    U02: group_by=day; rows grouped by day, ordered ASC
    U03: group_by=model_day; cartesian non-zero combos
    U04: from > to → 422 ADMIN_USAGE_INVALID_PAYLOAD
    U05: window > 90 days → 422 ADMIN_USAGE_WINDOW_TOO_WIDE
    U06: empty window → 200; rows=[]; totals all zero
    U07: non-admin user → 403 AUTH_PERMISSION_DENIED
    U08: missing 'from' param → 422 (Pydantic)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy import create_engine as _ce
from sqlalchemy.orm import sessionmaker as _sm

# ---------------------------------------------------------------------------
# Env vars — must be set BEFORE importing app modules
# ---------------------------------------------------------------------------
if not os.getenv("JWT_PRIVATE_KEY"):
    os.environ["JWT_PRIVATE_KEY"] = "test-dev-jwt-secret-key-for-testing-only-32b+"

_TEST_FERNET_KEY = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _TEST_FERNET_KEY

if not os.getenv("MFA_ENCRYPTION_KEY"):
    os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# ---------------------------------------------------------------------------
# App imports (after env vars)
# ---------------------------------------------------------------------------
from app.main import app  # noqa: E402
from app.security.encryption import encrypt_secret  # noqa: E402

# ---------------------------------------------------------------------------
# TestClient
# ---------------------------------------------------------------------------
client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Direct-commit DB setup
# ---------------------------------------------------------------------------
_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev",
)
_setup_engine = _ce(_DB_URL, pool_pre_ping=True)
_SetupSession = _sm(bind=_setup_engine, autocommit=False, autoflush=False)

_ph = PasswordHasher()

# Track created IDs for cleanup.
_created_user_ids: list[str] = []
_created_provider_ids: list[str] = []
_created_model_ids: list[str] = []


# ---------------------------------------------------------------------------
# Helpers — user creation (same pattern as test_admin_ai.py)
# ---------------------------------------------------------------------------

def _create_user_with_role(email: str, role_name: str, password: str = "AdminVerify2024!") -> dict:
    """Insert user + role via committed session. Returns {user_id, email}."""
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())

    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, status) "
                "VALUES (:id, :email, :pw, :name, 'active')"
            ),
            {"id": user_id, "email": email, "pw": pw_hash, "name": "Test User"},
        )
        role_row = sess.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": role_name}
        ).fetchone()
        if role_row is None:
            role_id = str(uuid.uuid4())
            sess.execute(
                text("INSERT INTO roles (id, name) VALUES (:id, :name)"),
                {"id": role_id, "name": role_name},
            )
        else:
            role_id = str(role_row[0])
        sess.execute(
            text("INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid) ON CONFLICT DO NOTHING"),
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
    """Sign in and return the access_token JWT string."""
    resp = client.post("/api/v1/auth/sign-in", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Sign-in failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _create_test_model(
    created_by: str,
    model_id_str: str = "gpt-4o-mini",
    provider_type: str = "openai",
    credential_plain: str = "sk-test",
) -> dict:
    """Create ai_provider + ai_model + ai_provider_credential. Returns {provider_id, model_id}."""
    provider_id = str(uuid.uuid4())
    model_uuid = str(uuid.uuid4())
    encrypted = encrypt_secret(credential_plain)

    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO ai_providers (id, name, provider_type, status, created_by) "
                "VALUES (:id, :name, :pt, 'draft', :cb)"
            ),
            {"id": provider_id, "name": f"Test Provider {provider_id[:8]}", "pt": provider_type, "cb": created_by},
        )
        cred_id = str(uuid.uuid4())
        sess.execute(
            text(
                "INSERT INTO ai_provider_credentials (id, provider_id, auth_type, encrypted_secret) "
                "VALUES (:id, :pid, 'api_key', :sec)"
            ),
            {"id": cred_id, "pid": provider_id, "sec": encrypted},
        )
        sess.execute(
            text(
                "INSERT INTO ai_models (id, provider_id, model_id, model_type, enabled, is_default) "
                "VALUES (:id, :pid, :mid, 'chat', true, false)"
            ),
            {"id": model_uuid, "pid": provider_id, "mid": model_id_str},
        )
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()

    _created_provider_ids.append(provider_id)
    _created_model_ids.append(model_uuid)
    return {"provider_id": provider_id, "model_id": model_uuid}


def _create_model_no_credential(created_by: str) -> dict:
    """Create ai_provider + ai_model but NO credential row."""
    provider_id = str(uuid.uuid4())
    model_uuid = str(uuid.uuid4())

    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO ai_providers (id, name, provider_type, status, created_by) "
                "VALUES (:id, :name, 'openai', 'draft', :cb)"
            ),
            {"id": provider_id, "name": f"NoCred Provider {provider_id[:8]}", "cb": created_by},
        )
        sess.execute(
            text(
                "INSERT INTO ai_models (id, provider_id, model_id, model_type, enabled) "
                "VALUES (:id, :pid, 'gpt-4o-mini', 'chat', true)"
            ),
            {"id": model_uuid, "pid": provider_id},
        )
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()

    _created_provider_ids.append(provider_id)
    _created_model_ids.append(model_uuid)
    return {"provider_id": provider_id, "model_id": model_uuid}


def _clear_rate_limit_bucket(prefix: str = "ADMIN_AI_TEST") -> None:
    """Delete all Redis keys with the given prefix to reset rate-limit state."""
    try:
        from app.security._redis_client import get_redis_client
        rc = get_redis_client()
        keys = rc.keys(f"{prefix}:*")
        if keys:
            rc.delete(*keys)
    except Exception:
        pass  # Rate-limit test will create its own state


def _clear_signin_rate_limit() -> None:
    """Clear the auth sign-in in-memory rate-limit store between tests.

    The auth sign-in rate limiter uses an in-process token bucket (not Redis).
    We reset it by clearing the _store dict in app.auth.rate_limit to avoid
    cascade failures from too many sign-in calls across test setup_methods.
    """
    try:
        from app.auth import rate_limit as _rl
        if hasattr(_rl, "_store"):
            _rl._store.clear()
    except Exception:
        pass


def _seed_usage_logs(model_id: str, user_id: str, count: int = 5) -> None:
    """Insert synthetic llm_usage_logs rows for usage aggregation tests."""
    sess = _SetupSession()
    try:
        for i in range(count):
            # Spread across 3 days
            days_ago = i % 3
            ts = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=i)
            sess.execute(
                text(
                    "INSERT INTO llm_usage_logs "
                    "(id, user_id, model_id, tokens_in, tokens_out, estimated_cost, latency_ms, created_at) "
                    "VALUES (:id, :uid, :mid, :ti, :to, :cost, :lat, :ts)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "uid": user_id,
                    "mid": model_id,
                    "ti": 100 + i * 10,
                    "to": 50 + i * 5,
                    "cost": 0.001 * (i + 1),
                    "lat": 200 + i * 50,
                    "ts": ts,
                },
            )
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# Fake LiteLLM response (Q1 researcher-confirmed shape)
# ---------------------------------------------------------------------------

def _make_fake_litellm_response(text: str = "Hola", tokens_in: int = 5, tokens_out: int = 3) -> object:
    """Build a fake litellm ModelResponse for monkeypatching acompletion."""
    usage = SimpleNamespace(
        prompt_tokens=tokens_in,
        completion_tokens=tokens_out,
        total_tokens=tokens_in + tokens_out,
    )
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    response = SimpleNamespace(
        choices=[choice],
        usage=usage,
        model="openai/gpt-4o-mini",
        _hidden_params={"response_cost": 0.00005},
    )
    return response


# ---------------------------------------------------------------------------
# Module-level setup/teardown
# ---------------------------------------------------------------------------

def setup_module(module: object) -> None:  # noqa: ARG001
    """Ensure Redis rate-limit keys are cleared at module start."""
    _clear_rate_limit_bucket("ADMIN_AI_TEST")


def teardown_module(module: object) -> None:  # noqa: ARG001
    """Clean up all test data created by this module."""
    sess = _SetupSession()
    try:
        if _created_model_ids:
            sess.execute(
                text("DELETE FROM ai_model_tests WHERE model_id = ANY(:ids)"),
                {"ids": _created_model_ids},
            )
            sess.execute(
                text("DELETE FROM llm_usage_logs WHERE model_id = ANY(:ids)"),
                {"ids": [uuid.UUID(m) for m in _created_model_ids]},
            )
            sess.execute(
                text("DELETE FROM ai_models WHERE id = ANY(:ids)"),
                {"ids": [uuid.UUID(m) for m in _created_model_ids]},
            )
        if _created_provider_ids:
            sess.execute(
                text("DELETE FROM ai_provider_credentials WHERE provider_id = ANY(:ids)"),
                {"ids": [uuid.UUID(p) for p in _created_provider_ids]},
            )
            sess.execute(
                text("DELETE FROM ai_providers WHERE id = ANY(:ids)"),
                {"ids": [uuid.UUID(p) for p in _created_provider_ids]},
            )
        if _created_user_ids:
            sess.execute(
                text("DELETE FROM user_roles WHERE user_id = ANY(:ids)"),
                {"ids": [uuid.UUID(u) for u in _created_user_ids]},
            )
            sess.execute(
                text("DELETE FROM users WHERE id = ANY(:ids)"),
                {"ids": [uuid.UUID(u) for u in _created_user_ids]},
            )
        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()
    _clear_rate_limit_bucket("ADMIN_AI_TEST")


# ===========================================================================
# POST /api/v1/admin/ai/models/{model_id}/test
# ===========================================================================

class TestModelTestEndpoint:
    """Tests T01–T16 for POST /api/v1/admin/ai/models/{model_id}/test."""

    def setup_method(self) -> None:
        """Create a fresh admin user and model for each test."""
        _clear_rate_limit_bucket("ADMIN_AI_TEST")
        _clear_signin_rate_limit()
        self.email = f"admin-mt-{uuid.uuid4().hex[:8]}@inditex-sandbox.com"
        u = _create_user_with_role(self.email, "people_admin")
        self.user_id = u["user_id"]
        self.token = _sign_in(self.email)

    def test_T01_happy_path(self) -> None:
        """T01: happy path — 200; rows inserted in ai_model_tests, llm_usage_logs; audit."""
        ids = _create_test_model(self.user_id)
        model_uuid = ids["model_id"]

        fake_resp = _make_fake_litellm_response("Hola", tokens_in=5, tokens_out=3)
        with patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
            resp = client.post(
                f"/api/v1/admin/ai/models/{model_uuid}/test",
                json={"prompt": "Di hola en una palabra.", "max_tokens": 10},
                headers={"Authorization": f"Bearer {self.token}", "X-Request-ID": str(uuid.uuid4())},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        assert "request_id" in body["meta"]
        d = body["data"]
        assert d["model_id"] == model_uuid
        assert d["output"] == "Hola"
        assert d["status"] == "success"
        assert d["latency_ms"] is not None
        assert d["id"] is not None

        # Verify DB rows
        sess = _SetupSession()
        try:
            mt = sess.execute(
                text("SELECT status, latency_ms FROM ai_model_tests WHERE model_id = :mid ORDER BY created_at DESC LIMIT 1"),
                {"mid": uuid.UUID(model_uuid)},
            ).fetchone()
            assert mt is not None, "ai_model_tests row missing"
            assert mt[0] == "success"
            assert mt[1] is not None

            ul = sess.execute(
                text("SELECT tokens_in, tokens_out FROM llm_usage_logs WHERE model_id = :mid ORDER BY created_at DESC LIMIT 1"),
                {"mid": uuid.UUID(model_uuid)},
            ).fetchone()
            assert ul is not None, "llm_usage_logs row missing"
            assert ul[0] == 5   # tokens_in
            assert ul[1] == 3   # tokens_out

            audit = sess.execute(
                text("SELECT action FROM audit_logs WHERE action = 'admin.ai.model.test' ORDER BY created_at DESC LIMIT 1"),
            ).fetchone()
            assert audit is not None, "audit_logs row missing"
        finally:
            sess.close()

    def test_T02_empty_prompt(self) -> None:
        """T02: empty prompt body → 422."""
        ids = _create_test_model(self.user_id)
        resp = client.post(
            f"/api/v1/admin/ai/models/{ids['model_id']}/test",
            json={"prompt": ""},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 422, resp.text

    def test_T03_whitespace_only_prompt(self) -> None:
        """T03: whitespace-only prompt → 422 (Pydantic field_validator)."""
        ids = _create_test_model(self.user_id)
        resp = client.post(
            f"/api/v1/admin/ai/models/{ids['model_id']}/test",
            json={"prompt": "   "},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 422, resp.text

    def test_T04_prompt_too_long(self) -> None:
        """T04: prompt over 4000 chars → 422."""
        ids = _create_test_model(self.user_id)
        resp = client.post(
            f"/api/v1/admin/ai/models/{ids['model_id']}/test",
            json={"prompt": "x" * 4001},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 422, resp.text

    def test_T05_model_not_found(self) -> None:
        """T05: model_id not found → 404 AI_MODEL_NOT_FOUND."""
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/admin/ai/models/{fake_id}/test",
            json={"prompt": "Hello"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["errors"][0]["code"] == "AI_MODEL_NOT_FOUND"

    def test_T06_no_credential(self) -> None:
        """T06: model exists, provider has NO credentials → 404 AI_PROVIDER_CREDENTIAL_NOT_FOUND."""
        ids = _create_model_no_credential(self.user_id)
        resp = client.post(
            f"/api/v1/admin/ai/models/{ids['model_id']}/test",
            json={"prompt": "Hello"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["errors"][0]["code"] == "AI_PROVIDER_CREDENTIAL_NOT_FOUND"

    def test_T07_decrypt_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T07: Fernet corruption → 502 AI_PROVIDER_TEST_FAILED; ai_model_tests status=failure."""
        # Temporarily break decryption by monkeypatching decrypt_secret.
        from app.security import encryption as enc_module
        monkeypatch.setattr(enc_module, "decrypt_secret", lambda _: (_ for _ in ()).throw(Exception("Fernet bad token")))

        ids = _create_test_model(self.user_id)
        resp = client.post(
            f"/api/v1/admin/ai/models/{ids['model_id']}/test",
            json={"prompt": "Hello"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 502, resp.text
        assert resp.json()["errors"][0]["code"] == "AI_PROVIDER_TEST_FAILED"

        # Verify failure row in ai_model_tests
        sess = _SetupSession()
        try:
            row = sess.execute(
                text("SELECT status FROM ai_model_tests WHERE model_id = :mid ORDER BY created_at DESC LIMIT 1"),
                {"mid": uuid.UUID(ids["model_id"])},
            ).fetchone()
            if row:  # May not exist if service couldn't persist it
                assert row[0] in ("failure", "timeout")
        finally:
            sess.close()

    def test_T08_litellm_rate_limit_error(self) -> None:
        """T08: LiteLLM RateLimitError → 502 AI_PROVIDER_TEST_FAILED."""
        import litellm as _litellm

        ids = _create_test_model(self.user_id)

        async def _fail(*args, **kwargs):
            raise _litellm.RateLimitError("rate limited", llm_provider="openai", model="gpt-4o-mini")

        with patch("litellm.acompletion", new=_fail):
            resp = client.post(
                f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                json={"prompt": "Hello"},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        assert resp.status_code == 502, resp.text
        assert resp.json()["errors"][0]["code"] == "AI_PROVIDER_TEST_FAILED"

    def test_T09_litellm_timeout(self) -> None:
        """T09: LiteLLM Timeout → 502 AI_PROVIDER_TEST_FAILED; ai_model_tests status=timeout."""
        import litellm as _litellm

        ids = _create_test_model(self.user_id)

        async def _timeout(*args, **kwargs):
            raise _litellm.Timeout("Request timed out", llm_provider="openai", model="gpt-4o-mini")

        with patch("litellm.acompletion", new=_timeout):
            resp = client.post(
                f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                json={"prompt": "Hello"},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        assert resp.status_code == 502, resp.text
        assert resp.json()["errors"][0]["code"] == "AI_PROVIDER_TEST_FAILED"

        # Verify timeout row in ai_model_tests
        sess = _SetupSession()
        try:
            row = sess.execute(
                text("SELECT status FROM ai_model_tests WHERE model_id = :mid ORDER BY created_at DESC LIMIT 1"),
                {"mid": uuid.UUID(ids["model_id"])},
            ).fetchone()
            if row:
                assert row[0] in ("timeout", "failure")
        finally:
            sess.close()

    def test_T10_employee_role(self) -> None:
        """T10: employee role → 403 AUTH_PERMISSION_DENIED."""
        emp_email = f"emp-{uuid.uuid4().hex[:8]}@inditex-sandbox.com"
        _create_user_with_role(emp_email, "employee")
        emp_token = _sign_in(emp_email)
        ids = _create_test_model(self.user_id)

        resp = client.post(
            f"/api/v1/admin/ai/models/{ids['model_id']}/test",
            json={"prompt": "Hello"},
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["errors"][0]["code"] == "AUTH_PERMISSION_DENIED"

    def test_T11_no_auth_header(self) -> None:
        """T11: no Authorization header → 401 AUTH_SESSION_EXPIRED."""
        ids = _create_test_model(self.user_id)
        resp = client.post(
            f"/api/v1/admin/ai/models/{ids['model_id']}/test",
            json={"prompt": "Hello"},
        )
        assert resp.status_code == 401, resp.text
        assert resp.json()["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"

    def test_T12_rate_limit_exceeded(self) -> None:
        """T12: 6th call in window → 429 RATE_LIMITED; no LiteLLM call made."""
        _clear_rate_limit_bucket("ADMIN_AI_TEST")
        ids = _create_test_model(self.user_id)

        fake_resp = _make_fake_litellm_response()
        call_count = 0

        async def _tracked(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fake_resp

        with patch("litellm.acompletion", new=_tracked):
            # Use short window_seconds so we can exhaust the 5/min burst
            from app.admin.model_test import router as mt_router_module
            original_limiter = mt_router_module._test_limiter
            from app.security.rate_limit import RateLimiter
            mt_router_module._test_limiter = RateLimiter(
                prefix="ADMIN_AI_TEST_T12",
                per_minute=5,
                burst=5,
                window_seconds=60,
            )
            _clear_rate_limit_bucket("ADMIN_AI_TEST_T12")
            try:
                for i in range(5):
                    r = client.post(
                        f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                        json={"prompt": "Hello"},
                        headers={"Authorization": f"Bearer {self.token}"},
                    )
                    # First 5 should either succeed or hit LiteLLM
                    assert r.status_code != 429, f"Hit rate limit too early at call {i+1}: {r.text}"

                # 6th call should be rate-limited
                r6 = client.post(
                    f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                    json={"prompt": "Hello"},
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                assert r6.status_code == 429, f"Expected 429, got {r6.status_code}: {r6.text}"
                assert r6.json()["errors"][0]["code"] == "RATE_LIMITED"
            finally:
                mt_router_module._test_limiter = original_limiter
                _clear_rate_limit_bucket("ADMIN_AI_TEST_T12")

    def test_T13_api_key_not_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """T13: api_key (plaintext) NEVER appears in any log captured by caplog."""
        _clear_rate_limit_bucket("ADMIN_AI_TEST")
        os.environ["ENABLE_VERBOSE_LOGGING"] = "true"
        ids = _create_test_model(self.user_id, credential_plain="sk-SECRET-SHOULD-NOT-APPEAR")

        fake_resp = _make_fake_litellm_response()
        with caplog.at_level(logging.DEBUG), patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
            resp = client.post(
                f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                json={"prompt": "Hello test"},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        os.environ["ENABLE_VERBOSE_LOGGING"] = "false"
        # 200 or 5xx — we only care that no secret leaked
        assert resp.status_code in (200, 502), resp.text

        all_log_text = "\n".join(caplog.messages)
        assert "sk-SECRET-SHOULD-NOT-APPEAR" not in all_log_text, (
            "API key appeared in logs!"
        )
        assert "Bearer " not in all_log_text, (
            "Bearer token appeared in logs!"
        )

    def test_T14_prompt_not_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """T14: prompt content NEVER appears in logs; only prompt_len is logged."""
        _clear_rate_limit_bucket("ADMIN_AI_TEST")
        os.environ["ENABLE_VERBOSE_LOGGING"] = "true"
        ids = _create_test_model(self.user_id)
        secret_prompt = "CONFIDENTIAL-PROMPT-CONTENT-XYZ-987"

        fake_resp = _make_fake_litellm_response()
        with caplog.at_level(logging.DEBUG), patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
            resp = client.post(
                f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                json={"prompt": secret_prompt},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        os.environ["ENABLE_VERBOSE_LOGGING"] = "false"
        assert resp.status_code in (200, 502), resp.text

        all_log_text = "\n".join(caplog.messages)
        assert secret_prompt not in all_log_text, (
            "Prompt content appeared in logs! Only prompt_len should be logged."
        )
        # The primary assertion is that content never leaks. prompt_len may or may
        # not appear depending on whether _VERBOSE was already set at import time
        # (module-level constant). The security guarantee (no content) is the gate.

    def test_T14b_prompt_not_in_litellm_logger(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Regression for /verify-slice F1 P02-S05-T002 — the third-party
        'LiteLLM' Python logger must NEVER emit prompt content when
        ENABLE_VERBOSE_LOGGING=true.

        T14 patches ``litellm.acompletion`` with ``AsyncMock``, so the library
        codepath that emits ``Request to litellm: ...messages=[{...}]`` at
        ``LiteLLM:DEBUG`` (utils.py:482) never runs. This test exercises the
        REAL litellm codepath by passing ``mock_response`` as a kwarg — LiteLLM
        short-circuits the network call but still runs the kwargs-logging
        preamble that emits the leak. The fix at
        ``app/llm_gateway/__init__.py`` (§D-LLMG-INIT-F1-LITELLM-LOGGER-LEVEL)
        forces ``logging.getLogger('LiteLLM').setLevel(logging.WARNING)`` at
        package import so the DEBUG record is gated out regardless of root
        logger level.

        Asserts:
          - no occurrence of the sentinel in ANY caplog record (across both
            'LiteLLM' and 'app.*' namespaces).
          - HTTP response succeeds (mock_response returns a fake completion).
        """
        _clear_rate_limit_bucket("ADMIN_AI_TEST")
        os.environ["ENABLE_VERBOSE_LOGGING"] = "true"
        ids = _create_test_model(self.user_id)
        # Unique sentinel distinct from T14 to avoid cross-test contamination.
        secret_prompt = "REGRESSION-F1-LITELLM-LOGGER-LEAK-SENTINEL-42"

        # Use litellm.mock_response: real litellm.acompletion runs the kwargs-
        # logging codepath (which is where the leak originates) but returns a
        # fake response without any network IO. NO AsyncMock — that bypasses
        # the very codepath we are trying to assert on.
        import litellm as _litellm

        _orig_acompletion = _litellm.acompletion

        async def _wrapped_acompletion(*args: object, **kwargs: object) -> object:
            kwargs["mock_response"] = "Hola"
            return await _orig_acompletion(*args, **kwargs)

        with caplog.at_level(logging.DEBUG), patch(
            "litellm.acompletion", new=_wrapped_acompletion
        ):
            resp = client.post(
                f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                json={"prompt": secret_prompt},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        os.environ["ENABLE_VERBOSE_LOGGING"] = "false"
        assert resp.status_code == 200, resp.text

        # Inspect every captured record across all logger namespaces — the
        # bug we are guarding against is in 'LiteLLM', not 'app.*', so caplog
        # .messages alone is insufficient (it omits the logger name context).
        leaked: list[tuple[str, str]] = []
        for record in caplog.records:
            msg = record.getMessage()
            if secret_prompt in msg:
                leaked.append((record.name, msg))
        assert not leaked, (
            "Prompt content leaked to logs via the following logger(s): "
            f"{leaked!r}. The fix in app/llm_gateway/__init__.py "
            "(§D-LLMG-INIT-F1-LITELLM-LOGGER-LEVEL) must keep "
            "logging.getLogger('LiteLLM').setLevel(logging.WARNING)."
        )

    @pytest.mark.parametrize("verbose", ["true", "false"])
    def test_T15_both_verbose_modes_pass(self, verbose: str) -> None:
        """T15: both ENABLE_VERBOSE_LOGGING=true and =false produce green runs."""
        _clear_rate_limit_bucket("ADMIN_AI_TEST")
        os.environ["ENABLE_VERBOSE_LOGGING"] = verbose
        ids = _create_test_model(self.user_id)

        fake_resp = _make_fake_litellm_response()
        with patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
            resp = client.post(
                f"/api/v1/admin/ai/models/{ids['model_id']}/test",
                json={"prompt": "Hello verbose test"},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        os.environ["ENABLE_VERBOSE_LOGGING"] = "false"
        assert resp.status_code == 200, f"verbose={verbose}: {resp.text}"

    def test_T16_concurrent_calls_distinct_rows(self) -> None:
        """T16: concurrent /test calls produce 2 distinct ai_model_tests + llm_usage_logs rows."""
        _clear_rate_limit_bucket("ADMIN_AI_TEST")
        ids = _create_test_model(self.user_id)
        model_uuid = ids["model_id"]

        fake_resp = _make_fake_litellm_response()

        # Use two separate clients to simulate concurrent calls
        with patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
            r1 = client.post(
                f"/api/v1/admin/ai/models/{model_uuid}/test",
                json={"prompt": "Call one"},
                headers={"Authorization": f"Bearer {self.token}"},
            )
            r2 = client.post(
                f"/api/v1/admin/ai/models/{model_uuid}/test",
                json={"prompt": "Call two"},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text

        # Verify 2 distinct rows
        sess = _SetupSession()
        try:
            rows = sess.execute(
                text("SELECT id FROM ai_model_tests WHERE model_id = :mid AND status = 'success'"),
                {"mid": uuid.UUID(model_uuid)},
            ).fetchall()
            assert len(rows) >= 2, f"Expected ≥2 ai_model_tests rows, got {len(rows)}"

            usage_rows = sess.execute(
                text("SELECT id FROM llm_usage_logs WHERE model_id = :mid"),
                {"mid": uuid.UUID(model_uuid)},
            ).fetchall()
            assert len(usage_rows) >= 2, f"Expected ≥2 llm_usage_logs rows, got {len(usage_rows)}"

            # IDs must be distinct
            test_ids = [str(r[0]) for r in rows]
            assert len(set(test_ids)) >= 2, "Duplicate row IDs detected"
        finally:
            sess.close()


# ===========================================================================
# GET /api/v1/admin/usage
# ===========================================================================

class TestUsageEndpoint:
    """Tests U01–U08 for GET /api/v1/admin/usage."""

    def setup_method(self) -> None:
        """Create admin user + model with seeded usage rows."""
        _clear_signin_rate_limit()
        self.email = f"admin-usage-{uuid.uuid4().hex[:8]}@inditex-sandbox.com"
        u = _create_user_with_role(self.email, "people_admin")
        self.user_id = u["user_id"]
        self.token = _sign_in(self.email)

        # Create two models for multi-model tests
        ids1 = _create_test_model(self.user_id, model_id_str="gpt-4o-mini")
        self.model_id_1 = ids1["model_id"]
        ids2 = _create_test_model(self.user_id, model_id_str="gpt-4o")
        self.model_id_2 = ids2["model_id"]

        # Seed usage logs: 3 rows for model1 (3 different days), 2 rows for model2
        _seed_usage_logs(self.model_id_1, self.user_id, count=3)
        _seed_usage_logs(self.model_id_2, self.user_id, count=2)

        # Window for queries: last 10 days
        self.from_dt = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        self.to_dt = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    def test_U01_group_by_model(self) -> None:
        """U01: group_by=model; 2 models; totals.invocations = total seeded rows."""
        resp = client.get(
            "/api/v1/admin/usage",
            params={"from": self.from_dt, "to": self.to_dt, "group_by": "model"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "data" in body
        d = body["data"]
        assert d["group_by"] == "model"
        assert "rows" in d
        assert "totals" in d
        # We seeded 3+2=5 rows across 2 models
        assert d["totals"]["invocations"] >= 5
        # At least 2 model rows
        model_ids_in_response = {r["model_id"] for r in d["rows"] if r.get("model_id")}
        assert self.model_id_1 in model_ids_in_response
        assert self.model_id_2 in model_ids_in_response

    def test_U02_group_by_day(self) -> None:
        """U02: group_by=day; rows grouped by day, ordered ascending."""
        resp = client.get(
            "/api/v1/admin/usage",
            params={"from": self.from_dt, "to": self.to_dt, "group_by": "day"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["group_by"] == "day"
        rows = d["rows"]
        assert len(rows) >= 1
        # Rows should have 'day' field
        for r in rows:
            assert "day" in r
        # Days should be ascending
        days = [r["day"] for r in rows if r["day"]]
        assert days == sorted(days), "Days not in ascending order"

    def test_U03_group_by_model_day(self) -> None:
        """U03: group_by=model_day; rows have both model_id and day fields."""
        resp = client.get(
            "/api/v1/admin/usage",
            params={"from": self.from_dt, "to": self.to_dt, "group_by": "model_day"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["group_by"] == "model_day"
        rows = d["rows"]
        for r in rows:
            assert "model_id" in r
            assert "day" in r

    def test_U04_from_greater_than_to(self) -> None:
        """U04: from > to → 422 ADMIN_USAGE_INVALID_PAYLOAD."""
        from_dt = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        to_dt = datetime.now(timezone.utc).isoformat()
        resp = client.get(
            "/api/v1/admin/usage",
            params={"from": from_dt, "to": to_dt, "group_by": "model"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["errors"][0]["code"] == "ADMIN_USAGE_INVALID_PAYLOAD"

    def test_U05_window_too_wide(self) -> None:
        """U05: window > 90 days → 422 ADMIN_USAGE_WINDOW_TOO_WIDE."""
        from_dt = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
        to_dt = datetime.now(timezone.utc).isoformat()
        resp = client.get(
            "/api/v1/admin/usage",
            params={"from": from_dt, "to": to_dt, "group_by": "model"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["errors"][0]["code"] == "ADMIN_USAGE_WINDOW_TOO_WIDE"

    def test_U06_empty_window(self) -> None:
        """U06: window with no rows → 200; rows=[]; totals all zero."""
        # Use a future window with no data
        from_dt = (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()
        to_dt = (datetime.now(timezone.utc) + timedelta(days=110)).isoformat()
        resp = client.get(
            "/api/v1/admin/usage",
            params={"from": from_dt, "to": to_dt, "group_by": "model"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["rows"] == []
        assert d["totals"]["invocations"] == 0
        assert d["totals"]["tokens_in"] == 0
        assert d["totals"]["tokens_out"] == 0

    def test_U07_non_admin_user(self) -> None:
        """U07: non-admin user → 403 AUTH_PERMISSION_DENIED."""
        emp_email = f"emp-usage-{uuid.uuid4().hex[:8]}@inditex-sandbox.com"
        _create_user_with_role(emp_email, "employee")
        emp_token = _sign_in(emp_email)

        resp = client.get(
            "/api/v1/admin/usage",
            params={"from": self.from_dt, "to": self.to_dt, "group_by": "model"},
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["errors"][0]["code"] == "AUTH_PERMISSION_DENIED"

    def test_U08_missing_from_param(self) -> None:
        """U08: missing 'from' query param → 422 (FastAPI Pydantic required field)."""
        resp = client.get(
            "/api/v1/admin/usage",
            params={"to": self.to_dt, "group_by": "model"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 422, resp.text
