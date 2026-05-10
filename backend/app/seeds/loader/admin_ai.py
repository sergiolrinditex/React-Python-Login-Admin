"""
Loader for the 'admin_ai' namespace.

Slice: P00-S02-T010 — Fix admin_ai seed loader to match real §10.3 schema
Phase: P00 — Scaffold + Design System

Loads admin_ai/providers.json + admin_ai/models.json into the THREE real tables:
  - ai_providers              (name, provider_type, base_url, status)
  - ai_provider_credentials   (provider_id, auth_type, encrypted_secret, expires_at)
  - ai_models                 (provider_id, model_id, model_type, enabled, auto_discovered)

Table-tolerant: tables don't exist until migration 0003; skips cleanly when missing.

FIXED in T010 (was broken in T005):
  - ai_providers INSERT now uses real §10.3 columns (no api_key / is_active / description).
    Idempotency: SELECT-then-INSERT (no UNIQUE on name in migration 0003).
    seed.is_active=True  → status='active'; False → status='draft'.
  - ai_provider_credentials INSERT added (was completely missing).
    Idempotency: DELETE WHERE provider_id + INSERT inside same transaction.
    api_key_env → resolved plaintext → Fernet-encrypted via app.core.security.encrypt_secret.
    auth_type mapping: provider_type='litellm' → 'master_key'; others → 'api_key'.
  - ai_models INSERT now uses real §10.3 columns.
    ON CONFLICT (provider_id, model_id) DO UPDATE (real UNIQUE index from migration 0003).
    provider_name → provider_id resolved from the provider upsert result dict.
    capability mapping: 'chat' → 'chat'; 'embedding' → 'embedding';
                        'reranker' → 'unknown' + warning (no DB enum yet; R3).
    Dropped columns: name, display_name, context_window (not in §10.3 DDL).

SECURITY:
  - Real api_key values NEVER in logs. Only env var NAME and masked status.
  - Fernet token (encrypted_secret) NEVER logged — only length hint at debug.
  - Fernet helper: app.core.security.encrypt_secret — same as discover-models endpoint.

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - pydantic 2.12.5
  - structlog 25.5.0
  - app.core.security (encrypt_secret — Fernet AEAD)

Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 + ADR-001 §15
        migration 0003_admin_ai_providers_models.py
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger
from app.core.security import encrypt_secret
from app.seeds.io import load_fixture
from app.seeds.loader._common import BundleType, LoadReport, resolve_env_var
from app.seeds.schemas.admin_ai import (
    AiModelListSeed,
    AiModelSeed,
    AiProviderListSeed,
    AiProviderSeed,
)
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Capability mapping: seed schema → §10.3 model_type enum
# ---------------------------------------------------------------------------

_CAPABILITY_TO_MODEL_TYPE: dict[str, str] = {
    "chat": "chat",
    "embedding": "embedding",
    # R3: 'reranker' has no §10.3 equivalent yet; map to 'unknown' + warn.
    "reranker": "unknown",
}


def _validate_providers(
    providers_data: AiProviderListSeed, bundle_type: BundleType
) -> list[AiProviderSeed]:
    """Validate each provider with bundle_type context.

    Purpose: ensure synthetic/productive guards are applied per provider.
    Returns: validated list (same objects, re-validated).
    Errors: BundleLoadError on validation failure.
    """
    from app.seeds.io import BundleLoadError  # noqa: PLC0415

    validated = []
    for raw_provider in providers_data.providers:
        try:
            p = AiProviderSeed.validate_with_bundle_type(raw_provider.model_dump(), bundle_type)
            validated.append(p)
        except ValueError as exc:
            raise BundleLoadError(
                Path("admin_ai/providers.json"),
                f"Provider '{raw_provider.name}': {exc}",
            ) from exc
    return validated


def _map_auth_type(provider_type: str) -> str:
    """Map provider_type to auth_type for ai_provider_credentials.

    Purpose: LiteLLM uses a master_key header; other providers use api_key.
    Params:
      provider_type — value from AiProviderSeed.provider_type field.
    Returns: 'master_key' for litellm, 'api_key' for all others.
    Source: ADR-001 §15 (T006 credential model decision).
    """
    return "master_key" if provider_type == "litellm" else "api_key"


async def _upsert_provider(
    engine: AsyncEngine,
    provider: AiProviderSeed,
) -> uuid.UUID | None:
    """SELECT-then-INSERT for ai_providers using real §10.3 columns.

    Idempotency pattern: no UNIQUE on name in migration 0003, so we
    SELECT first — if row exists, return its id without INSERT.

    Params:
      engine   — async engine.
      provider — validated AiProviderSeed.
    Returns: UUID of the provider row, or None on unexpected DB error.
    Errors: propagates sqlalchemy OperationalError (re-raised to caller).
    """
    status = "active" if provider.is_active else "draft"
    _logger.debug(
        "seed.admin_ai.provider.before",
        provider_name=provider.name,
        provider_type=provider.provider_type,
        status=status,
    )

    async with engine.begin() as conn:
        # Check if provider already exists (no UNIQUE constraint; SELECT-then-INSERT).
        existing = await conn.execute(
            text("SELECT id FROM ai_providers WHERE name = :name"),
            {"name": provider.name},
        )
        row = existing.fetchone()
        if row is not None:
            provider_id: uuid.UUID = row[0]
            _logger.debug(
                "seed.admin_ai.provider.exists",
                provider_name=provider.name,
                provider_id=str(provider_id),
            )
            return provider_id

        # Insert new provider row with real §10.3 columns.
        result = await conn.execute(
            text(
                """
                INSERT INTO ai_providers
                  (name, provider_type, base_url, status, created_by)
                VALUES
                  (:name, :provider_type, :base_url, :status, NULL)
                RETURNING id
                """
            ),
            {
                "name": provider.name,
                "provider_type": provider.provider_type,
                "base_url": provider.base_url,
                "status": status,
            },
        )
        provider_id = result.scalar_one()

    _logger.debug(
        "seed.admin_ai.provider.after",
        provider_name=provider.name,
        provider_id=str(provider_id),
    )
    return provider_id


async def _upsert_credential(
    engine: AsyncEngine,
    provider: AiProviderSeed,
    provider_id: uuid.UUID,
    api_key: str,
) -> None:
    """DELETE+INSERT credential for ai_provider_credentials (rotation pattern).

    Idempotency: DELETE existing credentials for this provider_id, then INSERT
    the new encrypted one in the same transaction. Atomic for concurrent readers.

    Params:
      engine      — async engine.
      provider    — AiProviderSeed (for logging — name/provider_type only).
      provider_id — UUID of the parent ai_providers row.
      api_key     — cleartext API key to encrypt (NEVER logged).
    Errors: CryptoError if Fernet key is invalid (propagated).
    """
    auth_type = _map_auth_type(provider.provider_type)
    _logger.debug(
        "seed.admin_ai.credential.before",
        provider_name=provider.name,
        auth_type=auth_type,
        env_var=provider.api_key_env,
    )

    # Fernet-encrypt the cleartext key.
    encrypted_token = encrypt_secret(api_key)

    async with engine.begin() as conn:
        # Rotation: remove existing credentials for this provider.
        await conn.execute(
            text("DELETE FROM ai_provider_credentials WHERE provider_id = :pid"),
            {"pid": str(provider_id)},
        )
        # Insert new encrypted credential.
        await conn.execute(
            text(
                """
                INSERT INTO ai_provider_credentials
                  (provider_id, auth_type, encrypted_secret, expires_at)
                VALUES
                  (:pid, :auth_type, :encrypted_secret, NULL)
                """
            ),
            {
                "pid": str(provider_id),
                "auth_type": auth_type,
                "encrypted_secret": encrypted_token,
            },
        )

    # NEVER log the token or cleartext. Log only length as proof of activity.
    _logger.debug(
        "seed.admin_ai.credential.after",
        provider_name=provider.name,
        auth_type=auth_type,
        token_length=len(encrypted_token),
    )


async def _upsert_model(
    engine: AsyncEngine,
    model: AiModelSeed,
    provider_id_by_name: dict[str, uuid.UUID],
    report: LoadReport,
) -> bool:
    """INSERT OR UPDATE ai_models using real §10.3 columns and the real UNIQUE index.

    Idempotency: ON CONFLICT (provider_id, model_id) DO UPDATE
    per uq_ai_models_provider_id_model_id (real UNIQUE index from migration 0003).

    Params:
      engine             — async engine.
      model              — validated AiModelSeed.
      provider_id_by_name — dict mapping provider name → UUID from the providers loop.
      report             — LoadReport to update rows_inserted counter.
    Returns: True if row was inserted/updated, False if orphan (skip).
    """
    provider_id = provider_id_by_name.get(model.provider_name)
    if provider_id is None:
        _logger.warning(
            "seed.admin_ai.model.orphan",
            model_name=model.name,
            model_id=model.model_id,
            provider_name=model.provider_name,
            reason="provider_not_in_run",
        )
        return False

    # Map capability → model_type.
    model_type = _CAPABILITY_TO_MODEL_TYPE.get(model.capability, "unknown")
    if model.capability == "reranker":
        _logger.warning(
            "seed.admin_ai.model.reranker_mapped",
            model_id=model.model_id,
            reason="reranker has no §10.3 model_type; mapped to unknown (R3)",
        )

    _logger.debug(
        "seed.admin_ai.model.before",
        model_id=model.model_id,
        model_type=model_type,
        provider_name=model.provider_name,
        enabled=model.is_active,
        auto_discovered=model.auto_discovered,
    )

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                INSERT INTO ai_models
                  (provider_id, model_id, model_type, enabled, auto_discovered)
                VALUES
                  (:provider_id, :model_id, :model_type, :enabled, :auto_discovered)
                ON CONFLICT (provider_id, model_id) DO UPDATE
                  SET model_type      = EXCLUDED.model_type,
                      enabled         = EXCLUDED.enabled,
                      auto_discovered = EXCLUDED.auto_discovered
                """
            ),
            {
                "provider_id": str(provider_id),
                "model_id": model.model_id,
                "model_type": model_type,
                "enabled": model.is_active,
                "auto_discovered": model.auto_discovered,
            },
        )
    report.rows_inserted += max(result.rowcount, 1)

    _logger.debug(
        "seed.admin_ai.model.after",
        model_id=model.model_id,
        provider_name=model.provider_name,
    )
    return True


async def load_admin_ai(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
    bundle_type: BundleType = "synthetic",
) -> LoadReport:
    """Load the 'admin_ai' namespace: providers.json + models.json.

    Purpose: seed AI provider + credential + model records for J103 admin AI journey.
    Tables targeted: ai_providers, ai_provider_credentials, ai_models.
    Table-tolerant: logs WARN and skips if tables do not exist (P00/P01 state).

    Idempotency:
      - ai_providers: SELECT-then-INSERT (no UNIQUE on name in migration 0003).
      - ai_provider_credentials: DELETE WHERE provider_id + INSERT (rotation pattern).
      - ai_models: ON CONFLICT (provider_id, model_id) DO UPDATE.

    Env-var resolution (productive bundle):
      For each provider with api_key_env set, resolve_env_var() reads the real key
      from the process environment. Fails fast with BundleLoadError if not set.
      The plaintext is Fernet-encrypted via app.core.security.encrypt_secret before
      being stored in ai_provider_credentials.encrypted_secret.

    Params:
      engine      — async engine.
      source_dir  — bundle root directory.
      dry_run     — validate only; no DB writes.
      bundle_type — 'synthetic' or 'productive'; forwarded to schema validators.
    Returns: LoadReport.
    Errors: BundleLoadError if fixture missing/invalid or productive env var missing.
            CryptoError if Fernet key is invalid (propagated from encrypt_secret).
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="admin_ai", dry_run=dry_run)
    ns = "admin_ai"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run, bundle_type=bundle_type)

    providers_data = load_fixture(source_dir, ns, "providers.json", AiProviderListSeed)
    models_data = load_fixture(source_dir, ns, "models.json", AiModelListSeed)

    # Validate with bundle_type context (productive guard).
    validated_providers = _validate_providers(providers_data, bundle_type)

    if dry_run:
        report.duration_ms = (time.monotonic() - t0) * 1000
        _logger.info("seed.namespace.done", namespace=ns, persisted=0, dry_run=True)
        return report

    # -----------------------------------------------------------------------
    # Phase 1 — ai_providers (and ai_provider_credentials)
    # -----------------------------------------------------------------------
    ai_prov_exist = await table_exists(engine, "ai_providers")
    ai_cred_exist = await table_exists(engine, "ai_provider_credentials")

    # Track provider_id by name for the models phase.
    provider_id_by_name: dict[str, uuid.UUID] = {}

    if not ai_prov_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="ai_providers",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("ai_providers")
    else:
        for provider in validated_providers:
            # Resolve api_key from env var or plaintext (synthetic path).
            api_key: str | None = None
            if provider.api_key_env:
                api_key = resolve_env_var(provider.api_key_env, required=True)
                _logger.debug(
                    "seed.admin_ai.key.resolved",
                    provider_name=provider.name,
                    env_var=provider.api_key_env,
                    resolved="[from_env]",
                )
            elif provider.api_key:
                api_key = provider.api_key
                # Mask: show only first 4 chars for debug tracing (no real key visible).
                masked = provider.api_key[:4] + "..." if len(provider.api_key) > 4 else "..."
                _logger.debug(
                    "seed.admin_ai.key.resolved",
                    provider_name=provider.name,
                    api_key_masked=masked,
                    resolved="[inline_synthetic]",
                )
            else:
                _logger.debug(
                    "seed.admin_ai.key.resolved",
                    provider_name=provider.name,
                    resolved="[none — public provider]",
                )

            # Upsert the provider row (SELECT-then-INSERT).
            provider_id = await _upsert_provider(engine, provider)
            if provider_id is None:
                continue

            provider_id_by_name[provider.name] = provider_id
            report.rows_inserted += 1

            # Upsert the credential when a key is available and credentials table exists.
            if api_key and ai_cred_exist:
                await _upsert_credential(engine, provider, provider_id, api_key)
                report.rows_inserted += 1
            elif api_key and not ai_cred_exist:
                _logger.warning(
                    "seed.namespace.table_missing",
                    namespace=ns,
                    table="ai_provider_credentials",
                    reason="table_missing",
                    action="credential_skipped",
                )
                if "ai_provider_credentials" not in report.skipped_tables:
                    report.skipped_tables.append("ai_provider_credentials")

    # -----------------------------------------------------------------------
    # Phase 2 — ai_models
    # -----------------------------------------------------------------------
    ai_model_exist = await table_exists(engine, "ai_models")
    if not ai_model_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="ai_models",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("ai_models")
    else:
        for model in models_data.models:
            await _upsert_model(engine, model, provider_id_by_name, report)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
