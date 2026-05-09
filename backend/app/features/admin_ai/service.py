"""
Service layer for admin_ai — discover-models use case.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Single responsibility: orchestrate the discover-models use case end-to-end.

Business rule (ADR-001 §15):
  Given a provider_id, fetch the provider record and its encrypted credential,
  decrypt the credential, call the provider-specific HTTP endpoint to list
  available models, reconcile the results against the ai_models catalog,
  persist new rows with auto_discovered=True, and log an audit entry.

Side effects:
  - Inserts rows into ai_models for newly discovered models.
  - Inserts one row into audit_logs.
  - Does NOT commit (session commit is handled by FastAPI's get_session dependency).

Error mapping (for routes.py):
  - ProviderNotFoundError → HTTP 404
  - UnsupportedProviderError → HTTP 422
  - CryptoError / no-credential → HTTP 502 (upstream provider config issue)
  - UpstreamProviderError → HTTP 502
  - sqlalchemy.exc.SQLAlchemyError → propagated (FastAPI 500 via default handler)

Logging (C1):
  BEFORE: route, provider_id, request_id (no credential, no base_url with key)
  AFTER:  added_count, existing_count, total_seen, latency_ms
  ERROR:  error_class + sanitised upstream_status (no key value, no raw body)

Dependencies:
  - app.features.admin_ai.repository (data access)
  - app.features.admin_ai.provider_clients (HTTP dispatch)
  - app.features.admin_ai.schemas (response models)
  - app.core.security (decrypt_secret, CryptoError)
  - app.core.logging (get_logger)
  - sqlalchemy.ext.asyncio.AsyncSession

Source: task-pack P00-S02-T006 §7 step 8 + §A1-A6 + §C1-C4
HILO_PEOPLE_TECHNICAL_GUIDE.md ADR-001 §15
"""
from __future__ import annotations

import time
import uuid

import structlog.contextvars
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import decrypt_secret
from app.features.admin_ai import provider_clients as pc
from app.features.admin_ai import repository as repo
from app.features.admin_ai.schemas import (
    AiModelOut,
    DiscoverModelsData,
    SkippedModel,
)

_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom domain errors
# ---------------------------------------------------------------------------


class ProviderNotFoundError(Exception):
    """Raised when the provider_id does not exist in ai_providers.

    Purpose: typed error for routes.py to return HTTP 404 cleanly.
    """

    def __init__(self, provider_id: uuid.UUID) -> None:
        """Initialise with the missing provider_id."""
        self.provider_id = provider_id
        super().__init__(f"Provider {provider_id} not found")


class MissingCredentialError(Exception):
    """Raised when no active credential exists for the provider.

    Purpose: typed error that maps to HTTP 502 (upstream provider config issue).
    This is a deployment/configuration problem, not a caller error.
    """

    def __init__(self, provider_id: uuid.UUID) -> None:
        """Initialise with the provider_id missing a credential."""
        self.provider_id = provider_id
        super().__init__(f"No active credential found for provider {provider_id}")


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


async def discover_models(
    session: AsyncSession,
    provider_id: uuid.UUID,
) -> DiscoverModelsData:
    """Discover models from an AI provider and reconcile against the catalog.

    Business rule (ADR-001):
      1. Fetch provider record → ProviderNotFoundError if missing.
      2. Fetch active credential → MissingCredentialError if none.
      3. Decrypt credential → CryptoError if tampered/wrong key.
      4. Dispatch to provider-specific HTTP client → UpstreamProviderError on failure.
      5. Normalise model list; build skipped list for invalid entries.
      6. Upsert new rows into ai_models (auto_discovered=True).
      7. Append audit_log row.
      8. Return DiscoverModelsData diff.

    Side effects: inserts into ai_models + audit_logs (session not committed here).

    Params:
      session     — SQLAlchemy async session from FastAPI get_session dependency.
      provider_id — UUID of the ai_providers row to query.
    Returns: DiscoverModelsData with added/existing/skipped/total_seen.
    Raises:
      ProviderNotFoundError    — if provider_id does not exist (→ HTTP 404).
      MissingCredentialError   — if no active credential is configured (→ HTTP 502).
      CryptoError              — if decryption fails (→ HTTP 502).
      UnsupportedProviderError — if provider_type is unknown (→ HTTP 422).
      UpstreamProviderError    — if the remote call fails (→ HTTP 502).

    Logging: BEFORE (provider_id, request_id) AFTER (added, existing, total_seen, ms).
    Security: credential plaintext lives only in this function scope, never logged.
    """
    # Grab request_id from structlog contextvars (bound by request_id_middleware)
    context = structlog.contextvars.get_contextvars()
    request_id = context.get("request_id", "")
    t_start = time.monotonic()

    _logger.info(
        "discover_models BEFORE",
        provider_id=str(provider_id),
        request_id=request_id,
    )

    # Step 1 — fetch provider
    provider = await repo.fetch_provider(session, provider_id)
    if provider is None:
        _logger.warning(
            "ERROR discover_models: provider not found",
            provider_id=str(provider_id),
        )
        raise ProviderNotFoundError(provider_id)

    # Step 2 — fetch credential
    cred = await repo.fetch_credential(session, provider_id)
    if cred is None:
        _logger.warning(
            "ERROR discover_models: no active credential",
            provider_id=str(provider_id),
            provider_type=provider.provider_type,
        )
        raise MissingCredentialError(provider_id)

    # Step 3 — decrypt (may raise CryptoError)
    # Security: cleartext lives in this local scope only. Never logged, never returned.
    plaintext_key = decrypt_secret(cred.encrypted_secret)

    # Step 4 — dispatch to provider client
    client = pc.get_provider_client(
        provider_type=provider.provider_type,
        base_url=provider.base_url or "",
        api_key=plaintext_key,
    )
    # Clear the key reference ASAP (plaintext_key is still in scope until fn ends,
    # but we prevent accidental re-use by reassigning the name)
    del plaintext_key

    provider_models = await client.list_models()

    # Step 5 — classify: valid provider models vs skipped
    valid_models: list[pc.ProviderModel] = []
    skipped: list[SkippedModel] = []
    for pm in provider_models:
        if not pm.model_id:
            skipped.append(SkippedModel(model_id="", reason="empty_model_id"))
            continue
        valid_models.append(pm)

    total_seen = len(provider_models)

    # Step 6 — upsert
    added_rows, existing_rows = await repo.upsert_new_models(
        session, provider_id, valid_models
    )

    # Step 7 — audit log
    await repo.insert_audit_log(
        session=session,
        provider_id=provider_id,
        provider_type=provider.provider_type,
        total_seen=total_seen,
        added_count=len(added_rows),
        existing_count=len(existing_rows),
        skipped_count=len(skipped),
        request_id=request_id,
    )

    # Step 8 — build response
    latency_ms = int((time.monotonic() - t_start) * 1000)
    _logger.info(
        "discover_models AFTER",
        provider_id=str(provider_id),
        added_count=len(added_rows),
        existing_count=len(existing_rows),
        skipped_count=len(skipped),
        total_seen=total_seen,
        latency_ms=latency_ms,
        request_id=request_id,
    )

    return DiscoverModelsData(
        added=[AiModelOut.model_validate(m) for m in added_rows],
        existing=[AiModelOut.model_validate(m) for m in existing_rows],
        skipped=skipped,
        total_seen=total_seen,
    )
