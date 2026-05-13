"""
Hilo People — MCP HTTP handlers: tools (PATCH tool).

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: FastAPI handler for PATCH /api/v1/admin/ai/mcp/tools/{tool_id}.
         Extracted from router.py for file-size compliance.

Key deps:
  - app.mcp.service (update_mcp_tool)
  - app.mcp.schemas (PatchToolRequest, ToolOut)
  - app.mcp.errors (McpToolNotFoundError)
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.routers._helpers import _error_response, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.mcp.errors import McpToolNotFoundError
from app.mcp.schemas import PatchToolRequest, ToolOut
from app.mcp.service import update_mcp_tool as _svc_update_tool
from app.security.permissions import require_admin

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_tools_router = APIRouter(tags=["admin-ai"])


@_tools_router.patch("/tools/{tool_id}", status_code=200)
async def patch_mcp_tool(
    tool_id: uuid.UUID,
    request: Request,
    body: PatchToolRequest,
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """PATCH /api/v1/admin/ai/mcp/tools/{tool_id} — update tool admin fields.

    At least one of enabled, requires_approval, risk_level must be provided.
    Only provided fields are updated (PATCH semantics).

    Args:
        tool_id:          UUID of the tool to update.
        request:          FastAPI Request.
        body:             PatchToolRequest (all fields optional).
        user_or_response: Admin User or 401/403.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 200 with updated ToolOut, 400 if no fields, 404 if not found.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "mcp.router.patch_tool.start user_id=%s tool_id=%s request_id=%s",
            str(user.id), str(tool_id), request_id,
        )  # BEFORE

    if body.enabled is None and body.requires_approval is None and body.risk_level is None:
        return _error_response(
            request_id=request_id, code="MCP_TOOL_PAYLOAD_INVALID",
            message="At least one of enabled, requires_approval, or risk_level must be provided.",
            http_status=400,
        )

    try:
        tool = _svc_update_tool(
            session, tool_id=tool_id, enabled=body.enabled,
            requires_approval=body.requires_approval, risk_level=body.risk_level,
            actor_user_id=user.id, request_id=request_id,
        )
    except McpToolNotFoundError:
        return _error_response(
            request_id=request_id, code="MCP_TOOL_NOT_FOUND",
            message="MCP tool not found.", http_status=404,
        )
    except Exception as exc:
        logger.error(
            "mcp.router.patch_tool.error tool_id=%s request_id=%s error=%s",
            str(tool_id), request_id, type(exc).__name__, exc_info=True,
        )
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Failed to update MCP tool.", http_status=500,
        )

    out = ToolOut(
        id=tool.id, server_id=tool.server_id, name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema or {}, output_schema=tool.output_schema or {},
        enabled=tool.enabled, requires_approval=tool.requires_approval,
        risk_level=tool.risk_level,
    ).model_dump(mode="json")

    if _VERBOSE:
        logger.debug(
            "mcp.router.patch_tool.ok tool_id=%s request_id=%s",
            str(tool_id), request_id,
        )  # AFTER

    return JSONResponse(content={"data": out, "meta": {"request_id": request_id}}, status_code=200)
