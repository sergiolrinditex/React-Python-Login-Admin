"""
Hilo People — Agents HTTP handlers: GET list and PATCH tool bindings.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: FastAPI handlers for:
           - GET  /api/v1/admin/ai/agents
           - PATCH /api/v1/admin/ai/agents/{agent_id}/tools

         Both endpoints are admin-scoped (require_admin).
         Extracted from router.py for file-size compliance.

Key deps:
  - app.agents.service (list_agents, bind_tools)
  - app.agents.schemas (AgentOut, PatchAgentToolsRequest)
  - app.agents.errors (AgentNotFoundError, AgentToolNotFoundError,
                       AgentToolNotApprovedError)
  - app.security.permissions.require_admin
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.agents.errors import (
    AgentNotFoundError,
    AgentToolNotApprovedError,
    AgentToolNotFoundError,
)
from app.agents.schemas import AgentOut, PatchAgentToolsRequest
from app.agents.service import bind_tools as _svc_bind, list_agents as _svc_list
from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.security.permissions import require_admin

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_agents_router = APIRouter(tags=["admin-ai"])


@_agents_router.get("/agents", status_code=200)
async def list_agents(
    request: Request,
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """GET /api/v1/admin/ai/agents — list all agents with bound tool details.

    Args:
        request:          FastAPI Request.
        user_or_response: Admin User or 401/403 JSONResponse.
        session:          SQLAlchemy Session.

    Returns:
        200 with {data: [Agent...], meta: {request_id}}.
        401 if no/invalid auth. 403 if non-admin.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "agents.router.list_agents.start user_id=%s request_id=%s",
            str(user.id), request_id,
        )  # BEFORE

    try:
        agents = _svc_list(session, request_id=request_id)
    except Exception as exc:
        logger.error(
            "agents.router.list_agents.error user_id=%s request_id=%s error=%s",
            str(user.id), request_id, type(exc).__name__, exc_info=True,
        )
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Failed to list agents.", http_status=500,
        )

    out = [AgentOut(**a).model_dump(mode="json") for a in agents]

    if _VERBOSE:
        logger.debug(
            "agents.router.list_agents.ok user_id=%s count=%d request_id=%s",
            str(user.id), len(out), request_id,
        )  # AFTER

    return JSONResponse(content={"data": out, "meta": {"request_id": request_id}}, status_code=200)


@_agents_router.patch("/agents/{agent_id}/tools", status_code=200)
async def patch_agent_tools(
    agent_id: uuid.UUID,
    request: Request,
    body: PatchAgentToolsRequest,
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """PATCH /api/v1/admin/ai/agents/{agent_id}/tools — set-replace tool bindings.

    Args:
        agent_id:         UUID of the agent to update.
        request:          FastAPI Request.
        body:             Validated PatchAgentToolsRequest.
        user_or_response: Admin User or 401/403.
        session:          SQLAlchemy Session.

    Returns:
        200 with {data: Agent, meta: {request_id}}.
        400 on invalid tool_ids. 401/403 on auth. 404 if agent not found.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "agents.router.patch_tools.start user_id=%s agent_id=%s "
            "tool_count=%d request_id=%s",
            str(user.id), str(agent_id), len(body.tool_ids), request_id,
        )  # BEFORE

    try:
        updated = _svc_bind(
            session,
            agent_id=agent_id,
            tool_ids=body.tool_ids,
            actor_user_id=user.id,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
    except AgentNotFoundError:
        return _error_response(
            request_id=request_id, code="AGENT_NOT_FOUND",
            message="Agent not found.", http_status=404,
        )
    except AgentToolNotFoundError as exc:
        return _error_response(
            request_id=request_id, code="AGENT_TOOL_NOT_FOUND",
            message=f"Tool not found: {exc.offending_id}",
            http_status=400, field="tool_ids",
        )
    except AgentToolNotApprovedError as exc:
        return _error_response(
            request_id=request_id, code="AGENT_TOOL_NOT_APPROVED",
            message=f"Tool is not approved (enabled=false): {exc.offending_id}",
            http_status=400, field="tool_ids",
        )
    except Exception as exc:
        logger.error(
            "agents.router.patch_tools.error user_id=%s agent_id=%s "
            "request_id=%s error=%s",
            str(user.id), str(agent_id), request_id, type(exc).__name__, exc_info=True,
        )
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Failed to update agent tool bindings.", http_status=500,
        )

    out = AgentOut(**updated).model_dump(mode="json")

    if _VERBOSE:
        logger.debug(
            "agents.router.patch_tools.ok user_id=%s agent_id=%s request_id=%s",
            str(user.id), str(agent_id), request_id,
        )  # AFTER

    return JSONResponse(content={"data": out, "meta": {"request_id": request_id}}, status_code=200)
