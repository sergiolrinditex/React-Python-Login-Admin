"""
Pydantic models for the 'mcp_agents' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Covers:
  - data/verification/mcp_agents/servers.json
  - data/verification/mcp_agents/agents.json

CHANGE from T003:
  - McpServerSeed: access_token now optional; new access_token_env field.
    Productive bundles use access_token_env; public servers may have neither.
    Synthetic bundles: access_token required with 'synthetic-' prefix.
  - AgentSeed: new fields agent_type, framework, parent_agent_name, subagent_topics.
    mcp_server_name is now optional (supervisor may not bind MCP directly).
    Cross-field validator: supervisor constraints and subagent constraints enforced.

SECURITY:
  - Productive servers: use access_token_env for servers requiring auth.
  - Public servers (e.g. docs-langchain): may omit both access_token and access_token_env.
  - Synthetic guard preserved via _require_synthetic_prefix.

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.seeds.schemas.admin_ai import _is_real_key, _require_synthetic_prefix


class McpServerSeed(BaseModel):
    """Seed record for an MCP server entry.

    Purpose: pre-register MCP servers for J105 MCP/agents journey.
    Supports both synthetic (dev) and productive bundles.

    Params:
      name            — unique server name (upsert key).
      endpoint_url    — HTTP endpoint for the MCP server.
      transport       — communication transport type.
      access_token    — plaintext token (synthetic bundles, 'synthetic-' prefix required).
      access_token_env — env var name holding the real token (productive bundles).
      is_active       — whether this server is enabled.
      allowed_tools   — list of tool names this server exposes.
      description     — optional human-readable description.

    NOTE: public servers (e.g. docs-langchain) may omit both access_token and
    access_token_env — the loader treats this as "no auth required".

    Errors: ValidationError if rules are violated.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., min_length=1, max_length=200, description="MCP server name (upsert key)."
    )
    endpoint_url: str = Field(..., description="HTTP/HTTPS endpoint.")
    transport: Literal["http", "https", "stdio"] = Field("http")
    access_token: str | None = Field(
        None, description="Plaintext token (synthetic, 'synthetic-' prefix)."
    )
    access_token_env: str | None = Field(
        None, description="Env var name for real token (productive)."
    )
    is_active: bool = Field(True)
    allowed_tools: list[str] = Field(default_factory=list)
    description: str | None = Field(None, max_length=500)

    @classmethod
    def validate_with_bundle_type(
        cls, data: dict[str, Any], bundle_type: str | None
    ) -> McpServerSeed:
        """Validate McpServerSeed with explicit bundle_type enforcement.

        Params:
          data        — raw dict from the fixture file.
          bundle_type — 'synthetic' or 'productive'. None raises ValueError.
        Returns: validated instance.
        Errors: ValueError on invariant violations.
        """
        if bundle_type is None:
            raise ValueError(
                "McpServerSeed: bundle_type must not be None. "
                "Pass bundle_type via validate_with_bundle_type()."
            )

        instance = cls.model_validate(data)

        if bundle_type == "synthetic":
            if not instance.access_token:
                raise ValueError(
                    "synthetic bundle: McpServerSeed.access_token is required."
                )
            _require_synthetic_prefix("access_token", instance.access_token)

        elif bundle_type == "productive":
            if instance.access_token and _is_real_key(instance.access_token):
                raise ValueError(
                    "productive bundle: McpServerSeed.access_token contains a plaintext real key. "
                    "Use access_token_env to reference an env var instead."
                )
            # Public servers may have neither token nor env var — allowed.

        else:
            raise ValueError(
                f"Unknown bundle_type: {bundle_type!r}. Expected 'synthetic' or 'productive'."
            )

        return instance


class McpServerListSeed(BaseModel):
    """Wrapper for a list of MCP server seeds."""

    model_config = ConfigDict(extra="forbid")

    servers: list[McpServerSeed]


class AgentSeed(BaseModel):
    """Seed record for an AI agent.

    Purpose: pre-create agents for J105 verification. Supports supervisor/subagent
    hierarchy with deepagents framework (P02-S08 implements the runtime).

    Params:
      name              — unique agent name (upsert key).
      description       — agent description shown in the UI.
      agent_type        — 'supervisor' or 'subagent'. Default: 'subagent'.
      framework         — runtime framework: 'deepagents', 'langchain', or 'custom'.
      mcp_server_name   — references an McpServerSeed.name (optional for supervisors).
      parent_agent_name — references the supervisor's name (required for subagents).
      subagent_topics   — routing topics for this subagent (None for supervisor).
      system_prompt     — system-level instruction for the agent.
      model_id          — model to use for this agent.
      is_active         — whether this agent is selectable.

    Cross-field invariants (enforced via model_validator):
      - supervisor: parent_agent_name must be None; subagent_topics must be None.
      - subagent: parent_agent_name must be non-null.

    Errors: ValidationError if cross-field invariants are violated.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200, description="Agent name (upsert key).")
    description: str = Field(..., min_length=1, max_length=500)
    agent_type: Literal["supervisor", "subagent"] = Field(
        "subagent", description="Agent role in the hierarchy."
    )
    framework: Literal["deepagents", "langchain", "custom"] = Field(
        "deepagents", description="Runtime framework for this agent."
    )
    mcp_server_name: str | None = Field(
        None, description="Parent MCP server name (optional for supervisors)."
    )
    parent_agent_name: str | None = Field(
        None, description="Supervisor agent name (required for subagents, None for supervisor)."
    )
    subagent_topics: list[str] | None = Field(
        None, description="Routing topic list (None for supervisor)."
    )
    system_prompt: str = Field(..., min_length=1)
    model_id: str = Field(..., description="LiteLLM model string.")
    is_active: bool = Field(True)

    @model_validator(mode="after")
    def _validate_hierarchy_invariants(self) -> AgentSeed:
        """Enforce supervisor/subagent cross-field constraints.

        Purpose: catch misconfigured agents early at fixture parse time.
        Rules:
          - supervisor: parent_agent_name=None, subagent_topics=None.
          - subagent: parent_agent_name non-null.
        """
        if self.agent_type == "supervisor":
            if self.parent_agent_name is not None:
                raise ValueError(
                    f"AgentSeed '{self.name}': supervisor agents must have parent_agent_name=None, "
                    f"got '{self.parent_agent_name}'."
                )
            if self.subagent_topics is not None:
                raise ValueError(
                    f"AgentSeed '{self.name}': supervisor agents must have subagent_topics=None, "
                    f"got a list with {len(self.subagent_topics)} topics."
                )
        elif self.agent_type == "subagent":
            if not self.parent_agent_name:
                raise ValueError(
                    f"AgentSeed '{self.name}': "
                    "subagent agents must have a non-null parent_agent_name."
                )
        return self


class AgentListSeed(BaseModel):
    """Wrapper for a list of agent seeds."""

    model_config = ConfigDict(extra="forbid")

    agents: list[AgentSeed]
