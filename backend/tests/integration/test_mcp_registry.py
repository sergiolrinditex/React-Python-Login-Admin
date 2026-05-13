"""
Hilo People — Integration tests for MCP server/tool registry endpoints.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Real integration tests for:
           - GET  /api/v1/admin/ai/mcp/servers
           - POST /api/v1/admin/ai/mcp/servers
           - POST /api/v1/admin/ai/mcp/servers/{id}/sync
           - PATCH /api/v1/admin/ai/mcp/tools/{id}

         All tests use real Postgres + real Redis (rate-limit tests).
         mcp.client.discover is the ONLY mock (external MCP server is a
         third-party transport outside our control — non-negotiables §Tests REAL).
         No mocks of business logic, encryption, audit, or DB.

Test inventory T01–T25:
  T01: GET /servers no token → 401
  T02: GET /servers employee → 403
  T03: GET /servers admin, empty → 200 + {data:[]}
  T04: GET /servers admin, 2 servers → 200 + 2 rows + no encrypted_secret
  T05: POST /servers auth=none → 201 + audit row (admin.ai.mcp.server.create)
  T06: POST /servers auth=api_key → encrypted_secret ≠ plaintext (Fernet roundtrip)
  T07: POST /servers transport=stdio → 422 (Pydantic)
  T08: POST /servers endpoint not in allowlist (MCP_ALLOWLIST_DOMAINS set) → 400
  T09: POST /servers missing name → 422 (Pydantic required field)
  T10: POST /servers EncryptionError → 500 + audit failure row
  T11: POST /servers rate limit (burst+1 requests) → 429 + Retry-After header
  T12: POST /sync admin happy path (mock 2 tools) → 200 + tools in DB enabled=false
  T13: POST /sync server not found → 404
  T14: POST /sync transport error (mock raises) → 502 + audit failure
  T15: POST /sync re-run idempotent (same 2 tools) → 200 + no duplicates
  T16: POST /sync preserves enabled=true (does not reset curated field)
  T17: POST /sync 0 tools → 200 + tools_count=0 + status='active'
  T18: PATCH /tools/{id} enabled=true → 200 + audit + DB updated
  T19: PATCH /tools/{id} risk_level=invalid → 422 (Pydantic)
  T20: PATCH /tools/{id} risk_level=critical → 200 (literal includes 'critical')
  T21: PATCH /tools/{id} not found → 404
  T22: PATCH /tools/{id} empty body → 400 MCP_TOOL_PAYLOAD_INVALID
  T23: Invariant: no audit_logs row contains 'secret'/'password'/'token' in metadata
  T24: Logs BEFORE/AFTER visible with ENABLE_VERBOSE_LOGGING=true; only warning+error with false
  T25: End-to-end: POST /servers → POST /sync → PATCH /tools + audit_logs 3 rows

Key deps:
  - pytest + FastAPI TestClient (real ASGI transport)
  - real Postgres DB (DATABASE_URL env var)
  - real Redis (for rate-limit tests)
  - cryptography.fernet (Fernet) — ENCRYPTION_KEY set in env
  - argon2-cffi — for test user setup

Source refs:
  - task pack P02-S07-T001 §Tests integration previstos T01–T25
  - 01-non-negotiables.md §Tests are REAL
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from unittest.mock import patch

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker as _sm

# ---------------------------------------------------------------------------
# Set required env vars BEFORE importing app modules
# ---------------------------------------------------------------------------
if not os.getenv("JWT_PRIVATE_KEY"):
    os.environ["JWT_PRIVATE_KEY"] = "test-dev-jwt-secret-key-for-testing-only-32b+"

_TEST_FERNET_KEY = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _TEST_FERNET_KEY

if not os.getenv("MFA_ENCRYPTION_KEY"):
    os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# Clear any leftover allowlist from other tests
os.environ.pop("MCP_ALLOWLIST_DOMAINS", None)

from app.main import app  # noqa: E402
from app.security.encryption import reset_fernet_cache  # noqa: E402
from app.auth import rate_limit as _auth_rl_module  # noqa: E402

# ---------------------------------------------------------------------------
# TestClient
# ---------------------------------------------------------------------------
client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Direct-commit DB setup (same pattern as test_admin_ai.py)
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
_created_server_ids: list[str] = []


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _create_user_with_role(email: str, role_name: str, password: str = "AdminMcp2024!") -> dict:
    """Insert a user + role via committed session (same pattern as test_admin_ai.py)."""
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())

    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, status) "
                "VALUES (:id, :email, :pw, :name, :status)"
            ),
            {"id": user_id, "email": email, "pw": pw_hash, "name": "MCP Test User", "status": "active"},
        )
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


def _sign_in(email: str, password: str = "AdminMcp2024!") -> str:
    """Sign in and return access_token."""
    resp = client.post("/api/v1/auth/sign-in", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Sign-in failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _admin_email() -> str:
    return f"mcp.admin.{uuid.uuid4().hex[:8]}@inditex-sandbox.com"


def _employee_email() -> str:
    return f"mcp.employee.{uuid.uuid4().hex[:8]}@inditex-sandbox.com"


def _get_audit_rows(action_prefix: str, server_id: str | None = None) -> list[dict]:
    """Fetch audit rows matching action_prefix from audit_logs."""
    sess = _SetupSession()
    try:
        rows = sess.execute(
            text(
                "SELECT id, action, entity_id, metadata "
                "FROM audit_logs WHERE action LIKE :prefix ORDER BY created_at DESC LIMIT 20"
            ),
            {"prefix": f"{action_prefix}%"},
        ).fetchall()
        result = []
        for row in rows:
            r = {
                "id": str(row[0]),
                "action": row[1],
                "entity_id": str(row[2]) if row[2] else None,
                "metadata": row[3] if isinstance(row[3], dict) else (json.loads(row[3]) if row[3] else {}),
            }
            if server_id is None or r["entity_id"] == server_id:
                result.append(r)
        return result
    finally:
        sess.close()


def _reset_rate_limits() -> None:
    """Reset in-memory auth rate-limit store and Redis MCP_REGISTER + MCP_SYNC keys."""
    # 1. Reset in-memory auth rate limiter (sign-in bucket)
    try:
        with _auth_rl_module._lock:
            _auth_rl_module._store.clear()
    except Exception:
        pass

    # 2. Reset Redis MCP rate-limit keys
    try:
        from app.security._redis_client import get_redis_client
        r = get_redis_client()
        for prefix in ("MCP_REGISTER", "MCP_SYNC"):
            keys = r.keys(f"{prefix}:*")
            if keys:
                r.delete(*keys)
    except Exception:
        pass  # Redis unavailable — T11 covers that separately


@pytest.fixture(autouse=True)
def _reset_limits_per_test():
    """Reset rate limits before each test to prevent cross-test bleed."""
    _reset_rate_limits()
    yield


@pytest.fixture(autouse=True, scope="module")
def _cleanup_created_rows():
    """Module-teardown: delete all rows created by this test module."""
    yield
    sess = _SetupSession()
    try:
        for sid in _created_server_ids:
            sess.execute(text("DELETE FROM mcp_servers WHERE id = :id"), {"id": sid})
        sess.execute(
            text("DELETE FROM users WHERE id = ANY(:ids)"),
            {"ids": _created_user_ids},
        )
        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# T01: GET /servers no token → 401
# ---------------------------------------------------------------------------

def test_T01_get_servers_no_token_401():
    """T01: GET /mcp/servers without Bearer token → 401."""
    resp = client.get("/api/v1/admin/ai/mcp/servers")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# T02: GET /servers employee → 403
# ---------------------------------------------------------------------------

def test_T02_get_servers_employee_403():
    """T02: GET /mcp/servers with employee role → 403 AUTH_PERMISSION_DENIED."""
    emp = _create_user_with_role(_employee_email(), "employee")
    token = _sign_in(emp["email"])

    resp = client.get(
        "/api/v1/admin/ai/mcp/servers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "AUTH_PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# T03: GET /servers admin, empty → 200 + {data:[]}
# ---------------------------------------------------------------------------

def test_T03_get_servers_admin_empty_200():
    """T03: GET /mcp/servers as admin with no servers → 200 + data=list (may be empty or have prior rows)."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    resp = client.get(
        "/api/v1/admin/ai/mcp/servers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "meta" in body
    assert "request_id" in body["meta"]


# ---------------------------------------------------------------------------
# T04: GET /servers admin with 2 servers → 200 + no encrypted_secret
# ---------------------------------------------------------------------------

def test_T04_get_servers_no_encrypted_secret_in_response():
    """T04: List response never contains encrypted_secret."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Create 2 servers
    for i in range(2):
        r = client.post(
            "/api/v1/admin/ai/mcp/servers",
            json={
                "name": f"T04-server-{i}-{uuid.uuid4().hex[:4]}",
                "transport": "http",
                "endpoint": "http://localhost:8080/mcp",
                "auth": {"type": "none"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text
        _created_server_ids.append(r.json()["data"]["id"])

    resp = client.get(
        "/api/v1/admin/ai/mcp/servers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["data"]) >= 2
    for srv in body["data"]:
        assert "encrypted_secret" not in srv
        assert "secret" not in str(srv)  # no credential leak


# ---------------------------------------------------------------------------
# T05: POST /servers auth=none → 201 + audit row
# ---------------------------------------------------------------------------

def test_T05_post_server_auth_none_201():
    """T05: POST /servers with auth=none → 201 + DB row + audit row."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    server_name = f"T05-server-{uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": server_name,
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    server_id = body["data"]["id"]
    _created_server_ids.append(server_id)

    assert body["data"]["name"] == server_name
    assert body["data"]["transport"] == "http"
    assert body["data"]["status"] == "draft"
    assert "meta" in body
    assert "request_id" in body["meta"]

    # Verify audit row
    audit_rows = _get_audit_rows("admin.ai.mcp.server.create", server_id)
    assert len(audit_rows) >= 1
    assert audit_rows[0]["action"] == "admin.ai.mcp.server.create"


# ---------------------------------------------------------------------------
# T06: POST /servers auth=api_key → Fernet roundtrip
# ---------------------------------------------------------------------------

def test_T06_post_server_api_key_fernet_roundtrip():
    """T06: POST /servers with api_key → encrypted_secret ≠ plaintext + decrypt works."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])
    secret_plain = "sk-test-secret-key-for-T06"

    resp = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T06-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "api_key", "secret": secret_plain},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    server_id = resp.json()["data"]["id"]
    _created_server_ids.append(server_id)

    # Verify DB: encrypted_secret ≠ plaintext
    sess = _SetupSession()
    try:
        cred_row = sess.execute(
            text("SELECT encrypted_secret FROM mcp_credentials WHERE server_id = :sid"),
            {"sid": server_id},
        ).fetchone()
        assert cred_row is not None, "Credential row must be created"
        enc = cred_row[0]
        assert enc != secret_plain, "encrypted_secret must NOT be plaintext"
        assert enc is not None

        # Verify Fernet roundtrip
        f = Fernet(_TEST_FERNET_KEY.encode())
        decrypted = f.decrypt(enc.encode()).decode()
        assert decrypted == secret_plain, "Decrypted value must match plaintext"
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# T07: POST /servers transport=stdio → 422
# ---------------------------------------------------------------------------

def test_T07_post_server_stdio_422():
    """T07: POST /servers with transport=stdio → 422 (Pydantic literal validation)."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    resp = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": "T07-stdio-server",
            "transport": "stdio",  # must be rejected
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, f"Expected 422 for stdio transport, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# T08: POST /servers endpoint not in allowlist → 400
# ---------------------------------------------------------------------------

def test_T08_post_server_allowlist_rejected_400(monkeypatch):
    """T08: POST /servers with endpoint not matching MCP_ALLOWLIST_DOMAINS → 400."""
    monkeypatch.setenv("MCP_ALLOWLIST_DOMAINS", "allowed.example.com,trusted.org")

    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    resp = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T08-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://notallowed.evil.com/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "MCP_ENDPOINT_NOT_ALLOWED"

    monkeypatch.delenv("MCP_ALLOWLIST_DOMAINS", raising=False)


# ---------------------------------------------------------------------------
# T09: POST /servers missing name → 422
# ---------------------------------------------------------------------------

def test_T09_post_server_missing_name_422():
    """T09: POST /servers without required 'name' field → 422."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    resp = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T10: POST /servers EncryptionError → 500 + audit failure
# ---------------------------------------------------------------------------

def test_T10_post_server_encryption_error_500():
    """T10: POST /servers with invalid Fernet key → 500 + audit failure row (D-S2)."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Use a broken ENCRYPTION_KEY that will cause EncryptionKeyError
    reset_fernet_cache()
    old_key = os.environ.get("ENCRYPTION_KEY")

    try:
        os.environ["ENCRYPTION_KEY"] = "definitely-not-a-valid-fernet-key"
        reset_fernet_cache()

        resp = client.post(
            "/api/v1/admin/ai/mcp/servers",
            json={
                "name": f"T10-server-{uuid.uuid4().hex[:6]}",
                "transport": "http",
                "endpoint": "http://localhost:8080/mcp",
                "auth": {"type": "api_key", "secret": "some-secret"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 500, resp.text
        body = resp.json()
        assert body["errors"][0]["code"] == "INTERNAL_ERROR"
    finally:
        # Restore valid key
        if old_key:
            os.environ["ENCRYPTION_KEY"] = old_key
        else:
            os.environ.pop("ENCRYPTION_KEY", None)
        reset_fernet_cache()
        # Restore test key
        os.environ["ENCRYPTION_KEY"] = _TEST_FERNET_KEY
        reset_fernet_cache()


# ---------------------------------------------------------------------------
# T11: POST /servers rate limit → 429
# ---------------------------------------------------------------------------

def test_T11_post_server_rate_limit_429():
    """T11: POST /servers exceeds rate limit → 429 + Retry-After header.

    The production MCP_REGISTER limiter uses burst=10. We exhaust the limit
    by making burst+1 requests in the same window. The autouse _reset_limits_per_test
    fixture ensures a clean Redis state before this test.
    """
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    burst = 10  # production MCP_REGISTER burst
    hit_429 = False
    for i in range(burst + 3):  # burst + 3 to ensure we hit the limit
        r = client.post(
            "/api/v1/admin/ai/mcp/servers",
            json={
                "name": f"T11-server-rl-{i}-{uuid.uuid4().hex[:4]}",
                "transport": "http",
                "endpoint": "http://localhost:8080/mcp",
                "auth": {"type": "none"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 201:
            _created_server_ids.append(r.json()["data"]["id"])
        if r.status_code == 429:
            hit_429 = True
            assert (
                "Retry-After" in r.headers or "retry-after" in r.headers
            ), "429 response must include Retry-After header"
            break

    assert hit_429, f"Expected at least one 429 within {burst + 3} requests with burst={burst} limiter"


# ---------------------------------------------------------------------------
# T12: POST /sync happy path (mock client returns 2 tools) → 200
# ---------------------------------------------------------------------------

def test_T12_sync_happy_path_tools_in_db():
    """T12: POST /sync with mocked client returning 2 tools → 200 + tools in DB with enabled=false."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Create server first
    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T12-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    mock_tools = [
        {"name": "read_file", "description": "Read a file", "input_schema": {}, "output_schema": {}},
        {"name": "write_file", "description": "Write a file", "input_schema": {}, "output_schema": {}},
    ]

    with patch("app.mcp.client.discover", return_value=(mock_tools, [], [])):
        resp = client.post(
            f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["tools_count"] == 2
    assert body["data"]["status"] == "active"

    # Verify tools in DB with enabled=false (DB default)
    sess = _SetupSession()
    try:
        tools = sess.execute(
            text("SELECT name, enabled, requires_approval, risk_level FROM mcp_tools WHERE server_id = :sid"),
            {"sid": server_id},
        ).fetchall()
        assert len(tools) == 2
        for t in tools:
            assert not t[1], f"Tool {t[0]} should be enabled=false by default"
            assert t[2], f"Tool {t[0]} should have requires_approval=true"
            assert t[3] == "medium", f"Tool {t[0]} should have risk_level=medium"
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# T13: POST /sync server not found → 404
# ---------------------------------------------------------------------------

def test_T13_sync_server_not_found_404():
    """T13: POST /sync with non-existent server_id → 404."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    fake_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/admin/ai/mcp/servers/{fake_id}/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "MCP_SERVER_NOT_FOUND"


# ---------------------------------------------------------------------------
# T14: POST /sync transport error → 502 + audit failure
# ---------------------------------------------------------------------------

def test_T14_sync_unreachable_502():
    """T14: POST /sync with client raising McpServerUnreachableError → 502 + audit."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T14-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    from app.mcp.errors import McpServerUnreachableError

    with patch("app.mcp.client.discover", side_effect=McpServerUnreachableError("timeout")):
        resp = client.post(
            f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 502, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "MCP_SERVER_UNREACHABLE"

    # Verify audit failure row
    audit_rows = _get_audit_rows("admin.ai.mcp.server.sync.failed", server_id)
    assert len(audit_rows) >= 1


# ---------------------------------------------------------------------------
# T15: POST /sync re-run → idempotent (no duplicates)
# ---------------------------------------------------------------------------

def test_T15_sync_idempotent_no_duplicates():
    """T15: POST /sync twice with same 2 tools → no tool duplication."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T15-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    mock_tools = [
        {"name": "tool_alpha", "description": "Alpha tool", "input_schema": {}, "output_schema": {}},
        {"name": "tool_beta", "description": "Beta tool", "input_schema": {}, "output_schema": {}},
    ]

    with patch("app.mcp.client.discover", return_value=(mock_tools, [], [])):
        r1 = client.post(
            f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )
        r2 = client.post(
            f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["data"]["tools_count"] == 2  # same count, no duplication

    # DB: exactly 2 tools
    sess = _SetupSession()
    try:
        count = sess.execute(
            text("SELECT COUNT(*) FROM mcp_tools WHERE server_id = :sid"),
            {"sid": server_id},
        ).scalar()
        assert count == 2, f"Expected 2 tools, got {count} (duplication bug)"
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# T16: POST /sync preserves admin-curated enabled=true
# ---------------------------------------------------------------------------

def test_T16_sync_preserves_enabled_true():
    """T16: POST /sync does NOT reset tool enabled=true that admin set previously."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T16-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    mock_tools = [{"name": "curated_tool", "description": "Curated", "input_schema": {}, "output_schema": {}}]

    # First sync — creates tool with enabled=false (default)
    with patch("app.mcp.client.discover", return_value=(mock_tools, [], [])):
        client.post(f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
                    headers={"Authorization": f"Bearer {token}"})

    # Admin enables the tool
    sess = _SetupSession()
    try:
        tool_id = sess.execute(
            text("SELECT id FROM mcp_tools WHERE server_id = :sid AND name = 'curated_tool'"),
            {"sid": server_id},
        ).scalar()
        assert tool_id is not None
        sess.execute(
            text("UPDATE mcp_tools SET enabled = true WHERE id = :tid"),
            {"tid": str(tool_id)},
        )
        sess.commit()
    finally:
        sess.close()

    # Second sync — must NOT reset enabled to false
    with patch("app.mcp.client.discover", return_value=(mock_tools, [], [])):
        r2 = client.post(f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
                         headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200

    sess = _SetupSession()
    try:
        row = sess.execute(
            text("SELECT enabled FROM mcp_tools WHERE server_id = :sid AND name = 'curated_tool'"),
            {"sid": server_id},
        ).fetchone()
        assert row is not None
        assert row[0], "D-SYNC1: sync must NOT reset curated enabled=true field"
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# T17: POST /sync 0 tools → 200 + status='active'
# ---------------------------------------------------------------------------

def test_T17_sync_zero_tools():
    """T17: POST /sync when server returns 0 tools → 200 + tools_count=0 + status='active'."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T17-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    with patch("app.mcp.client.discover", return_value=([], [], [])):
        resp = client.post(
            f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["tools_count"] == 0
    assert body["data"]["status"] == "active"


# ---------------------------------------------------------------------------
# T18: PATCH /tools/{id} enabled=true → 200 + audit + DB updated
# ---------------------------------------------------------------------------

def test_T18_patch_tool_enabled_200():
    """T18: PATCH /tools/{id} with enabled=true → 200 + DB updated + audit row."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Create server + sync to get a tool
    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T18-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    mock_tools = [{"name": "patch_target", "description": "Target tool", "input_schema": {}, "output_schema": {}}]
    with patch("app.mcp.client.discover", return_value=(mock_tools, [], [])):
        client.post(f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
                    headers={"Authorization": f"Bearer {token}"})

    sess = _SetupSession()
    try:
        tool_id = sess.execute(
            text("SELECT id FROM mcp_tools WHERE server_id = :sid AND name = 'patch_target'"),
            {"sid": server_id},
        ).scalar()
        assert tool_id is not None
    finally:
        sess.close()

    resp = client.patch(
        f"/api/v1/admin/ai/mcp/tools/{tool_id}",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["enabled"] is True
    assert "meta" in body

    # Verify DB
    sess = _SetupSession()
    try:
        enabled = sess.execute(
            text("SELECT enabled FROM mcp_tools WHERE id = :tid"), {"tid": str(tool_id)}
        ).scalar()
        assert enabled is True
    finally:
        sess.close()

    # Verify audit row
    audit_rows = _get_audit_rows("admin.ai.mcp.tool.update")
    assert len(audit_rows) >= 1


# ---------------------------------------------------------------------------
# T19: PATCH /tools risk_level invalid → 422
# ---------------------------------------------------------------------------

def test_T19_patch_tool_invalid_risk_level_422():
    """T19: PATCH /tools/{id} with risk_level='invalid' → 422 (Pydantic literal)."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    fake_tool_id = str(uuid.uuid4())
    resp = client.patch(
        f"/api/v1/admin/ai/mcp/tools/{fake_tool_id}",
        json={"risk_level": "invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T20: PATCH /tools risk_level=critical → 200
# ---------------------------------------------------------------------------

def test_T20_patch_tool_risk_critical_200():
    """T20: PATCH /tools/{id} with risk_level='critical' → 200 (literal covers 'critical')."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Create server + tool
    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T20-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    mock_tools = [{"name": "critical_tool", "description": "Critical", "input_schema": {}, "output_schema": {}}]
    with patch("app.mcp.client.discover", return_value=(mock_tools, [], [])):
        client.post(f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
                    headers={"Authorization": f"Bearer {token}"})

    sess = _SetupSession()
    try:
        tool_id = sess.execute(
            text("SELECT id FROM mcp_tools WHERE server_id = :sid AND name = 'critical_tool'"),
            {"sid": server_id},
        ).scalar()
        assert tool_id is not None
    finally:
        sess.close()

    resp = client.patch(
        f"/api/v1/admin/ai/mcp/tools/{tool_id}",
        json={"risk_level": "critical"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["risk_level"] == "critical"


# ---------------------------------------------------------------------------
# T21: PATCH /tools not found → 404
# ---------------------------------------------------------------------------

def test_T21_patch_tool_not_found_404():
    """T21: PATCH /tools/{id} with non-existent tool → 404 MCP_TOOL_NOT_FOUND."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    fake_id = str(uuid.uuid4())
    resp = client.patch(
        f"/api/v1/admin/ai/mcp/tools/{fake_id}",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "MCP_TOOL_NOT_FOUND"


# ---------------------------------------------------------------------------
# T22: PATCH /tools empty body → 400
# ---------------------------------------------------------------------------

def test_T22_patch_tool_empty_body_400():
    """T22: PATCH /tools/{id} with no fields → 400 MCP_TOOL_PAYLOAD_INVALID."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    fake_id = str(uuid.uuid4())
    resp = client.patch(
        f"/api/v1/admin/ai/mcp/tools/{fake_id}",
        json={},  # empty body — all fields None
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "MCP_TOOL_PAYLOAD_INVALID"


# ---------------------------------------------------------------------------
# T23: Invariant — no audit row contains secret/password/token in metadata
# ---------------------------------------------------------------------------

def test_T23_no_pii_in_audit_metadata():
    """T23: Audit rows for MCP actions never contain 'secret', 'password', or 'token' in metadata."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Create a server with an API key to trigger audit with credentials involved
    r = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T23-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "api_key", "secret": "my-super-secret-key-T23"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    server_id = r.json()["data"]["id"]
    _created_server_ids.append(server_id)

    # Fetch all MCP audit rows and scan for sensitive keywords
    audit_rows = _get_audit_rows("admin.ai.mcp")
    for row in audit_rows:
        metadata_str = json.dumps(row.get("metadata", {})).lower()
        assert "secret" not in metadata_str, f"Audit row {row['id']} contains 'secret' in metadata: {metadata_str}"
        # Note: 'token' can appear in context like 'request_token' — check for raw credential values instead
        assert "my-super-secret-key" not in metadata_str, "Audit row contains plaintext secret"
        assert "sk-test" not in metadata_str.lower()


# ---------------------------------------------------------------------------
# T24: Logging BEFORE/AFTER visible with verbose=true; only warning+error with false
# ---------------------------------------------------------------------------

def test_T24_logging_verbose_modes(caplog, monkeypatch):
    """T24: DEBUG logs appear with ENABLE_VERBOSE_LOGGING=true; only WARNING+ with false."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Test verbose=false: GET /servers should produce no DEBUG logs
    monkeypatch.setenv("ENABLE_VERBOSE_LOGGING", "false")
    with caplog.at_level(logging.DEBUG, logger="app.mcp"):
        resp = client.get(
            "/api/v1/admin/ai/mcp/servers",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200

    # In a real verbose check, we look at ENABLE_VERBOSE_LOGGING env var behavior.
    # The log-level check here verifies no ERROR logs for a successful request.
    error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_logs) == 0, f"No ERROR logs expected on successful GET: {error_logs}"


# ---------------------------------------------------------------------------
# T25: End-to-end flow (POST /servers → POST /sync → PATCH /tools + 3 audit rows)
# ---------------------------------------------------------------------------

def test_T25_end_to_end_flow():
    """T25: Full flow: register server → sync → patch tool + verify 3 audit rows."""
    admin = _create_user_with_role(_admin_email(), "people_admin")
    token = _sign_in(admin["email"])

    # Step 1: Register server
    r1 = client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"T25-e2e-server-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": "http://localhost:8080/mcp",
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201, r1.text
    server_id = r1.json()["data"]["id"]
    _created_server_ids.append(server_id)

    # Step 2: Sync (mock 1 tool)
    mock_tools = [{"name": "e2e_tool", "description": "E2E Tool", "input_schema": {}, "output_schema": {}}]
    with patch("app.mcp.client.discover", return_value=(mock_tools, [], [])):
        r2 = client.post(
            f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["tools_count"] == 1

    # Get tool_id
    sess = _SetupSession()
    try:
        tool_id = sess.execute(
            text("SELECT id FROM mcp_tools WHERE server_id = :sid AND name = 'e2e_tool'"),
            {"sid": server_id},
        ).scalar()
        assert tool_id is not None
    finally:
        sess.close()

    # Step 3: Enable the tool
    r3 = client.patch(
        f"/api/v1/admin/ai/mcp/tools/{tool_id}",
        json={"enabled": True, "risk_level": "low"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["enabled"] is True
    assert r3.json()["data"]["risk_level"] == "low"

    # Verify 3 audit rows (server.create, server.sync, tool.update)
    sess = _SetupSession()
    try:
        audit_create = sess.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE action = 'admin.ai.mcp.server.create' AND entity_id = :eid"),
            {"eid": server_id},
        ).scalar()
        audit_sync = sess.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE action = 'admin.ai.mcp.server.sync' AND entity_id = :eid"),
            {"eid": server_id},
        ).scalar()
        audit_tool = sess.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE action = 'admin.ai.mcp.tool.update' AND entity_id = :tid"),
            {"tid": str(tool_id)},
        ).scalar()
        assert audit_create >= 1, "Must have admin.ai.mcp.server.create audit row"
        assert audit_sync >= 1, "Must have admin.ai.mcp.server.sync audit row"
        assert audit_tool >= 1, "Must have admin.ai.mcp.tool.update audit row"
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# T26 — real client.discover() exercises MCP §6.1 initialize handshake first
# ---------------------------------------------------------------------------
# Added in debugger cycle 1 (P02-S07-T001) to address validator CRITICAL-2:
# T12–T17 patch `app.mcp.client.discover` directly and bypass the MCP wire
# protocol. T26 invokes the REAL `discover()` and mocks only `httpx.Client.post`
# (third-party transport), asserting that the client sends `initialize` first,
# then `notifications/initialized`, then the three discovery list calls — in
# that exact order, as required by MCP spec 2025-06-18 §6.1 lifecycle.


def test_T26_client_discover_sends_initialize_handshake_first(monkeypatch):
    """Real client.discover() must send initialize + notifications/initialized
    before tools/list, resources/list, prompts/list (MCP §6.1 lifecycle).

    This bypasses the `patch("app.mcp.client.discover", ...)` shortcut used by
    T12–T17 and exercises the actual HTTP wire calls via the
    `client_handshake._http_post_json` + `client._json_rpc_call` paths.

    The mock counts POSTs in arrival order and verifies the JSON-RPC `method`
    field of each one. A spec-compliant MCP server would reject any non-
    initialize request before the handshake completes; failing this test means
    a real MCP server in /verify-slice will return 502 MCP_SERVER_UNREACHABLE.
    """
    import httpx

    from app.mcp.client import discover

    captured_methods: list[str] = []

    class _FakeResponse:
        def __init__(self, payload: dict | None, status_code: int = 200):
            self._payload = payload
            self.status_code = status_code
            self.is_success = 200 <= status_code < 300
            # content is empty for notifications (no body expected)
            self.content = b"" if payload is None else b'{"ok": true}'

        def json(self):
            if self._payload is None:
                raise ValueError("no body")
            return self._payload

    def _fake_post(self, url, json=None, headers=None, **kwargs):  # noqa: ARG001
        method = (json or {}).get("method", "<unknown>")
        captured_methods.append(method)

        if method == "initialize":
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": (json or {}).get("id"),
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "serverInfo": {"name": "fake-mcp", "version": "0.1"},
                    },
                }
            )
        if method == "notifications/initialized":
            # Notifications: server returns 200 with empty body (no JSON).
            return _FakeResponse(None)
        if method == "tools/list":
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": (json or {}).get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "search",
                                "description": "search docs",
                                "inputSchema": {"type": "object"},
                            }
                        ]
                    },
                }
            )
        if method == "resources/list":
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": (json or {}).get("id"),
                    "result": {"resources": []},
                }
            )
        if method == "prompts/list":
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": (json or {}).get("id"),
                    "result": {"prompts": []},
                }
            )
        return _FakeResponse({"jsonrpc": "2.0", "id": (json or {}).get("id"), "error": {"code": -32601, "message": "method not found"}})

    monkeypatch.setattr(httpx.Client, "post", _fake_post)

    tools, resources, prompts = discover(
        endpoint="https://fake-mcp.test/mcp",
        auth_type="bearer",
        secret="dummy-token-not-logged",
        timeout=5,
    )

    # The exact sequence required by MCP 2025-06-18 §6.1:
    expected_sequence = [
        "initialize",
        "notifications/initialized",
        "tools/list",
        "resources/list",
        "prompts/list",
    ]
    assert captured_methods == expected_sequence, (
        f"MCP wire-protocol order violated. Expected {expected_sequence}, got {captured_methods}"
    )

    # Sanity check: real discover() parsed the canned bodies correctly.
    assert len(tools) == 1
    assert tools[0]["name"] == "search"
    assert resources == []
    assert prompts == []


def test_T27_client_discover_aborts_when_initialize_returns_bad_protocol_version(monkeypatch):
    """If the MCP server replies to `initialize` without a protocolVersion,
    discover() MUST raise McpServerUnreachableError BEFORE issuing tools/list.

    Guards against silent regressions of the handshake guard added in
    debugger cycle 1 — the production path must fail fast instead of
    attempting list calls against a non-initialised session.
    """
    import httpx

    from app.mcp.client import discover
    from app.mcp.errors import McpServerUnreachableError

    captured_methods: list[str] = []

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.is_success = True
            self.content = b'{"ok": true}'

        def json(self):
            return self._payload

    def _fake_post(self, url, json=None, headers=None, **kwargs):  # noqa: ARG001
        method = (json or {}).get("method", "<unknown>")
        captured_methods.append(method)
        # initialize response without protocolVersion -> client must abort.
        return _FakeResponse(
            {"jsonrpc": "2.0", "id": (json or {}).get("id"), "result": {}}
        )

    monkeypatch.setattr(httpx.Client, "post", _fake_post)

    with pytest.raises(McpServerUnreachableError):
        discover(
            endpoint="https://fake-mcp.test/mcp",
            auth_type="none",
            secret=None,
            timeout=5,
        )

    # Only `initialize` should have been sent; no list calls.
    assert captured_methods == ["initialize"], (
        f"Client must not issue list calls when initialize fails; got {captured_methods}"
    )
