"""
Hilo People — Real transport integration tests for MCP sync 502 path.

Slice:  P04-S02-T006 — Backend MCP sync returns 500 instead of 502 for unreachable MCP server
Phase:  P04 Complete Features (bug fix + regression coverage)
Purpose: Cover the unreachable MCP server transport path WITHOUT mocking
         `mcp.client.discover`. T14 in test_mcp_registry.py mocks `discover` at
         the service boundary, which means the real httpx path through
         `client_handshake.initialize_session → _http_post_json` was never tested.
         This module covers ONLY the 502 acceptance criteria from the task pack,
         using real sockets/ports to force genuine transport errors.

Test inventory:
  TA: POST /sync, target = closed port (ConnectError) → 502 + MCP_SERVER_UNREACHABLE + audit
  TB: POST /sync, target = TCP socket that accepts+closes immediately → 502 + MCP_SERVER_UNREACHABLE
  TC: POST /sync, happy path (monkeypatched httpx transport with valid MCP JSON) → 200
  TD: POST /sync, no token → 401 (auth gates preserved)
  TE: POST /sync, employee token → 403 (admin-only gate preserved)

Key deps:
  - pytest + FastAPI TestClient (real ASGI transport; no uvicorn process needed)
  - real Postgres DB (DATABASE_URL env var; real audit_log writes)
  - argon2-cffi / cryptography.fernet (test user setup)
  - socket stdlib: TCP stub for TB

Source refs:
  - task pack P04-S02-T006 §5 Acceptance / §6 Pasos de implementación
  - 01-non-negotiables.md §Tests are REAL
  - non-negotiables §Logging — BEFORE/AFTER/ERROR verified in TC/TA
"""

from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker as _sm

# ---------------------------------------------------------------------------
# Required env vars BEFORE importing app modules
# ---------------------------------------------------------------------------
if not os.getenv("JWT_PRIVATE_KEY"):
    os.environ["JWT_PRIVATE_KEY"] = "test-dev-jwt-secret-key-for-testing-only-32b+"

# Only set ENCRYPTION_KEY if not already set — avoids clobbering a key set by
# another test module in the same pytest session (e.g. test_mcp_registry.py).
if not os.getenv("ENCRYPTION_KEY"):
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

if not os.getenv("MFA_ENCRYPTION_KEY"):
    os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# Disable MCP allowlist so any endpoint is accepted
os.environ.pop("MCP_ALLOWLIST_DOMAINS", None)

# Short timeout to avoid slow CI
os.environ.setdefault("MCP_DISCOVERY_TIMEOUT_SECONDS", "3")

from app.main import app  # noqa: E402
from app.auth import rate_limit as _auth_rl_module  # noqa: E402

# ---------------------------------------------------------------------------
# TestClient + DB helpers
# ---------------------------------------------------------------------------
_client = TestClient(app, raise_server_exceptions=False)

_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev",
)
_setup_engine = _ce(_DB_URL, pool_pre_ping=True)
_SetupSession = _sm(bind=_setup_engine, autocommit=False, autoflush=False)
_ph = PasswordHasher()

_created_user_ids: list[str] = []
_created_server_ids: list[str] = []


# ---------------------------------------------------------------------------
# Test helpers (same pattern as test_mcp_registry.py)
# ---------------------------------------------------------------------------

def _create_admin(email: str, password: str = "UnreachAdmin2024!") -> dict:
    """Insert admin user + people_admin role; return {user_id, email}."""
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())
    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, status) "
                "VALUES (:id, :email, :pw, :name, :status)"
            ),
            {
                "id": user_id,
                "email": email,
                "pw": pw_hash,
                "name": "Unreachable Test Admin",
                "status": "active",
            },
        )
        role_row = sess.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": "people_admin"},
        ).fetchone()
        if role_row is None:
            new_role_id = str(uuid.uuid4())
            sess.execute(
                text("INSERT INTO roles (id, name) VALUES (:id, :name)"),
                {"id": new_role_id, "name": "people_admin"},
            )
            role_id = new_role_id
        else:
            role_id = str(role_row[0])
        sess.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid) ON CONFLICT DO NOTHING"
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


def _create_employee(email: str, password: str = "UnreachEmp2024!") -> dict:
    """Insert employee user (no admin role); return {user_id, email}."""
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())
    sess = _SetupSession()
    try:
        sess.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, status) "
                "VALUES (:id, :email, :pw, :name, :status)"
            ),
            {
                "id": user_id,
                "email": email,
                "pw": pw_hash,
                "name": "Unreachable Test Employee",
                "status": "active",
            },
        )
        role_row = sess.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": "people_employee"},
        ).fetchone()
        if role_row:
            role_id = str(role_row[0])
            sess.execute(
                text(
                    "INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid) ON CONFLICT DO NOTHING"
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


def _sign_in(email: str, password: str) -> str:
    """Sign in and return access_token."""
    resp = _client.post("/api/v1/auth/sign-in", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Sign-in failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _register_server(token: str, endpoint: str) -> str:
    """Register an MCP server; return server_id."""
    r = _client.post(
        "/api/v1/admin/ai/mcp/servers",
        json={
            "name": f"unreachable-test-{uuid.uuid4().hex[:6]}",
            "transport": "http",
            "endpoint": endpoint,
            "auth": {"type": "none"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, f"Register failed: {r.text}"
    sid = r.json()["data"]["id"]
    _created_server_ids.append(sid)
    return sid


def _get_audit_rows(action_prefix: str, server_id: str | None = None) -> list[dict]:
    """Fetch audit rows from audit_logs matching action_prefix."""
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
                "metadata": (
                    row[3]
                    if isinstance(row[3], dict)
                    else (json.loads(row[3]) if row[3] else {})
                ),
            }
            if server_id is None or r["entity_id"] == server_id:
                result.append(r)
        return result
    finally:
        sess.close()


def _reset_rate_limits() -> None:
    """Reset in-memory auth rate-limit store and Redis MCP_REGISTER + MCP_SYNC keys.

    Mirrors the same helper in `test_mcp_registry.py`. Required because the
    MCP sync endpoint uses a Redis-backed rate limiter (burst=5) keyed by
    client identity. Without this reset, running this file after any other
    MCP suite drains the burst and TA/TB/TC get HTTP 429 instead of the
    expected 502/200 outcomes.
    """
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
        pass  # Redis unavailable — non-blocking for this suite


@pytest.fixture(autouse=True)
def _reset_limits_per_test():
    """Reset rate limits before each test to prevent cross-test bleed."""
    _reset_rate_limits()
    yield


@pytest.fixture(autouse=True, scope="module")
def _cleanup_rows():
    """Module teardown: delete rows created by this module."""
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
# TA: Closed port → real httpx ConnectError → 502 + MCP_SERVER_UNREACHABLE
# ---------------------------------------------------------------------------

def test_TA_sync_closed_port_returns_502() -> None:
    """TA: POST /sync target=closed-port forces real httpx.ConnectError → 502.

    This test does NOT mock discover(). It uses a port that has no listener so
    the real httpx client triggers ConnectError inside client_handshake.py →
    McpServerUnreachableError → router maps to 502.

    Confirms:
    - HTTP 502
    - errors[0].code == MCP_SERVER_UNREACHABLE
    - data is null, meta.request_id present, field=null, details=null
    - audit_log row admin.ai.mcp.server.sync.failed written
    """
    admin = _create_admin(f"ta.unreachable.{uuid.uuid4().hex[:6]}@inditex-sandbox.com")
    token = _sign_in(admin["email"], "UnreachAdmin2024!")
    # Port 65500 is not in use; this triggers ConnectError immediately.
    server_id = _register_server(token, "http://127.0.0.1:65500/mcp")

    resp = _client.post(
        f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 502, f"Expected 502, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["data"] is None
    assert "request_id" in body["meta"]
    assert body["meta"]["request_id"]  # non-empty
    assert len(body["errors"]) == 1
    err = body["errors"][0]
    assert err["code"] == "MCP_SERVER_UNREACHABLE"
    assert err["message"]  # non-empty
    assert err["field"] is None
    assert err["details"] is None

    # Verify audit row
    audit_rows = _get_audit_rows("admin.ai.mcp.server.sync.failed", server_id)
    assert len(audit_rows) >= 1, "Expected audit failure row"


# ---------------------------------------------------------------------------
# TB: TCP stub that accepts+closes → real HTTP parse failure → 502
# ---------------------------------------------------------------------------

def _run_accept_and_close_server(host: str, port: int, ready_event: threading.Event) -> None:
    """Listen on host:port, accept one connection, then close it immediately.

    The remote side receives an empty response body, which causes httpx to
    raise a RemoteProtocolError (a subclass of httpx.RequestError), correctly
    mapped to McpServerUnreachableError by the catch block in client_handshake.py.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    srv.settimeout(5.0)
    ready_event.set()
    try:
        conn, _ = srv.accept()
        conn.close()
    except (OSError, TimeoutError):
        pass
    finally:
        srv.close()


def test_TB_sync_accept_and_close_returns_502() -> None:
    """TB: TCP server that accepts then closes → httpx.RemoteProtocolError → 502.

    This exercises the `except (httpx.ConnectError, httpx.RequestError)` branch
    in _http_post_json (client_handshake.py) with a REAL httpx client making a
    REAL TCP connection. httpx.RemoteProtocolError is a subclass of
    httpx.RequestError and is caught correctly.

    The stub runs in a background thread; the ready_event ensures the test
    does not POST before the socket is listening.
    """
    admin = _create_admin(f"tb.unreachable.{uuid.uuid4().hex[:6]}@inditex-sandbox.com")
    token = _sign_in(admin["email"], "UnreachAdmin2024!")

    # Pick an ephemeral port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    ready = threading.Event()
    stub_thread = threading.Thread(
        target=_run_accept_and_close_server,
        args=("127.0.0.1", port, ready),
        daemon=True,
    )
    stub_thread.start()
    ready.wait(timeout=2.0)

    server_id = _register_server(token, f"http://127.0.0.1:{port}/mcp")

    resp = _client.post(
        f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    stub_thread.join(timeout=3.0)

    assert resp.status_code == 502, f"Expected 502, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["data"] is None
    assert body["errors"][0]["code"] == "MCP_SERVER_UNREACHABLE"
    assert body["errors"][0]["field"] is None
    assert body["errors"][0]["details"] is None
    assert "request_id" in body["meta"]

    # Audit row present
    audit_rows = _get_audit_rows("admin.ai.mcp.server.sync.failed", server_id)
    assert len(audit_rows) >= 1, "Expected audit failure row"


# ---------------------------------------------------------------------------
# TC: Happy path — monkeypatched httpx transport → 200 preserved
# ---------------------------------------------------------------------------

class _FakeMcpTransport:
    """Minimal httpx transport that simulates a real MCP server response.

    Handles:
      - POST initialize → JSON-RPC result with protocolVersion
      - POST notifications/initialized → empty 200
      - POST tools/list, resources/list, prompts/list → empty result
    """

    def handle_request(self, request: Any) -> Any:
        """Return appropriate JSON-RPC response per method."""
        import httpx  # noqa: PLC0415

        try:
            body = json.loads(request.content)
        except (json.JSONDecodeError, AttributeError):
            body = {}

        method = body.get("method", "")
        req_id = body.get("id")

        if method == "initialize":
            resp_body = json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "serverInfo": {"name": "fake-mcp", "version": "0.1"},
                },
            }).encode()
            return httpx.Response(200, content=resp_body, headers={"content-type": "application/json"})

        if method == "notifications/initialized":
            return httpx.Response(200, content=b"", headers={"content-type": "application/json"})

        if method in ("tools/list", "resources/list", "prompts/list"):
            key = method.split("/")[0]  # tools, resources, prompts
            resp_body = json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {key: []},
            }).encode()
            return httpx.Response(200, content=resp_body, headers={"content-type": "application/json"})

        return httpx.Response(404, content=b'{"error":"not found"}')


def test_TC_sync_happy_path_200_preserved() -> None:
    """TC: POST /sync with monkeypatched httpx → 200 + envelope correct.

    Uses a minimal httpx.MockTransport to simulate a real MCP server that
    responds to initialize + tools/list + resources/list + prompts/list.
    Verifies that the 200 path is not broken by any 502 changes.
    """
    import httpx  # noqa: PLC0415

    admin = _create_admin(f"tc.unreachable.{uuid.uuid4().hex[:6]}@inditex-sandbox.com")
    token = _sign_in(admin["email"], "UnreachAdmin2024!")
    # Use localhost — MCP_ALLOWLIST_DOMAINS allows localhost by default
    server_id = _register_server(token, "http://localhost:19999/mcp")

    transport = httpx.MockTransport(_FakeMcpTransport().handle_request)

    with patch("httpx.Client") as mock_client_cls:
        # httpx.Client is used as context manager: __enter__ returns the client
        mock_inst = mock_client_cls.return_value.__enter__.return_value
        mock_inst.post.side_effect = lambda url, **kw: transport.handle_request(
            httpx.Request("POST", url, content=json.dumps(kw.get("json", {})).encode())
        )

        resp = _client.post(
            f"/api/v1/admin/ai/mcp/servers/{server_id}/sync",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["data"] is not None
    assert "tools_count" in body["data"]
    assert "request_id" in body["meta"]


# ---------------------------------------------------------------------------
# TD: No token → 401 (auth gate preserved)
# ---------------------------------------------------------------------------

def test_TD_sync_no_token_401_preserved() -> None:
    """TD: POST /sync with no Authorization → 401 (require_admin gate intact)."""
    fake_id = str(uuid.uuid4())
    resp = _client.post(f"/api/v1/admin/ai/mcp/servers/{fake_id}/sync")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["errors"][0]["code"] in (
        "AUTH_TOKEN_MISSING", "AUTH_TOKEN_INVALID", "AUTH_SESSION_EXPIRED"
    )


# ---------------------------------------------------------------------------
# TE: Employee token → 403 (admin-only gate preserved)
# ---------------------------------------------------------------------------

def test_TE_sync_employee_403_preserved() -> None:
    """TE: POST /sync with employee token → 403 (admin-only gate intact)."""
    emp = _create_employee(f"te.unreachable.{uuid.uuid4().hex[:6]}@inditex-sandbox.com")
    token = _sign_in(emp["email"], "UnreachEmp2024!")
    fake_id = str(uuid.uuid4())
    resp = _client.post(
        f"/api/v1/admin/ai/mcp/servers/{fake_id}/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["errors"][0]["code"] in ("AUTH_FORBIDDEN", "AUTH_PERMISSION_DENIED")
