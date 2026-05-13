"""
Hilo People — Admin AI model catalog HTTP router (handlers only).

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: FastAPI handlers for GET /api/v1/admin/ai/models and
         PATCH /api/v1/admin/ai/models/{model_id}. Orchestration lives in
         model_catalog/service.py; this module only wires HTTP → service.

Key deps:
  - app.admin.model_catalog.service.patch_model
  - app.admin.model_catalog.repository.list_models
  - app.admin.model_catalog.schemas (ModelOut, UpdateModelRequest)
  - app.security.permissions.require_admin
  - app.auth.routers._helpers (_error_response, _get_client_ip, _get_request_id)

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract (GET/PATCH /models)

Decisions:
  - D-PATCH1: both fields None → 400 AI_MODEL_PAYLOAD_INVALID (not 422).
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.admin.model_catalog.repository import list_models as _repo_list
from app.admin.model_catalog.schemas import ModelOut, UpdateModelRequest
from app.admin.model_catalog.service import patch_model as _svc_patch
from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.security.permissions import require_admin

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

models_router = APIRouter(tags=["admin-ai"])


@models_router.get("/models", status_code=200)
async def list_models(
    request: Request,
    provider_id: uuid.UUID | None = Query(
        default=None, description="Filter by provider UUID"
    ),
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """GET /api/v1/admin/ai/models — list AI models (admin only).

    Args:
        request:          FastAPI Request.
        provider_id:      Optional UUID filter query param.
        user_or_response: Admin User or JSONResponse 401/403.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 200 with {"data": [...], "meta": {"request_id": "..."}}.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "admin.models.list.start user_id=%s provider_filter=%s request_id=%s",
            str(user.id),
            str(provider_id) if provider_id else "none",
            request_id,
        )  # BEFORE

    try:
        models = _repo_list(session, provider_id)
    except Exception as exc:
        logger.error(
            "admin.models.list.error user_id=%s request_id=%s error=%s",
            str(user.id),
            request_id,
            type(exc).__name__,
            exc_info=True,
        )
        return _error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="Failed to list models.",
            http_status=500,
        )

    out = [ModelOut.model_validate(m).model_dump(mode="json") for m in models]

    if _VERBOSE:
        logger.debug(
            "admin.models.list.ok user_id=%s request_id=%s count=%d",
            str(user.id),
            request_id,
            len(out),
        )  # AFTER

    return JSONResponse(
        content={"data": out, "meta": {"request_id": request_id}},
        status_code=200,
    )


@models_router.patch("/models/{model_id}", status_code=200)
async def patch_model(
    model_id: uuid.UUID,
    request: Request,
    body: UpdateModelRequest,
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """PATCH /api/v1/admin/ai/models/{model_id} — update a model (admin only).

    Args:
        model_id:         Target model UUID (path).
        request:          FastAPI Request.
        body:             UpdateModelRequest payload.
        user_or_response: Admin User or JSONResponse 401/403.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 200 with updated model data, or 4xx error envelope.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "admin.models.patch.start user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )  # BEFORE

    # D-PATCH1: At least one field must be provided.
    if body.enabled is None and body.is_default is None:
        logger.warning(
            "admin.models.patch.empty_payload user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code="AI_MODEL_PAYLOAD_INVALID",
            message="At least one of 'enabled' or 'is_default' must be provided.",
            http_status=400,
        )

    try:
        model = _svc_patch(
            session,
            actor_user_id=user.id,
            model_id=model_id,
            enabled=body.enabled,
            is_default=body.is_default,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
    except Exception:
        return _error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="Failed to update model.",
            http_status=500,
        )

    if model is None:
        logger.warning(
            "admin.models.patch.not_found user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code="AI_MODEL_NOT_FOUND",
            message="Model not found.",
            http_status=404,
        )

    out = ModelOut.model_validate(model).model_dump(mode="json")

    if _VERBOSE:
        logger.debug(
            "admin.models.patch.ok user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )  # AFTER

    return JSONResponse(
        content={"data": out, "meta": {"request_id": request_id}},
        status_code=200,
    )


__all__ = ["models_router"]
