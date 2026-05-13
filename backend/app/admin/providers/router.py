"""
Hilo People — Admin AI providers HTTP router (handlers only).

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: FastAPI handlers for GET /api/v1/admin/ai/providers and
         POST /api/v1/admin/ai/providers. All business orchestration lives
         in providers/service.py and providers/repository.py; this module
         only wires HTTP → service → response envelope.

Key deps:
  - app.admin.providers.service (create_provider, create_provider_limiter)
  - app.admin.providers.repository (list_providers)
  - app.admin.providers.schemas (CreateProviderRequest, ProviderOut)
  - app.security.permissions.require_admin
  - app.security.encryption.EncryptionError
  - app.auth.routers._helpers (_error_response, _get_client_ip, _get_request_id)

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract
  - 01-non-negotiables.md §Logging (BEFORE/AFTER, no PII/credentials)

Decisions:
  - D-AE: Success responses build the envelope here ({data, meta:{request_id}}).
  - D-PERM2: require_admin returns JSONResponse on 403; we propagate early.
  - D-RL1: The rate limiter dependency is the singleton from service.py so
    its identity in the FastAPI dependency graph is stable across requests.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.admin.providers.repository import list_providers as _repo_list
from app.admin.providers.schemas import CreateProviderRequest, ProviderOut
from app.admin.providers.service import (
    create_provider as _svc_create,
    create_provider_limiter,
)
from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.security.encryption import EncryptionError
from app.security.permissions import require_admin

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

providers_router = APIRouter(tags=["admin-ai"])


@providers_router.get("/providers", status_code=200)
async def list_providers(
    request: Request,
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """GET /api/v1/admin/ai/providers — list all AI providers (admin only).

    Returns provider rows with credential metadata (has_credentials, auth_type,
    expires_at) but NEVER returns encrypted_secret or any raw credential value.

    Args:
        request:          FastAPI Request (X-Request-ID, client IP).
        user_or_response: Admin User on success; JSONResponse 401/403 on failure.
        session:          SQLAlchemy Session from get_db_session dependency.

    Returns:
        JSONResponse 200 with {"data": [...], "meta": {"request_id": "..."}}
        or 401/403 JSONResponse from require_admin.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "admin.providers.list.start user_id=%s request_id=%s",
            str(user.id),
            request_id,
        )  # BEFORE

    try:
        providers = _repo_list(session)
    except Exception as exc:
        logger.error(
            "admin.providers.list.error user_id=%s request_id=%s error=%s",
            str(user.id),
            request_id,
            type(exc).__name__,
            exc_info=True,
        )
        return _error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="Failed to list providers.",
            http_status=500,
        )

    out = [ProviderOut(**p).model_dump(mode="json") for p in providers]

    if _VERBOSE:
        logger.debug(
            "admin.providers.list.ok user_id=%s request_id=%s count=%d",
            str(user.id),
            request_id,
            len(out),
        )  # AFTER

    return JSONResponse(
        content={"data": out, "meta": {"request_id": request_id}},
        status_code=200,
    )


@providers_router.post("/providers", status_code=201)
async def create_provider(
    request: Request,
    body: CreateProviderRequest,
    user_or_response: User | JSONResponse = Depends(require_admin),
    _rl: JSONResponse | None = Depends(create_provider_limiter),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/admin/ai/providers — create a new AI provider (admin only).

    Delegates to service.create_provider, which encrypts credentials, commits
    or rolls back the transaction, and writes the audit row (D-S2).

    NEVER logs secret_plain, encrypted_secret, or any credential value.

    Args:
        request:          FastAPI Request.
        body:             Validated CreateProviderRequest payload.
        user_or_response: Admin User or JSONResponse 401/403 from require_admin.
        _rl:              None on success; JSONResponse 429/503 from rate limiter.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 201 with created provider (no credential values) or
        4xx/5xx error response.
    """
    # Propagate 401/403 from require_admin.
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    # Propagate 429/503 from rate limiter.
    if isinstance(_rl, JSONResponse):
        return _rl

    request_id = _get_request_id(request)
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "admin.providers.create.start user_id=%s provider_type=%s "
            "name_len=%d request_id=%s",
            str(user.id),
            body.provider_type,
            len(body.name),
            request_id,
        )  # BEFORE — credential fields intentionally omitted

    try:
        provider = _svc_create(
            session,
            provider_type=body.provider_type,
            name=body.name,
            base_url=body.base_url,
            auth_type=body.credentials.auth_type,
            secret_plain=body.credentials.secret_plain,
            refresh_token_plain=body.credentials.refresh_token_plain,
            expires_at=body.credentials.expires_at,
            created_by=user.id,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
    except EncryptionError:
        # Service already wrote audit (outcome=failure) and rolled back.
        return _error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="Failed to encrypt provider credentials.",
            http_status=500,
        )
    except Exception:
        # Service already wrote audit (outcome=failure) and rolled back.
        return _error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="Failed to create provider.",
            http_status=500,
        )

    out = ProviderOut(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        status=provider.status,
        created_by=provider.created_by,
        has_credentials=True,
        credential_auth_type=body.credentials.auth_type,
        expires_at=body.credentials.expires_at,
    ).model_dump(mode="json")

    if _VERBOSE:
        logger.debug(
            "admin.providers.create.ok user_id=%s provider_id=%s request_id=%s",
            str(user.id),
            str(provider.id),
            request_id,
        )  # AFTER

    return JSONResponse(
        content={"data": out, "meta": {"request_id": request_id}},
        status_code=201,
    )


# Public re-export hint for static analyzers; not strictly required.
__all__ = ["providers_router"]
