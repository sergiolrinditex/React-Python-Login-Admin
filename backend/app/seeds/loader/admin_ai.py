"""
Loader for the 'admin_ai' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Loads admin_ai/providers.json + admin_ai/models.json into ai_providers + ai_models.
Table-tolerant: tables don't exist until P02-S01-T001; skips cleanly when missing.

CHANGE from T003:
  - AiProviderSeed validates with bundle_type context.
  - Productive bundles: api_key resolved from api_key_env via resolve_env_var().
    The real key is NEVER logged — only 'api_key_masked=<env_var_name>' appears.
  - AiModelSeed: updated SQL to match new shape (name, capability, is_active,
    auto_discovered, display_name).
  - Fail-fast if env var is missing for productive provider with api_key_env set.

SECURITY:
  - Real api_key values NEVER in logs. Only the env var NAME is logged (not value).
  - Resolved key is used only in DB insert; not retained in memory after conn.execute().

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - pydantic 2.12.5
  - structlog 25.5.0
"""
from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger
from app.seeds.io import load_fixture
from app.seeds.loader._common import BundleType, LoadReport, resolve_env_var
from app.seeds.schemas.admin_ai import (
    AiModelListSeed,
    AiProviderListSeed,
    AiProviderSeed,
)
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


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


async def load_admin_ai(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
    bundle_type: BundleType = "synthetic",
) -> LoadReport:
    """Load the 'admin_ai' namespace: admin_ai/providers.json + models.json.

    Purpose: seed AI provider and model records for J103 admin AI journey.
    Tables targeted: ai_providers, ai_models.
    Table-tolerant: logs WARN and skips if tables do not exist (P00/P01 state).

    Env-var resolution (productive bundle):
      For each provider with api_key_env set, resolve_env_var() reads the real key
      from the process environment. Fails fast with clear error if not set.

    Params:
      engine      — async engine.
      source_dir  — bundle root directory.
      dry_run     — validate only; no DB writes.
      bundle_type — 'synthetic' or 'productive'; forwarded to schema validators.
    Returns: LoadReport.
    Errors: BundleLoadError if fixture missing/invalid or productive env var missing.
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

    ai_prov_exist = await table_exists(engine, "ai_providers")
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
            # Resolve api_key from env var for productive bundles.
            api_key: str | None = None
            if provider.api_key_env:
                api_key = resolve_env_var(provider.api_key_env, required=True)
                _logger.debug(
                    "seed.admin_ai.upsert_provider.before",
                    provider_name=provider.name,
                    api_key_env=provider.api_key_env,
                    api_key_masked="[resolved_from_env]",
                )
            elif provider.api_key:
                api_key = provider.api_key
                masked_key = provider.api_key[:4] + "..." if len(provider.api_key) > 4 else "..."
                _logger.debug(
                    "seed.admin_ai.upsert_provider.before",
                    provider_name=provider.name,
                    api_key_masked=masked_key,
                )
            else:
                _logger.debug(
                    "seed.admin_ai.upsert_provider.before",
                    provider_name=provider.name,
                    api_key_masked="[none — public provider]",
                )

            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO ai_providers
                          (name, provider_type, api_key, base_url, is_active, description)
                        VALUES
                          (:name, :provider_type, :api_key, :base_url, :is_active, :description)
                        ON CONFLICT (name) DO UPDATE
                          SET provider_type = EXCLUDED.provider_type,
                              api_key = EXCLUDED.api_key,
                              base_url = EXCLUDED.base_url,
                              is_active = EXCLUDED.is_active,
                              description = EXCLUDED.description
                        """
                    ),
                    {
                        "name": provider.name,
                        "provider_type": provider.provider_type,
                        "api_key": api_key,
                        "base_url": provider.base_url,
                        "is_active": provider.is_active,
                        "description": provider.description,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)
            _logger.debug("seed.admin_ai.upsert_provider.after", provider_name=provider.name)

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
            display_name = model.display_name or model.name
            _logger.debug(
                "seed.admin_ai.upsert_model.before",
                model_name=model.name,
                capability=model.capability,
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO ai_models
                          (name, model_id, provider_name, display_name, capability,
                           is_active, auto_discovered, context_window)
                        VALUES
                          (:name, :model_id, :provider_name, :display_name, :capability,
                           :is_active, :auto_discovered, :context_window)
                        ON CONFLICT (name) DO UPDATE
                          SET model_id = EXCLUDED.model_id,
                              provider_name = EXCLUDED.provider_name,
                              display_name = EXCLUDED.display_name,
                              capability = EXCLUDED.capability,
                              is_active = EXCLUDED.is_active,
                              auto_discovered = EXCLUDED.auto_discovered,
                              context_window = EXCLUDED.context_window
                        """
                    ),
                    {
                        "name": model.name,
                        "model_id": model.model_id,
                        "provider_name": model.provider_name,
                        "display_name": display_name,
                        "capability": model.capability,
                        "is_active": model.is_active,
                        "auto_discovered": model.auto_discovered,
                        "context_window": model.context_window,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)
            _logger.debug("seed.admin_ai.upsert_model.after", model_name=model.name)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
