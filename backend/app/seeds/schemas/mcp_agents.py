"""
Pydantic models for the 'mcp_agents' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Covers:
  - data/verification/mcp_agents/servers.json
  - data/verification/mcp_agents/agents.json

SECURITY: mcp_token fields MUST be prefixed 'synthetic-' (same guard as admin_ai).

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.seeds.schemas.admin_ai import _require_synthetic_prefix


class McpServerSeed(BaseModel):
    """Seed record for an MCP server entry.

    Purpose: pre-register the sandbox MCP server for J105 MCP/agents journey.
    Params:
      name           — unique server name (upsert key).
      endpoint_url   — HTTP endpoint for the MCP server.
      transport      — communication transport type.
      access_token   — MUST start with 'synthetic-'.
      is_active      — whether this server is enabled.
      allowed_tools  — list of tool names this server exposes.
    Errors: ValidationError if access_token is missing or not synthetic.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., min_length=1, max_length=200, description="MCP server name (upsert key)."
    )
    endpoint_url: str = Field(..., description="HTTP/HTTPS endpoint.")
    transport: Literal["http", "https", "stdio"] = Field("http")
    access_token: str = Field(..., description="Must start with 'synthetic-'.")
    is_active: bool = Field(True)
    allowed_tools: list[str] = Field(default_factory=list)
    description: str | None = Field(None, max_length=500)

    @field_validator("access_token")
    @classmethod
    def validate_synthetic_token(cls, v: str) -> str:
        """Enforce synthetic- prefix for access_token."""
        return _require_synthetic_prefix("access_token", v)


class McpServerListSeed(BaseModel):
    """Wrapper for a list of MCP server seeds."""

    model_config = ConfigDict(extra="forbid")

    servers: list[McpServerSeed]


class AgentSeed(BaseModel):
    """Seed record for an AI agent.

    Purpose: pre-create the 'people_helper' agent for J105 verification.
    Params:
      name           — unique agent name (upsert key).
      description    — agent description shown in the UI.
      mcp_server_name — references an McpServerSeed.name.
      system_prompt  — system-level instruction for the agent (plain text).
      model_id       — model to use for this agent.
      is_active      — whether this agent is selectable.
    Errors: ValidationError if required fields are missing.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200, description="Agent name (upsert key).")
    description: str = Field(..., min_length=1, max_length=500)
    mcp_server_name: str = Field(..., description="Parent MCP server name.")
    system_prompt: str = Field(..., min_length=1)
    model_id: str = Field(..., description="LiteLLM model string.")
    is_active: bool = Field(True)


class AgentListSeed(BaseModel):
    """Wrapper for a list of agent seeds."""

    model_config = ConfigDict(extra="forbid")

    agents: list[AgentSeed]
