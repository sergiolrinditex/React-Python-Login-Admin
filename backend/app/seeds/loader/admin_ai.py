"""
Loader for the 'admin_ai' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Loads admin_ai/providers.json + admin_ai/models.json into ai_providers +
ai_models (table-tolerant).

NOTE on encryption: synthetic credentials are written as plaintext because
they start with 'synthetic-' and carry no real value. When P02-S02-T001
lands the encryption service, a follow-up task will add encrypt-on-write
here. Do NOT implement encryption in this loader.

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
from app.seeds.loader._common import LoadReport
from app.seeds.schemas.admin_ai import AiModelListSeed, AiProviderListSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


async def load_admin_ai(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
) -> LoadReport:
    """Load the 'admin_ai' namespace: admin_ai/providers.json + models.json.

    Purpose: seed AI provider and model records for J103 admin AI journey.
    Tables targeted: ai_providers, ai_models.
    Table-tolerant: logs WARN and skips if tables do not exist.

    IMPORTANT — encryption: synthetic credentials are written as plaintext
      because they start with 'synthetic-' and carry no real value.
      When P02-S02-T001 lands the encryption service, a follow-up task will
      add encrypt-on-write here. Do NOT implement encryption in this loader.

    Params/Returns/Errors: see load_auth docstring.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="admin_ai", dry_run=dry_run)
    ns = "admin_ai"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run)

    providers_data = load_fixture(source_dir, ns, "providers.json", AiProviderListSeed)
    models_data = load_fixture(source_dir, ns, "models.json", AiModelListSeed)

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
        for provider in providers_data.providers:
            # Mask synthetic api_key in logs (first 4 chars + ...).
            masked_key = provider.api_key[:4] + "..." if len(provider.api_key) > 4 else "..."
            _logger.debug(
                "seed.admin_ai.upsert_provider.before",
                provider_name=provider.name,
                api_key_masked=masked_key,
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
                        "api_key": provider.api_key,
                        "base_url": provider.base_url,
                        "is_active": provider.is_active,
                        "description": provider.description,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)

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
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO ai_models (model_id, provider_name, display_name, enabled)
                        VALUES (:model_id, :provider_name, :display_name, :enabled)
                        ON CONFLICT (model_id) DO UPDATE
                          SET provider_name = EXCLUDED.provider_name,
                              display_name = EXCLUDED.display_name,
                              enabled = EXCLUDED.enabled
                        """
                    ),
                    {
                        "model_id": model.model_id,
                        "provider_name": model.provider_name,
                        "display_name": model.display_name,
                        "enabled": model.enabled,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
