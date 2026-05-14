"""
Hilo People — Verification data loaders for AI credential and model tables.

Slice:  P02-S03-T004 — Rotate ENCRYPTION_KEY in dev .env + seed active AI provider
Phase:  P02 Core Features
Purpose: Contains load_ai_provider_credentials() and load_ai_models() — two loaders
         for FK-dependent tables under ai_providers. Split into its own file per
         01-non-negotiables.md §File size (one responsibility per file).

         Responsibility: upsert ai_provider_credentials and ai_models rows from
         verification fixtures, encrypting credentials at load time and resolving
         provider_ref (name) → provider_id via SQL lookup.

         FK-safe load order (D-T004-A5):
           load_ai_providers() (loader.py) → load_ai_provider_credentials() → load_ai_models()

Key deps:
  - sqlalchemy==2.0.49 (Session, Engine, inspect, text)
  - cryptography==48.0.0 (via app.security.encryption.encrypt_secret — lazy import)
  - structlog==25.5.0 (BEFORE/AFTER/ERROR logging)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 DB Schema
    (ai_provider_credentials, ai_models)
  - P02-S03-T004 D-T004-A4 (loader SRP), D-T004-A5 (FK-safe order),
    D-T004-A6 (encrypt at load time, never at fixture-author time)
  - 01-non-negotiables.md §Security (Fernet AEAD; never log credential values)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR; no PII/secrets in logs)
"""

from __future__ import annotations

import json

import structlog
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.verification_data.loader_base import LoadResult, _info, _table_exists
from app.verification_data.schemas import AiModelFixture, AiProviderCredentialFixture

log = structlog.get_logger(__name__)


def load_ai_provider_credentials(
    session: Session,
    engine: Engine,
    fixtures: list[AiProviderCredentialFixture],
) -> LoadResult:
    """Load AI provider credentials idempotently into ai_provider_credentials table.

    Encrypts credential_plain at LOAD TIME via app.security.encryption.encrypt_secret()
    (Fernet AEAD). The plain credential is NEVER stored in the DB.

    Idempotency key: (provider_id, auth_type) — upsert on conflict.

    Provider lookup: resolves provider_ref (name) to provider_id via
    SELECT id FROM ai_providers WHERE name = :name. Skips rows where
    provider_ref is not found (warns and continues).

    Args:
        session:  Active SQLAlchemy sync Session.
        engine:   Engine for table-existence checks.
        fixtures: List of AiProviderCredentialFixture objects.

    Returns:
        LoadResult with counts and status.

    Raises:
        EncryptionKeyError: If ENCRYPTION_KEY is not set or is a placeholder.
    """
    _info("verification_data.admin_ai.ai_provider_credentials.start", count=len(fixtures))
    # BEFORE: check required tables exist (deferred-skip pattern)
    if not _table_exists(engine, "ai_provider_credentials"):
        log.warning(
            "verification_data.admin_ai.deferred_until_schema_ready",
            reason="table_missing", table="ai_provider_credentials",
        )
        return LoadResult(
            group="admin_ai", status="deferred",
            reason="table_missing:ai_provider_credentials",
        )
    if not _table_exists(engine, "ai_providers"):
        log.warning(
            "verification_data.admin_ai.deferred_until_schema_ready",
            reason="table_missing", table="ai_providers",
        )
        return LoadResult(
            group="admin_ai", status="deferred", reason="table_missing:ai_providers",
        )

    # Import encrypt_secret lazily — ENCRYPTION_KEY must be valid at call time.
    # D-T004-A6: encrypt at load time, never at fixture-author time.
    from app.security.encryption import encrypt_secret  # noqa: PLC0415

    total_inserted = total_updated = 0
    for fx in fixtures:
        _info(
            "verification_data.admin_ai.ai_provider_credentials.upsert",
            provider_ref=fx.provider_ref,
            auth_type=fx.auth_type,
        )

        # Resolve provider_ref → provider_id
        prov_row = session.execute(
            text("SELECT id FROM ai_providers WHERE name = :name"),
            {"name": fx.provider_ref},
        ).fetchone()
        if prov_row is None:
            log.warning(
                "verification_data.admin_ai.ai_provider_credentials.skip",
                reason="provider_not_found", provider_ref=fx.provider_ref,
            )
            continue

        provider_id = str(prov_row[0])

        # Encrypt at load time — BEFORE log (never log the value, only the length)
        log.debug(
            "verification_data.admin_ai.ai_provider_credentials.encrypt",
            provider_id=provider_id,
            auth_type=fx.auth_type,
            credential_len=len(fx.credential_plain),
        )
        encrypted_secret = encrypt_secret(fx.credential_plain)

        existing = session.execute(
            text(
                "SELECT id FROM ai_provider_credentials"
                " WHERE provider_id = :pid AND auth_type = :auth_type"
            ),
            {"pid": provider_id, "auth_type": fx.auth_type},
        ).fetchone()

        if existing is None:
            session.execute(
                text(
                    "INSERT INTO ai_provider_credentials"
                    " (provider_id, auth_type, encrypted_secret, expires_at)"
                    " VALUES (:pid, :auth_type, :enc, :exp)"
                ),
                {
                    "pid": provider_id,
                    "auth_type": fx.auth_type,
                    "enc": encrypted_secret,
                    "exp": fx.expires_at,
                },
            )
            total_inserted += 1
        else:
            session.execute(
                text(
                    "UPDATE ai_provider_credentials"
                    " SET encrypted_secret = :enc, expires_at = :exp"
                    " WHERE provider_id = :pid AND auth_type = :auth_type"
                ),
                {
                    "pid": provider_id,
                    "auth_type": fx.auth_type,
                    "enc": encrypted_secret,
                    "exp": fx.expires_at,
                },
            )
            total_updated += 1

    session.commit()
    _info(
        "verification_data.admin_ai.ai_provider_credentials.ok",
        inserted=total_inserted, updated=total_updated,
    )
    return LoadResult(
        group="admin_ai", status="ok",
        inserted=total_inserted, updated=total_updated,
    )


def load_ai_models(
    session: Session,
    engine: Engine,
    fixtures: list[AiModelFixture],
) -> LoadResult:
    """Load AI models idempotently into ai_models table.

    Idempotency key: (provider_id, model_id) — upsert on conflict.

    Provider lookup: resolves provider_ref (name) to provider_id via
    SELECT id FROM ai_providers WHERE name = :name. Skips rows where
    provider_ref is not found (warns and continues).

    Sets enabled and is_default from fixture values. The at-most-one-default
    invariant per model_type is enforced at DB level (FU-20260513085435);
    for dev bootstrap a single fixture row per type is expected.

    Args:
        session:  Active SQLAlchemy sync Session.
        engine:   Engine for table-existence checks.
        fixtures: List of AiModelFixture objects.

    Returns:
        LoadResult with counts and status.
    """
    _info("verification_data.admin_ai.ai_models.start", count=len(fixtures))
    # BEFORE: check required tables exist (deferred-skip pattern)
    if not _table_exists(engine, "ai_models"):
        log.warning(
            "verification_data.admin_ai.deferred_until_schema_ready",
            reason="table_missing", table="ai_models",
        )
        return LoadResult(
            group="admin_ai", status="deferred", reason="table_missing:ai_models",
        )
    if not _table_exists(engine, "ai_providers"):
        log.warning(
            "verification_data.admin_ai.deferred_until_schema_ready",
            reason="table_missing", table="ai_providers",
        )
        return LoadResult(
            group="admin_ai", status="deferred", reason="table_missing:ai_providers",
        )

    total_inserted = total_updated = 0
    for fx in fixtures:
        _info(
            "verification_data.admin_ai.ai_models.upsert",
            provider_ref=fx.provider_ref,
            model_id=fx.model_id,
            model_type=fx.model_type,
            enabled=fx.enabled,
            is_default=fx.is_default,
        )

        # Resolve provider_ref → provider_id
        prov_row = session.execute(
            text("SELECT id FROM ai_providers WHERE name = :name"),
            {"name": fx.provider_ref},
        ).fetchone()
        if prov_row is None:
            log.warning(
                "verification_data.admin_ai.ai_models.skip",
                reason="provider_not_found", provider_ref=fx.provider_ref,
            )
            continue

        provider_id = str(prov_row[0])

        existing = session.execute(
            text(
                "SELECT id FROM ai_models"
                " WHERE provider_id = :pid AND model_id = :mid"
            ),
            {"pid": provider_id, "mid": fx.model_id},
        ).fetchone()

        caps_json = json.dumps(fx.capabilities)
        pricing_json = json.dumps(fx.pricing)

        if existing is None:
            session.execute(
                text(
                    "INSERT INTO ai_models"
                    " (provider_id, model_id, model_type, enabled, is_default,"
                    "  capabilities, pricing)"
                    " VALUES (:pid, :mid, :mtype, :enabled, :is_default,"
                    "         CAST(:caps AS JSONB), CAST(:pricing AS JSONB))"
                ),
                {
                    "pid": provider_id, "mid": fx.model_id, "mtype": fx.model_type,
                    "enabled": fx.enabled, "is_default": fx.is_default,
                    "caps": caps_json, "pricing": pricing_json,
                },
            )
            total_inserted += 1
        else:
            session.execute(
                text(
                    "UPDATE ai_models"
                    " SET model_type = :mtype, enabled = :enabled,"
                    "     is_default = :is_default,"
                    "     capabilities = CAST(:caps AS JSONB),"
                    "     pricing = CAST(:pricing AS JSONB)"
                    " WHERE provider_id = :pid AND model_id = :mid"
                ),
                {
                    "pid": provider_id, "mid": fx.model_id, "mtype": fx.model_type,
                    "enabled": fx.enabled, "is_default": fx.is_default,
                    "caps": caps_json, "pricing": pricing_json,
                },
            )
            total_updated += 1

    session.commit()
    _info(
        "verification_data.admin_ai.ai_models.ok",
        inserted=total_inserted, updated=total_updated,
    )
    return LoadResult(
        group="admin_ai", status="ok",
        inserted=total_inserted, updated=total_updated,
    )
