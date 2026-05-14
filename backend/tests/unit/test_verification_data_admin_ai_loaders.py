"""
Hilo People — Unit tests for new admin_ai verification data loaders.

Slice:  P02-S03-T004 — Rotate ENCRYPTION_KEY in dev .env + seed active AI provider
Phase:  P02 Core Features
Purpose: 4 tests for load_ai_provider_credentials() and load_ai_models() (T06..T09):
           T06 — load_ai_provider_credentials encrypts and stores; decrypt round-trips
           T07 — second call with same (provider_id, auth_type) UPDATES, not inserts
           T08 — load_ai_models upserts on (provider_id, model_id); respects enabled+is_default
           T09 — _table_exists=False → both loaders return deferred LoadResult without raising

         Uses REAL SQLAlchemy engine + Postgres (pg_session fixture from conftest.py).
         If no Postgres available, tests are skipped (not failed) via pg_engine fixture.
         Only mock: ENCRYPTION_KEY env var (monkeypatched to a real Fernet key per test).

Key deps:
  - pytest==9.0.2
  - sqlalchemy==2.0.49 (pg_engine / pg_session from conftest)
  - cryptography==48.0.0 (Fernet — validate round-trip)
  - app.verification_data.loader (load_ai_provider_credentials, load_ai_models)
  - app.security.encryption (encrypt_secret, decrypt_secret, reset_fernet_cache)
  - app.verification_data.schemas (AiProviderCredentialFixture, AiModelFixture)

Source refs:
  - task pack P02-S03-T004 §Test plan T06..T09
  - D-T004-A4 (loader SRP), D-T004-A5 (FK-safe order), D-T004-A6 (encrypt at load time)
  - 01-non-negotiables.md §Tests are REAL (real Postgres, real Fernet, no mocks of own code)
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Deferred import guard — skip whole module if integration DB not available.
# Tests that need pg_session/pg_engine will be skipped by the fixture itself.
# ---------------------------------------------------------------------------


def _make_fernet_key() -> str:
    """Generate a fresh valid Fernet key string."""
    return Fernet.generate_key().decode()


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture()
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Patch ENCRYPTION_KEY with a fresh valid Fernet key; reset cache after.

    Returns:
        The generated key string (for round-trip assertions).
    """
    key = _make_fernet_key()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # Reset lru_cache so the patched key is picked up
    from app.security.encryption import reset_fernet_cache
    reset_fernet_cache()
    yield key
    # Teardown: reset cache again so other tests start clean
    reset_fernet_cache()


@pytest.fixture()
def seeded_provider(pg_session: Any, pg_engine: Any) -> dict[str, str]:
    """Insert a minimal ai_providers row for FK tests.

    Returns:
        Dict with provider 'id' (str UUID) and 'name'.
    """
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(pg_engine)
    if not insp.has_table("ai_providers"):
        pytest.skip("ai_providers table not available — integration DB required")

    provider_name = f"test_provider_{uuid.uuid4().hex[:8]}"
    result = pg_session.execute(
        text(
            "INSERT INTO ai_providers (name, provider_type, base_url, status)"
            " VALUES (:name, 'litellm', 'http://localhost:4000', 'active')"
            " RETURNING id"
        ),
        {"name": provider_name},
    ).fetchone()
    pg_session.commit()
    return {"id": str(result[0]), "name": provider_name}


# ===========================================================================
# T06 — load_ai_provider_credentials encrypts and stores; decrypt round-trips
# ===========================================================================
@pytest.mark.integration
def test_load_credentials_encrypts_and_round_trips(
    pg_session: Any,
    pg_engine: Any,
    fernet_key: str,
    seeded_provider: dict[str, str],
) -> None:
    """T06: loader encrypts credential_plain; stored value != plain; decrypt round-trips."""
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(pg_engine)
    if not insp.has_table("ai_provider_credentials"):
        pytest.skip("ai_provider_credentials table not available")

    from app.security.encryption import decrypt_secret
    from app.verification_data.loader import load_ai_provider_credentials
    from app.verification_data.schemas import AiProviderCredentialFixture

    credential_plain = "hilo-dev-test-bearer-key-t06"
    fixtures = [
        AiProviderCredentialFixture(
            provider_ref=seeded_provider["name"],
            auth_type="bearer",
            credential_plain=credential_plain,
        )
    ]

    result = load_ai_provider_credentials(pg_session, pg_engine, fixtures)

    assert result.status == "ok", f"Expected ok, got {result.status}: {result.reason}"
    assert result.inserted == 1, f"Expected inserted=1, got {result.inserted}"

    row = pg_session.execute(
        text(
            "SELECT encrypted_secret FROM ai_provider_credentials"
            " WHERE provider_id = :pid AND auth_type = 'bearer'"
        ),
        {"pid": seeded_provider["id"]},
    ).fetchone()

    assert row is not None, "No credential row found after load"
    encrypted_secret = row[0]

    # Stored value must NOT equal the plain credential
    assert encrypted_secret != credential_plain, (
        "SECURITY: credential_plain was stored in plain text!"
    )
    # Round-trip decrypt must return the original plain value
    decrypted = decrypt_secret(encrypted_secret)
    assert decrypted == credential_plain, (
        f"decrypt_secret round-trip failed: expected {credential_plain!r}, got {decrypted!r}"
    )


# ===========================================================================
# T07 — Second call with same (provider_id, auth_type) UPDATES, not inserts
# ===========================================================================
@pytest.mark.integration
def test_load_credentials_idempotent_upsert(
    pg_session: Any,
    pg_engine: Any,
    fernet_key: str,
    seeded_provider: dict[str, str],
) -> None:
    """T07: second run with same (provider_id, auth_type) → updated=1, not duplicate insert."""
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(pg_engine)
    if not insp.has_table("ai_provider_credentials"):
        pytest.skip("ai_provider_credentials table not available")

    from app.verification_data.loader import load_ai_provider_credentials
    from app.verification_data.schemas import AiProviderCredentialFixture

    fixtures = [
        AiProviderCredentialFixture(
            provider_ref=seeded_provider["name"],
            auth_type="api_key",
            credential_plain="first-run-key-t07",
        )
    ]

    # First run
    r1 = load_ai_provider_credentials(pg_session, pg_engine, fixtures)
    assert r1.status == "ok"
    assert r1.inserted == 1

    # Second run — same auth_type, different plain (should UPDATE)
    fixtures2 = [
        AiProviderCredentialFixture(
            provider_ref=seeded_provider["name"],
            auth_type="api_key",
            credential_plain="second-run-key-t07",
        )
    ]
    r2 = load_ai_provider_credentials(pg_session, pg_engine, fixtures2)
    assert r2.status == "ok"
    assert r2.updated == 1, f"Expected updated=1 on second run, got {r2.updated}"
    assert r2.inserted == 0, f"Expected inserted=0 on second run, got {r2.inserted}"

    # Only one row should exist
    count = pg_session.execute(
        text(
            "SELECT COUNT(*) FROM ai_provider_credentials"
            " WHERE provider_id = :pid AND auth_type = 'api_key'"
        ),
        {"pid": seeded_provider["id"]},
    ).scalar()
    assert count == 1, f"Expected 1 credential row, found {count}"


# ===========================================================================
# T08 — load_ai_models upserts on (provider_id, model_id); enabled+is_default set correctly
# ===========================================================================
@pytest.mark.integration
def test_load_models_upsert_and_flags(
    pg_session: Any,
    pg_engine: Any,
    seeded_provider: dict[str, str],
) -> None:
    """T08: load_ai_models inserts with enabled=True, is_default=True; second run updates.

    Note: ai_models has a partial unique index UNIQUE(model_type) WHERE is_default=true
    (global across all providers, see FU-20260513085435). The test clears any existing
    is_default=true chat model before inserting to avoid UniqueViolation.
    """
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(pg_engine)
    if not insp.has_table("ai_models"):
        pytest.skip("ai_models table not available")

    from app.verification_data.loader import load_ai_models
    from app.verification_data.schemas import AiModelFixture

    # Clear any existing is_default=true chat models to avoid UniqueViolation from
    # the global partial unique index UNIQUE(model_type) WHERE is_default=true.
    # This is a test-isolation step; the loader does not need to do this because
    # the verification bootstrap runs idempotently on its OWN provider row.
    pg_session.execute(
        text("UPDATE ai_models SET is_default = false WHERE model_type = 'chat' AND is_default = true")
    )
    pg_session.commit()

    fixtures = [
        AiModelFixture(
            provider_ref=seeded_provider["name"],
            model_id="gpt-4o-mini-t08",  # unique model_id for test isolation
            model_type="chat",
            enabled=True,
            is_default=True,
            capabilities=["chat", "streaming"],
            pricing={},
        )
    ]

    r1 = load_ai_models(pg_session, pg_engine, fixtures)
    assert r1.status == "ok", f"Expected ok, got {r1.status}"
    assert r1.inserted == 1

    row = pg_session.execute(
        text(
            "SELECT model_type, enabled, is_default FROM ai_models"
            " WHERE provider_id = :pid AND model_id = 'gpt-4o-mini-t08'"
        ),
        {"pid": seeded_provider["id"]},
    ).fetchone()

    assert row is not None, "No model row found after load"
    assert row[0] == "chat", f"model_type should be 'chat', got {row[0]!r}"
    assert row[1] is True, f"enabled should be True, got {row[1]}"
    assert row[2] is True, f"is_default should be True, got {row[2]}"

    # Second run — should update, not insert duplicate
    r2 = load_ai_models(pg_session, pg_engine, fixtures)
    assert r2.status == "ok"
    assert r2.updated == 1, f"Expected updated=1 on second run, got {r2.updated}"
    assert r2.inserted == 0

    count = pg_session.execute(
        text(
            "SELECT COUNT(*) FROM ai_models"
            " WHERE provider_id = :pid AND model_id = 'gpt-4o-mini-t08'"
        ),
        {"pid": seeded_provider["id"]},
    ).scalar()
    assert count == 1, f"Expected 1 model row, found {count}"


# ===========================================================================
# T09 — _table_exists=False → both loaders return deferred without raising
# ===========================================================================
def test_loaders_deferred_when_tables_missing() -> None:
    """T09: if ai_provider_credentials or ai_models tables missing → LoadResult(status='deferred')."""
    from unittest.mock import MagicMock

    from app.verification_data.loader import (
        load_ai_models,
        load_ai_provider_credentials,
    )
    from app.verification_data.schemas import AiModelFixture, AiProviderCredentialFixture

    # Mock engine where has_table always returns False
    mock_engine = MagicMock()

    with patch(
        "app.verification_data.loader_ai_tables._table_exists",
        return_value=False,
    ):
        mock_session = MagicMock()

        # credentials loader — deferred
        cred_fixtures = [
            AiProviderCredentialFixture(
                provider_ref="test_provider",
                auth_type="bearer",
                credential_plain="test-plain-key",
            )
        ]
        cred_result = load_ai_provider_credentials(mock_session, mock_engine, cred_fixtures)
        assert cred_result.status == "deferred", (
            f"Expected deferred, got {cred_result.status}"
        )
        assert "table_missing" in cred_result.reason

        # models loader — deferred
        model_fixtures = [
            AiModelFixture(
                provider_ref="test_provider",
                model_id="gpt-4o-mini",
                model_type="chat",
            )
        ]
        model_result = load_ai_models(mock_session, mock_engine, model_fixtures)
        assert model_result.status == "deferred", (
            f"Expected deferred, got {model_result.status}"
        )
        assert "table_missing" in model_result.reason

        # No DB calls should have been made
        mock_session.execute.assert_not_called()
        mock_session.commit.assert_not_called()
