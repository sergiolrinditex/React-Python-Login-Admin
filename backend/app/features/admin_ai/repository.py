"""
SQLAlchemy repository for admin_ai feature — discover-models slice.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Responsibilities (single: data access for the discover-models use case):
  - fetch_provider       — look up an AiProvider by UUID primary key.
  - fetch_credential     — look up the first active AiProviderCredential for a provider.
  - list_existing_models — return existing AiModel rows for a provider_id.
  - upsert_new_models    — insert models that don't exist yet (SELECT-then-INSERT diff).
  - insert_audit_log     — append an AuditLog row for the discover action.

Design: SELECT-then-INSERT diff pattern (cleaner than ON CONFLICT DO NOTHING for
getting the diff). Caller passes a list of ProviderModel; repository returns
(added: list[AiModel], existing: list[AiModel]).

Transaction: session is managed by the FastAPI get_session() dependency (unit-of-work
per request). Repository methods do NOT commit — the session commits after the route
handler returns normally, or rolls back on exception.

Indexes relied on (migration 0003):
  - uq_ai_models_provider_id_model_id (UNIQUE) — O(log n) lookup per model_id.
  - ix_ai_provider_credentials_provider_id — FK join on fetch_credential.

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - app.db.models.admin_ai (AiProvider, AiProviderCredential, AiModel)
  - app.db.models.auth (AuditLog)
  - app.core.logging (get_logger)

Source: task-pack P00-S02-T006 §7 steps 7 + §A2 + §B3 + §6.3
HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.admin_ai import AiModel, AiProvider, AiProviderCredential
from app.db.models.auth import AuditLog

if TYPE_CHECKING:
    from app.features.admin_ai.provider_clients import ProviderModel

_logger = get_logger(__name__)


async def fetch_provider(
    session: AsyncSession,
    provider_id: uuid.UUID,
) -> AiProvider | None:
    """Fetch an AiProvider row by primary key.

    Purpose: look up the provider record before making a remote call.
    Params:
      session     — SQLAlchemy async session (from FastAPI get_session).
      provider_id — UUID primary key.
    Returns: AiProvider ORM instance, or None if not found.
    Raises: sqlalchemy.exc.SQLAlchemyError on DB error (propagated to caller).
    """
    _logger.debug("BEFORE fetch_provider", provider_id=str(provider_id))
    result = await session.execute(
        sa.select(AiProvider).where(AiProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    _logger.debug(
        "AFTER fetch_provider",
        provider_id=str(provider_id),
        found=provider is not None,
    )
    return provider


async def fetch_credential(
    session: AsyncSession,
    provider_id: uuid.UUID,
) -> AiProviderCredential | None:
    """Fetch the first non-expired AiProviderCredential for a provider.

    Purpose: retrieve the encrypted credential for on-the-fly decryption.
    Returns the first credential ordered by id (insertion order). If multiple
    credentials exist (key rotation), the most recently inserted row wins
    because gen_random_uuid() v4 sorts roughly by insertion time.

    Security: the encrypted_secret column is returned as-is; decryption happens
    in the service layer via app.core.security.decrypt_secret(). Never log it.

    Params:
      session     — SQLAlchemy async session.
      provider_id — UUID of the parent ai_providers row.
    Returns: AiProviderCredential or None (if no credential is configured).
    Raises: sqlalchemy.exc.SQLAlchemyError on DB error.
    """
    _logger.debug("BEFORE fetch_credential", provider_id=str(provider_id))
    now = datetime.now(tz=UTC)
    result = await session.execute(
        sa.select(AiProviderCredential)
        .where(AiProviderCredential.provider_id == provider_id)
        .where(
            sa.or_(
                AiProviderCredential.expires_at.is_(None),
                AiProviderCredential.expires_at > now,
            )
        )
        .order_by(AiProviderCredential.id)
        .limit(1)
    )
    cred = result.scalar_one_or_none()
    _logger.debug(
        "AFTER fetch_credential",
        provider_id=str(provider_id),
        found=cred is not None,
    )
    return cred


async def list_existing_models(
    session: AsyncSession,
    provider_id: uuid.UUID,
) -> list[AiModel]:
    """Return all AiModel rows currently in the catalog for a provider.

    Purpose: used in the SELECT-then-INSERT diff — existing model_ids are
    checked against this set before inserting new rows.

    Params:
      session     — SQLAlchemy async session.
      provider_id — UUID of the parent ai_providers row.
    Returns: list of AiModel ORM instances (may be empty for new providers).
    Raises: sqlalchemy.exc.SQLAlchemyError on DB error.
    """
    _logger.debug("BEFORE list_existing_models", provider_id=str(provider_id))
    result = await session.execute(
        sa.select(AiModel)
        .where(AiModel.provider_id == provider_id)
        .order_by(AiModel.model_id)
    )
    models = list(result.scalars().all())
    _logger.debug(
        "AFTER list_existing_models",
        provider_id=str(provider_id),
        count=len(models),
    )
    return models


async def upsert_new_models(
    session: AsyncSession,
    provider_id: uuid.UUID,
    provider_models: list[ProviderModel],
) -> tuple[list[AiModel], list[AiModel]]:
    """Insert new models and return (added, existing) split.

    Algorithm (SELECT-then-INSERT diff):
      1. Load existing model_ids for this provider.
      2. For each ProviderModel not already in the existing set, INSERT a new row
         with auto_discovered=True, enabled=False, is_default=False.
      3. Return added (new rows) and existing (unchanged rows).

    Acceptance A2: existing rows by (provider_id, model_id) are LEFT UNCHANGED.
    The UNIQUE index on (provider_id, model_id) prevents duplicate inserts; we
    rely on the in-memory diff rather than ON CONFLICT to preserve this invariant.

    Params:
      session        — SQLAlchemy async session.
      provider_id    — UUID of the parent ai_providers row.
      provider_models — normalised models from the provider client.
    Returns: (added, existing) — lists of AiModel ORM instances.
    Raises: sqlalchemy.exc.SQLAlchemyError on DB error (session rolls back).

    Logs: BEFORE (counts), AFTER (added_count, existing_count).
    """
    _logger.info(
        "BEFORE upsert_new_models",
        provider_id=str(provider_id),
        provider_model_count=len(provider_models),
    )

    # Step 1: load current catalog
    existing_rows = await list_existing_models(session, provider_id)
    existing_ids: set[str] = {m.model_id for m in existing_rows}

    # Step 2: insert new rows
    added_rows: list[AiModel] = []
    for pm in provider_models:
        if pm.model_id in existing_ids:
            continue
        new_model = AiModel(
            id=uuid.uuid4(),
            provider_id=provider_id,
            model_id=pm.model_id,
            model_type=pm.model_type,
            capabilities=[],
            enabled=False,
            is_default=False,
            pricing={},
            latency_ms_avg=None,
            auto_discovered=True,
        )
        session.add(new_model)
        added_rows.append(new_model)

    # Flush so added rows get their DB defaults (server_default for id if not set)
    if added_rows:
        await session.flush()

    # Step 3: return split
    # Existing = rows that matched provider_models (reported as already catalogued)
    provider_model_ids = {pm.model_id for pm in provider_models}
    matched_existing = [m for m in existing_rows if m.model_id in provider_model_ids]

    _logger.info(
        "AFTER upsert_new_models",
        provider_id=str(provider_id),
        added_count=len(added_rows),
        existing_count=len(matched_existing),
    )
    return added_rows, matched_existing


async def insert_audit_log(
    session: AsyncSession,
    provider_id: uuid.UUID,
    provider_type: str,
    total_seen: int,
    added_count: int,
    existing_count: int,
    skipped_count: int,
    request_id: str,
) -> None:
    """Append an audit_log row for the discover-models action (B3).

    Uses the §10.3 AuditLog schema shape: (actor_user_id, action, entity_type,
    entity_id, metadata, created_at). Per discrepancy D2: the non-negotiable
    §Audit log fields (ip, user_agent, request_id) are not yet columns — they
    live inside the metadata JSONB for now. P01-S01-T005 adds the columns.

    Action string: 'ai.provider.discover_models' (per task-pack §B3).

    Params:
      session       — SQLAlchemy async session.
      provider_id   — entity_id (UUID of the ai_provider that was queried).
      provider_type — metadata field.
      total_seen    — from the provider response.
      added_count   — models inserted.
      existing_count — models already in catalog.
      skipped_count — models skipped (parse errors / unsupported type).
      request_id    — from X-Request-ID middleware (correlation ID).
    Raises: sqlalchemy.exc.SQLAlchemyError on DB error.
    """
    _logger.debug(
        "BEFORE insert_audit_log",
        action="ai.provider.discover_models",
        provider_id=str(provider_id),
        total_seen=total_seen,
    )
    audit = AuditLog(
        id=uuid.uuid4(),
        actor_user_id=None,  # system action (no user session in P00 stub)
        action="ai.provider.discover_models",
        entity_type="ai_provider",
        entity_id=provider_id,  # UUID column — pass UUID directly
        metadata_col={
            "provider_type": provider_type,
            "total_seen": total_seen,
            "added_count": added_count,
            "existing_count": existing_count,
            "skipped_count": skipped_count,
            "request_id": request_id,
        },
        created_at=datetime.now(tz=UTC),
    )
    session.add(audit)
    await session.flush()
    _logger.debug(
        "AFTER insert_audit_log",
        action="ai.provider.discover_models",
        provider_id=str(provider_id),
    )
