"""
FastAPI router for admin_ai feature — discover-models endpoint.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Endpoint:
  POST /providers/{provider_id}/discover-models
  (mounted in main.py under prefix /api/v1/admin/ai → full path:
   POST /api/v1/admin/ai/providers/{provider_id}/discover-models)

Acceptance:
  A1. Endpoint implemented in features/admin_ai/, mounted under /api/v1 prefix.
  A3. Returns { data: { added, existing, skipped, total_seen } } (§6.2 envelope).
  A4. Admin-only: 401 without auth, 403 with non-admin token (P00 stub via require_admin).
  A5. 404 when provider_id not found; 502 on upstream failure; 422 on malformed input.

Exception handlers registered on the router:
  - ProviderNotFoundError    → 404
  - UnsupportedProviderError → 422
  - MissingCredentialError   → 502
  - CryptoError              → 502
  - UpstreamProviderError    → 502

Logging (C1): handled entirely by service.py. The route layer logs nothing extra
to avoid double-logging; FastAPI exception handler logs error_class + details.

Dependencies:
  - fastapi 0.136.1
  - sqlalchemy.ext.asyncio.AsyncSession (via app.core.db.get_session)
  - app.core.security.require_admin (P00 stub auth guard)
  - app.features.admin_ai.service (use-case)
  - app.features.admin_ai.schemas (response model)

Source: task-pack P00-S02-T006 §7 step 9 + §6.4 mount strategy
HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import CryptoError, require_admin
from app.features.admin_ai import service
from app.features.admin_ai.provider_clients import UnsupportedProviderError, UpstreamProviderError
from app.features.admin_ai.schemas import DiscoverModelsResponse
from app.features.admin_ai.service import MissingCredentialError, ProviderNotFoundError

router = APIRouter(tags=["admin-ai"])


@router.post(
    "/providers/{provider_id}/discover-models",
    response_model=DiscoverModelsResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover models from an AI provider",
    description=(
        "Call the provider's model-list endpoint, reconcile results against "
        "the ai_models catalog, insert new rows with auto_discovered=True, and "
        "return a diff {added, existing, skipped, total_seen}. "
        "Admin-only (P00 stub: requires 'Bearer dev-admin-' token)."
    ),
)
async def discover_models(
    provider_id: uuid.UUID,
    _token: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> DiscoverModelsResponse:
    """POST /providers/{provider_id}/discover-models — main handler.

    Purpose: HTTP layer for the discover-models use case. Delegates to
    service.discover_models() and maps typed domain errors to HTTP status codes.

    Params:
      provider_id — UUID path param for the ai_providers row.
      _token      — validated admin token (from require_admin dependency; not used directly).
      session     — SQLAlchemy async session (from get_session dependency).
    Returns: DiscoverModelsResponse (§6.2 envelope: { data: DiscoverModelsData }).
    Raises:
      HTTP 404 — provider_id not found.
      HTTP 422 — unsupported provider_type (FastAPI also 422s bad UUIDs automatically).
      HTTP 502 — upstream provider call failed, no credential, or decrypt error.
    """
    try:
        data = await service.discover_models(session=session, provider_id=provider_id)
    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "provider_not_found",
                    "message": f"Provider {provider_id} not found.",
                }
            },
        ) from exc
    except UnsupportedProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "unsupported_provider_type",
                    "message": (
                        f"Provider type {exc.provider_type!r} is not supported. "
                        "Supported: gemini, openai, litellm."
                    ),
                }
            },
        ) from exc
    except (MissingCredentialError, CryptoError, UpstreamProviderError) as exc:
        # All three map to 502 — upstream/config issue, not caller error.
        msg = (
            exc.message
            if isinstance(exc, UpstreamProviderError)
            else str(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "upstream_provider_error",
                    "message": msg,
                }
            },
        ) from exc

    return DiscoverModelsResponse(data=data)
