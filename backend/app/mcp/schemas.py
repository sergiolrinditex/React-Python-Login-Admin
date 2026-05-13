"""
Hilo People — MCP server and tool Pydantic v2 schemas.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Request/response schemas for 4 MCP admin endpoints:
           - CreateServerRequest  (POST /mcp/servers)
           - ServerOut            (GET/POST /mcp/servers)
           - SyncResponse         (POST /mcp/servers/{id}/sync)
           - PatchToolRequest     (PATCH /mcp/tools/{id})
           - ToolOut              (PATCH /mcp/tools/{id})

Business rule enforced here (instrucciones.md §3.1#mcp-agents line 99):
  - transport must be 'http' or 'sse' — 'stdio' rejected with Pydantic 422.

Key deps:
  - pydantic v2 (BaseModel, ConfigDict, Field, model_validator, field_validator)

Source refs:
  - task pack P02-S07-T001 §Schema DB, §Endpoints
  - instrucciones.md §3.1#mcp-agents (transport allowlist, defaults)
  - TECHNICAL_GUIDE §6.2#mcp
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Auth sub-schema for server credential (POST /mcp/servers body)
# ---------------------------------------------------------------------------

class ServerAuthInput(BaseModel):
    """Credential payload embedded in CreateServerRequest.

    auth_type='none' means no credential is needed (public endpoint).
    Other types require a non-empty secret value.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["none", "api_key", "bearer", "oauth2"] = Field(
        description="Authentication kind for this MCP server."
    )
    secret: Optional[str] = Field(
        default=None,
        description="Raw secret (API key, bearer token, OAuth client secret). "
                    "Never stored in plaintext — encrypted with Fernet before persistence.",
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description="OAuth2 refresh token (encrypted before persistence).",
    )


# ---------------------------------------------------------------------------
# POST /mcp/servers — request
# ---------------------------------------------------------------------------

class CreateServerRequest(BaseModel):
    """Request body for POST /api/v1/admin/ai/mcp/servers.

    transport is strictly 'http' or 'sse'. 'stdio' is rejected here per
    instrucciones.md §3.1#mcp-agents line 99: stdio disabled for external
    production servers.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200, description="Human-readable server name.")
    transport: Literal["http", "sse"] = Field(
        description="Transport type. 'stdio' is not permitted for external servers."
    )
    endpoint: str = Field(
        min_length=1,
        max_length=2000,
        description="HTTP/SSE endpoint URL (e.g. https://mcp.example.com/mcp).",
    )
    auth: ServerAuthInput = Field(
        description="Authentication credentials for this server."
    )


# ---------------------------------------------------------------------------
# GET/POST /mcp/servers — response
# ---------------------------------------------------------------------------

class ServerOut(BaseModel):
    """Response shape for one MCP server row.

    Credentials are NEVER included in the response. Only metadata is returned.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    name: str
    transport: str
    endpoint: Optional[str] = None
    status: str
    last_sync_at: Optional[Any] = None
    created_by: Optional[uuid.UUID] = None
    has_credential: bool = False
    auth_type: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /mcp/servers/{id}/sync — response
# ---------------------------------------------------------------------------

class SyncResponse(BaseModel):
    """Response shape for sync operation."""

    model_config = ConfigDict(extra="forbid")

    tools_count: int
    resources_count: int
    prompts_count: int
    status: str


# ---------------------------------------------------------------------------
# PATCH /mcp/tools/{id} — request
# ---------------------------------------------------------------------------

class PatchToolRequest(BaseModel):
    """Request body for PATCH /api/v1/admin/ai/mcp/tools/{id}.

    At least one field must be provided (validated in router).
    All fields are optional; only provided fields are updated (PATCH semantics).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: Optional[bool] = Field(default=None, description="Enable or disable the tool.")
    requires_approval: Optional[bool] = Field(
        default=None,
        description="Whether human approval is required before invoking this tool.",
    )
    risk_level: Optional[Literal["low", "medium", "high", "critical"]] = Field(
        default=None,
        description="Risk classification for admin approval UI.",
    )


# ---------------------------------------------------------------------------
# PATCH /mcp/tools/{id} — response
# ---------------------------------------------------------------------------

class ToolOut(BaseModel):
    """Response shape for one MCP tool row."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    server_id: uuid.UUID
    name: str
    description: Optional[str] = None
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    enabled: bool
    requires_approval: bool
    risk_level: str
