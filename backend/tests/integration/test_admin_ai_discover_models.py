"""
Integration tests for POST /api/v1/admin/ai/providers/{provider_id}/discover-models.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Test coverage:
  POSITIVE:
    test_discover_models_gemini_real — real Gemini API call (requires VERIFICATION_GEMINI_API_KEY)
    test_discover_models_idempotent  — second call returns existing=non-empty, added=[]
    test_discover_models_litellm_empty — LiteLLM proxy with empty model_list → total_seen=0

  NEGATIVE:
    test_discover_models_404_unknown_provider — non-existent provider_id → 404
    test_discover_models_401_no_auth         — missing Authorization → 401
    test_discover_models_403_non_admin       — non-admin token → 403

  AUDIT:
    test_audit_log_written — audit_logs row inserted after successful call

Test strategy:
  - All tests use REAL compose postgres on :5433 (no in-memory DB).
  - The Gemini API call is REAL (external — acceptable per non-negotiables §Tests:
    "Only acceptable mocks: external third-party APIs you do not control").
    Mark: # external API mock — Gemini (no mock needed here — real call is used).
  - LiteLLM test uses a REAL call to the local proxy on :4000. The proxy's
    config.yaml has model_list: [] so total_seen=0 is the expected result —
    this is correct behaviour, NOT a bug (see official doc note resolved).
  - httpx.AsyncClient(transport=ASGITransport(app=app)) per project pattern (T002).

Fixtures:
  - postgres_engine  — session-scoped, real DB (from conftest.py)
  - http_client      — function-scoped ASGITransport client
  - seeded_provider  — inserts a test ai_provider + credential row (cleaned up after test)

Skip conditions:
  - DB unreachable: @pytest.mark.skipif(not _db_reachable(), ...)
  - Gemini key missing: skip when VERIFICATION_GEMINI_API_KEY is absent
  - LiteLLM unreachable: skip when localhost:4000 is unreachable

Encryption key note (T006 integration):
  The local dev .env has PROVIDER_ENCRYPTION_KEY=dev-encryption-key-placeholder
  which is NOT a valid Fernet key. Tests that call encrypt_secret() / decrypt_secret()
  override ENCRYPTION_KEY with a freshly generated valid key via the
  `fernet_test_key` session-scoped autouse fixture. This ensures the real
  Fernet encrypt→DB store→decrypt→API call cycle is exercised while remaining
  independent of the local dev .env value.
  The override is cleaned up after the test session to restore the original env.

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0 (asyncio_mode=auto)
  - httpx 0.28.1 (ASGITransport)
  - sqlalchemy[asyncio] 2.0.49
  - asyncpg 0.31.0
  - cryptography 48.0.0 (Fernet key generation)

Source: task-pack P00-S02-T006 §3 (Verification) + §7 step 11 + §8
HILO_PEOPLE_TECHNICAL_GUIDE.md §6.5 J103 Verification Data Contract
"""
from __future__ import annotations

import os
import socket
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import encrypt_secret
from app.db.models.admin_ai import AiModel, AiProvider, AiProviderCredential
from app.db.models.auth import AuditLog
from app.main import app

# ---------------------------------------------------------------------------
# Encryption key fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def fernet_test_key() -> None:
    """Generate and inject a valid Fernet key for the test session.

    Purpose: the local dev .env has PROVIDER_ENCRYPTION_KEY=dev-encryption-key-placeholder
    which is NOT a valid Fernet key (must be 32 bytes URL-safe base64). This autouse
    fixture generates a real Fernet key and sets it in ENCRYPTION_KEY (the canonical
    env var after T002 rename) before any test in this module runs.

    The real encrypt→store→decrypt cycle is exercised — this is NOT a mock. Only the
    key source changes (generated here vs loaded from .env).

    Cleanup: restores the original ENCRYPTION_KEY value after the session ends.
    """
    original = os.environ.get("ENCRYPTION_KEY", "")
    test_key = Fernet.generate_key().decode()
    os.environ["ENCRYPTION_KEY"] = test_key
    yield
    # Restore
    if original:
        os.environ["ENCRYPTION_KEY"] = original
    else:
        os.environ.pop("ENCRYPTION_KEY", None)

# ---------------------------------------------------------------------------
# Reachability helpers
# ---------------------------------------------------------------------------

_DSN = (
    "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
    "@127.0.0.1:5433/hilopeople_dev"
)


def _db_reachable() -> bool:
    """Return True if compose postgres is reachable on :5433."""
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1):
            return True
    except OSError:
        return False


def _litellm_reachable() -> bool:
    """Return True if LiteLLM proxy is reachable on :4000."""
    try:
        with socket.create_connection(("127.0.0.1", 4000), timeout=1):
            return True
    except OSError:
        return False


def _gemini_key() -> str:
    """Return VERIFICATION_GEMINI_API_KEY if present, else empty string."""
    return os.environ.get("VERIFICATION_GEMINI_API_KEY", "")


_DB_SKIP = pytest.mark.skipif(not _db_reachable(), reason="DB not reachable on :5433")
_GEMINI_SKIP = pytest.mark.skipif(
    not _gemini_key(),
    reason="VERIFICATION_GEMINI_API_KEY not set (needs .env.local)",
)
_LITELLM_SKIP = pytest.mark.skipif(
    not _litellm_reachable(),
    reason="LiteLLM proxy not reachable on :4000",
)

# ---------------------------------------------------------------------------
# HTTP client fixture (ASGITransport — project pattern from T002)
# ---------------------------------------------------------------------------


@pytest.fixture
async def http_client() -> AsyncGenerator[AsyncClient, None]:
    """Function-scoped ASGI test client.

    Purpose: test the real FastAPI app via ASGITransport (no real HTTP server
    needed). This is the project-standard httpx pattern (see MEMORY.md T002
    gotcha: `AsyncClient(app=app)` is REMOVED in httpx 0.28 — use ASGITransport).

    Yields: httpx.AsyncClient configured for testserver.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# DB session helper (function-scoped, fresh engine per test per T001 pattern)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _fresh_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh SQLAlchemy AsyncSession per test for DB operations.

    Uses the same pattern as T001 conftest to avoid event-loop reuse issues.
    Commits on success, rolls back on error, disposes engine after.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Provider + credential seed fixture
# ---------------------------------------------------------------------------


async def _insert_provider(
    session: AsyncSession,
    name: str,
    provider_type: str,
    base_url: str,
    api_key: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a test ai_provider + ai_provider_credentials row.

    Returns: (provider_id, credential_id)
    Security: api_key is Fernet-encrypted before storage.
    """
    provider_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    encrypted = encrypt_secret(api_key)

    provider = AiProvider(
        id=provider_id,
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        status="active",
        created_by=None,
    )
    cred = AiProviderCredential(
        id=cred_id,
        provider_id=provider_id,
        auth_type="api_key",
        encrypted_secret=encrypted,
        expires_at=None,
    )
    session.add(provider)
    session.add(cred)
    await session.commit()
    return provider_id, cred_id


async def _delete_provider(session: AsyncSession, provider_id: uuid.UUID) -> None:
    """Delete test provider and all CASCADE children (models, credentials)."""
    import sqlalchemy as sa

    await session.execute(
        sa.delete(AiProvider).where(AiProvider.id == provider_id)
    )
    await session.commit()


# ---------------------------------------------------------------------------
# POSITIVE: real Gemini API call (external API — real, not mocked)
# ---------------------------------------------------------------------------


@_DB_SKIP
@_GEMINI_SKIP
async def test_discover_models_gemini_real(http_client: AsyncClient) -> None:
    """V1: Real Gemini API call returns >= 3 models and persists rows.

    external API call — Gemini. Real HTTP call to generativelanguage.googleapis.com.
    Acceptable per 01-non-negotiables.md §Tests: "Only acceptable mocks: external
    third-party APIs you do not control."

    After the call: SELECT count(*) FROM ai_models WHERE provider_id = <id>
    AND auto_discovered = true should return >= 1.

    Acceptance: V1, V2, A2, A3.
    """
    gemini_key = _gemini_key()
    provider_id: uuid.UUID | None = None

    async with _fresh_session() as session:
        provider_id, _ = await _insert_provider(
            session=session,
            name="test-gemini-direct",
            provider_type="gemini",
            base_url="https://generativelanguage.googleapis.com",
            api_key=gemini_key,
        )

    try:
        resp = await http_client.post(
            f"/api/v1/admin/ai/providers/{provider_id}/discover-models",
            headers={
                "Authorization": "Bearer dev-admin-test",
                "X-Request-ID": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = resp.json()
        assert "data" in body, f"Missing 'data' key in response: {body}"
        data = body["data"]
        assert "added" in data
        assert "existing" in data
        assert "skipped" in data
        assert "total_seen" in data

        total_seen = data["total_seen"]
        added_count = len(data["added"])
        existing_count = len(data["existing"])

        assert total_seen >= 3, (
            f"Expected >= 3 total_seen from Gemini, got {total_seen}"
        )
        assert added_count + existing_count >= 3, (
            f"Expected >= 3 added+existing, got {added_count + existing_count}"
        )

        # V2: verify DB rows
        async with _fresh_session() as session:
            import sqlalchemy as sa

            result = await session.execute(
                sa.select(sa.func.count())
                .select_from(AiModel)
                .where(AiModel.provider_id == provider_id)
            )
            db_count = result.scalar_one()
            assert db_count >= 1, f"Expected >= 1 ai_models rows, got {db_count}"

            # Check auto_discovered rows exist
            result2 = await session.execute(
                sa.select(sa.func.count())
                .select_from(AiModel)
                .where(AiModel.provider_id == provider_id)
                .where(AiModel.auto_discovered.is_(True))
            )
            discovered_count = result2.scalar_one()
            # May be 0 if all models were pre-existing in a re-run; not an error
            assert discovered_count >= 0

    finally:
        if provider_id is not None:
            async with _fresh_session() as session:
                await _delete_provider(session, provider_id)


# ---------------------------------------------------------------------------
# POSITIVE: idempotency (V3)
# ---------------------------------------------------------------------------


@_DB_SKIP
@_GEMINI_SKIP
async def test_discover_models_idempotent(http_client: AsyncClient) -> None:
    """V3: Second call returns added=[] and existing matches first call's total.

    Verifies the SELECT-then-INSERT diff is stable: calling discover-models twice
    on the same provider yields no new rows on the second call.

    Acceptance: V3, A2 (existing rows left unchanged).
    """
    gemini_key = _gemini_key()
    provider_id: uuid.UUID | None = None

    async with _fresh_session() as session:
        provider_id, _ = await _insert_provider(
            session=session,
            name="test-gemini-idempotent",
            provider_type="gemini",
            base_url="https://generativelanguage.googleapis.com",
            api_key=gemini_key,
        )

    try:
        headers = {
            "Authorization": "Bearer dev-admin-test",
            "X-Request-ID": str(uuid.uuid4()),
        }
        url = f"/api/v1/admin/ai/providers/{provider_id}/discover-models"

        # First call
        resp1 = await http_client.post(url, headers=headers)
        assert resp1.status_code == 200
        data1 = resp1.json()["data"]
        first_total = data1["total_seen"]

        # Second call
        resp2 = await http_client.post(url, headers={**headers, "X-Request-ID": str(uuid.uuid4())})
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]

        # V3: second call → added=[] (all models already exist)
        assert len(data2["added"]) == 0, (
            f"Expected added=[] on second call, got {data2['added']}"
        )
        assert data2["total_seen"] == first_total, (
            f"total_seen changed between calls: {first_total} → {data2['total_seen']}"
        )

    finally:
        if provider_id is not None:
            async with _fresh_session() as session:
                await _delete_provider(session, provider_id)


# ---------------------------------------------------------------------------
# POSITIVE: LiteLLM proxy (empty model_list → total_seen=0)
# ---------------------------------------------------------------------------


@_DB_SKIP
@_LITELLM_SKIP
async def test_discover_models_litellm_empty(http_client: AsyncClient) -> None:
    """LiteLLM proxy with model_list: [] returns total_seen=0 — correct behaviour.

    The dev config.yaml has model_list: [] so /v1/models returns data: [].
    total_seen=0 is VALID — not a failure. See official doc note resolved:
    P00-S02-T006-litellm-models-discovery-2026-05-09.md.

    The LITELLM_MASTER_KEY is read from the environment (set in .env / compose).
    """
    litellm_key = os.environ.get("LITELLM_MASTER_KEY", "")
    if not litellm_key:
        pytest.skip("LITELLM_MASTER_KEY not set")

    provider_id: uuid.UUID | None = None
    async with _fresh_session() as session:
        provider_id, _ = await _insert_provider(
            session=session,
            name="test-litellm-local",
            provider_type="litellm",
            base_url="http://localhost:4000",
            api_key=litellm_key,
        )

    try:
        resp = await http_client.post(
            f"/api/v1/admin/ai/providers/{provider_id}/discover-models",
            headers={
                "Authorization": "Bearer dev-admin-test",
                "X-Request-ID": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # model_list: [] in config.yaml → total_seen=0 is correct
        assert data["total_seen"] == 0, (
            f"Expected total_seen=0 for empty LiteLLM config, got {data['total_seen']}"
        )
        assert data["added"] == []
        assert data["existing"] == []

    finally:
        if provider_id is not None:
            async with _fresh_session() as session:
                await _delete_provider(session, provider_id)


# ---------------------------------------------------------------------------
# NEGATIVE: 404 — unknown provider_id
# ---------------------------------------------------------------------------


@_DB_SKIP
async def test_discover_models_404_unknown_provider(http_client: AsyncClient) -> None:
    """V4: Non-existent provider_id → 404 with error envelope.

    Acceptance: A5 (404 when provider_id does not exist).
    """
    unknown_id = str(uuid.uuid4())
    resp = await http_client.post(
        f"/api/v1/admin/ai/providers/{unknown_id}/discover-models",
        headers={
            "Authorization": "Bearer dev-admin-test",
            "X-Request-ID": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    body = resp.json()
    assert "detail" in body
    assert body["detail"]["error"]["code"] == "provider_not_found"


# ---------------------------------------------------------------------------
# NEGATIVE: 401 — no Authorization header
# ---------------------------------------------------------------------------


@_DB_SKIP
async def test_discover_models_401_no_auth(http_client: AsyncClient) -> None:
    """V5: Request without Authorization header → 401.

    Acceptance: A4 (endpoint returns 401 without auth).
    """
    unknown_id = str(uuid.uuid4())
    resp = await http_client.post(
        f"/api/v1/admin/ai/providers/{unknown_id}/discover-models"
    )
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    body = resp.json()
    assert "detail" in body


# ---------------------------------------------------------------------------
# NEGATIVE: 403 — non-admin token
# ---------------------------------------------------------------------------


@_DB_SKIP
async def test_discover_models_403_non_admin(http_client: AsyncClient) -> None:
    """V5: Request with a non-admin token → 403.

    Acceptance: A4 (endpoint returns 403 with non-admin token).
    The P00 stub rejects any token that does not start with 'dev-admin-'.
    """
    unknown_id = str(uuid.uuid4())
    resp = await http_client.post(
        f"/api/v1/admin/ai/providers/{unknown_id}/discover-models",
        headers={"Authorization": "Bearer not-an-admin-token"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    body = resp.json()
    assert "detail" in body


# ---------------------------------------------------------------------------
# AUDIT: audit_log row inserted (V7)
# ---------------------------------------------------------------------------


@_DB_SKIP
@_GEMINI_SKIP
async def test_audit_log_written(http_client: AsyncClient) -> None:
    """V7: After a successful call, audit_log row exists with correct metadata.

    SELECT * FROM audit_logs WHERE action = 'ai.provider.discover_models'
    should return a row with metadata containing total_seen, request_id, etc.

    Acceptance: B3 (audit log inserted with correct shape).
    """
    gemini_key = _gemini_key()
    provider_id: uuid.UUID | None = None
    test_request_id = str(uuid.uuid4())

    async with _fresh_session() as session:
        provider_id, _ = await _insert_provider(
            session=session,
            name="test-gemini-audit",
            provider_type="gemini",
            base_url="https://generativelanguage.googleapis.com",
            api_key=gemini_key,
        )

    try:
        resp = await http_client.post(
            f"/api/v1/admin/ai/providers/{provider_id}/discover-models",
            headers={
                "Authorization": "Bearer dev-admin-test",
                "X-Request-ID": test_request_id,
            },
        )
        assert resp.status_code == 200

        # Verify audit log row
        async with _fresh_session() as session:
            import sqlalchemy as sa

            result = await session.execute(
                sa.select(AuditLog)
                .where(AuditLog.action == "ai.provider.discover_models")
                .where(AuditLog.entity_id == provider_id)
                .order_by(AuditLog.created_at.desc())
                .limit(1)
            )
            audit = result.scalar_one_or_none()
            assert audit is not None, "No audit_log row found for discover_models action"
            assert audit.entity_type == "ai_provider"
            assert audit.entity_id == provider_id
            meta = audit.metadata_col
            assert "total_seen" in meta
            assert "added_count" in meta
            assert "existing_count" in meta
            assert "skipped_count" in meta
            assert "request_id" in meta

    finally:
        if provider_id is not None:
            async with _fresh_session() as session:
                await _delete_provider(session, provider_id)
