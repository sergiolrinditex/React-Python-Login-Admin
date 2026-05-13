"""
Hilo People — MCP HTTP handlers: servers (GET list, POST register, POST sync).

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: FastAPI handlers for:
           - GET  /api/v1/admin/ai/mcp/servers
           - POST /api/v1/admin/ai/mcp/servers
           - POST /api/v1/admin/ai/mcp/servers/{server_id}/sync

         Extracted from router.py for file-size compliance.
         All business orchestration in service_register.py / service_sync.py.

Key deps:
  - app.mcp.service (register_server, sync_server, rate limiters)
  - app.mcp.repository (list_servers)
  - app.mcp.schemas (CreateServerRequest, ServerOut, SyncResponse)
  - app.mcp.errors (McpServerNotFoundError, McpServerUnreachableError)
  - app.security.permissions.require_admin
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.mcp.errors import McpServerNotFoundError, McpServerUnreachableError
from app.mcp.repository import list_servers as _repo_list_servers
from app.mcp.schemas import CreateServerRequest, ServerOut, SyncResponse
from app.mcp.service import (
    register_server as _svc_register,
    register_server_limiter,
    sync_server as _svc_sync,
    sync_server_limiter,
)
from app.security.encryption import EncryptionError
from app.security.permissions import require_admin

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_servers_router = APIRouter(tags=["admin-ai"])


@_servers_router.get("/servers", status_code=200)
async def list_mcp_servers(
    request: Request,
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """GET /api/v1/admin/ai/mcp/servers — list all registered MCP servers.

    Args:
        request:          FastAPI Request.
        user_or_response: Admin User or 401/403 JSONResponse.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 200 with {data: [...], meta: {request_id}}.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "mcp.router.list_servers.start user_id=%s request_id=%s",
            str(user.id), request_id,
        )  # BEFORE

    try:
        servers = _repo_list_servers(session)
    except Exception as exc:
        logger.error(
            "mcp.router.list_servers.error user_id=%s request_id=%s error=%s",
            str(user.id), request_id, type(exc).__name__, exc_info=True,
        )
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Failed to list MCP servers.", http_status=500,
        )

    out = [ServerOut(**s).model_dump(mode="json") for s in servers]

    if _VERBOSE:
        logger.debug(
            "mcp.router.list_servers.ok user_id=%s request_id=%s count=%d",
            str(user.id), request_id, len(out),
        )  # AFTER

    return JSONResponse(content={"data": out, "meta": {"request_id": request_id}}, status_code=200)


@_servers_router.post("/servers", status_code=201)
async def create_mcp_server(
    request: Request,
    body: CreateServerRequest,
    user_or_response: User | JSONResponse = Depends(require_admin),
    _rl: JSONResponse | None = Depends(register_server_limiter),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/admin/ai/mcp/servers — register a new MCP server.

    Args:
        request:          FastAPI Request.
        body:             Validated CreateServerRequest.
        user_or_response: Admin User or 401/403.
        _rl:              None on success; 429/503 from rate limiter.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 201 with created server or 4xx/5xx.
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
            "mcp.router.create_server.start user_id=%s transport=%s "
            "auth_type=%s request_id=%s",
            str(user.id), body.transport, body.auth.type, request_id,
        )  # BEFORE

    try:
        server = _svc_register(
            session, name=body.name, transport=body.transport,
            endpoint=body.endpoint, auth_type=body.auth.type,
            secret_plain=body.auth.secret, refresh_token_plain=body.auth.refresh_token,
            created_by=user.id, request_id=request_id, ip=ip,
        )
    except ValueError as exc:
        logger.warning(
            "mcp.router.create_server.allowlist_denied user_id=%s request_id=%s",
            str(user.id), request_id,
        )
        return _error_response(
            request_id=request_id, code="MCP_ENDPOINT_NOT_ALLOWED",
            message=str(exc), http_status=400,
        )
    except EncryptionError:
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Failed to encrypt server credentials.", http_status=500,
        )
    except Exception:
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Failed to register MCP server.", http_status=500,
        )

    out = ServerOut(
        id=server.id, name=server.name, transport=server.transport_type,
        endpoint=server.endpoint_url, status=server.status,
        last_sync_at=server.last_sync_at, created_by=server.created_by,
        has_credential=(body.auth.type != "none"),
        auth_type=body.auth.type if body.auth.type != "none" else None,
    ).model_dump(mode="json")

    if _VERBOSE:
        logger.debug(
            "mcp.router.create_server.ok user_id=%s server_id=%s request_id=%s",
            str(user.id), str(server.id), request_id,
        )  # AFTER

    return JSONResponse(content={"data": out, "meta": {"request_id": request_id}}, status_code=201)


@_servers_router.post("/servers/{server_id}/sync", status_code=200)
async def sync_mcp_server(
    server_id: uuid.UUID,
    request: Request,
    user_or_response: User | JSONResponse = Depends(require_admin),
    _rl: JSONResponse | None = Depends(sync_server_limiter),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/admin/ai/mcp/servers/{server_id}/sync — discover tools.

    Args:
        server_id:        UUID of the server to sync.
        request:          FastAPI Request.
        user_or_response: Admin User or 401/403.
        _rl:              None on success; 429/503 from rate limiter.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 200 with {data: {tools_count, status}, meta: {request_id}}.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response
    if isinstance(_rl, JSONResponse):
        return _rl

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "mcp.router.sync_server.start user_id=%s server_id=%s request_id=%s",
            str(user.id), str(server_id), request_id,
        )  # BEFORE

    try:
        result = _svc_sync(session, server_id=server_id,
                           actor_user_id=user.id, request_id=request_id)
    except McpServerNotFoundError:
        return _error_response(
            request_id=request_id, code="MCP_SERVER_NOT_FOUND",
            message="MCP server not found.", http_status=404,
        )
    except McpServerUnreachableError as exc:
        logger.error(
            "mcp.router.sync_server.unreachable server_id=%s request_id=%s error=%s",
            str(server_id), request_id, str(exc),
        )
        return _error_response(
            request_id=request_id, code="MCP_SERVER_UNREACHABLE",
            message="Cannot connect to the MCP server. Check the endpoint and credentials.",
            http_status=502,
        )
    except Exception as exc:
        logger.error(
            "mcp.router.sync_server.error server_id=%s request_id=%s error=%s",
            str(server_id), request_id, type(exc).__name__, exc_info=True,
        )
        return _error_response(
            request_id=request_id, code="INTERNAL_ERROR",
            message="Failed to sync MCP server.", http_status=500,
        )

    out = SyncResponse(**result).model_dump(mode="json")

    if _VERBOSE:
        logger.debug(
            "mcp.router.sync_server.ok server_id=%s tools=%d request_id=%s",
            str(server_id), result["tools_count"], request_id,
        )  # AFTER

    return JSONResponse(content={"data": out, "meta": {"request_id": request_id}}, status_code=200)
