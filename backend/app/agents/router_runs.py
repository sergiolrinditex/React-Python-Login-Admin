"""
Hilo People — Agents HTTP handler: POST /agents/runs.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: FastAPI handler for POST /api/v1/agents/runs.

         This endpoint is admin-scoped (Sí admin per TECHNICAL_GUIDE §6.2)
         even though it lives outside /admin/ai/ (V1 design: only admins can
         trigger runs). The require_admin dependency enforces this.

         Rate-limited: 5 req/min/user via start_run_limiter (Redis sliding-window).

Key deps:
  - app.agents.service (start_agent_run, start_run_limiter)
  - app.agents.schemas (CreateAgentRunRequest, AgentRunCreatedOut)
  - app.agents.errors (AgentNotFoundError, AgentDisabledError, AgentRunFailedError)
  - app.security.permissions.require_admin
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.agents.errors import (
    AgentDisabledError,
    AgentNotFoundError,
    AgentRunFailedError,
)
from app.agents.schemas import AgentRunCreatedOut, CreateAgentRunRequest
from app.agents.service import start_agent_run as _svc_start, start_run_limiter
from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.security.permissions import require_admin

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_runs_router = APIRouter(tags=["agents"])


@_runs_router.post("/agents/runs", status_code=200)
async def start_run(
    request: Request,
    body: CreateAgentRunRequest,
    user_or_response: User | JSONResponse = Depends(require_admin),
    _rl: JSONResponse | None = Depends(start_run_limiter),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/agents/runs — trigger a single blocking agent smoke run.

    Admin-only (V1). Rate-limited to 5 req/min per IP.

    Args:
        request:          FastAPI Request.
        body:             Validated CreateAgentRunRequest.
        user_or_response: Admin User or 401/403 JSONResponse.
        _rl:              None on success; 429/503 from rate limiter.
        session:          SQLAlchemy Session.

    Returns:
        200 with {data: {run_id, status}, meta: {request_id}}.
        400 on payload validation. 401/403 on auth.
        404 if agent not found. 409 if agent disabled.
        502 if DeepAgents execution fails.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    if isinstance(_rl, JSONResponse):
        return _rl

    request_id = _get_request_id(request)
    ip = _get_client_ip(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "agents.router.start_run.start user_id=%s agent_id=%s "
            "input_len=%d request_id=%s",
            str(user.id), str(body.agent_id), len(body.input), request_id,
        )  # BEFORE

    try:
        result = _svc_start(
            session,
            agent_id=body.agent_id,
            input_text=body.input,
            actor_user_id=user.id,
            request_id=request_id,
            ip=ip,
        )
    except AgentNotFoundError:
        return _error_response(
            request_id=request_id, code="AGENT_NOT_FOUND",
            message="Agent not found.", http_status=404,
        )
    except AgentDisabledError:
        return _error_response(
            request_id=request_id, code="AGENT_DISABLED",
            message="Agent is disabled and cannot accept run requests.",
            http_status=409,
        )
    except AgentRunFailedError as exc:
        logger.error(
            "agents.router.start_run.failed user_id=%s agent_id=%s "
            "request_id=%s error=%s",
            str(user.id), str(body.agent_id), request_id, str(exc),
        )
        return _error_response(
            request_id=request_id, code="AGENT_RUN_FAILED",
            message="Agent run failed. Check server logs for details.",
            http_status=502,
        )
    except Exception as exc:
        logger.error(
            "agents.router.start_run.error user_id=%s agent_id=%s "
            "request_id=%s error=%s",
            str(user.id), str(body.agent_id), request_id, type(exc).__name__,
            exc_info=True,
        )
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Unexpected error starting agent run.", http_status=500,
        )

    out = AgentRunCreatedOut(
        run_id=result["run_id"],
        status=result["status"],
    ).model_dump(mode="json")

    if _VERBOSE:
        logger.debug(
            "agents.router.start_run.ok user_id=%s run_id=%s "
            "status=%s request_id=%s",
            str(user.id), str(result["run_id"]), result["status"], request_id,
        )  # AFTER

    return JSONResponse(content={"data": out, "meta": {"request_id": request_id}}, status_code=200)
