"""
Hilo People — SQLAlchemy 2.x ORM models: MCP servers and tools.

Slice:  P02-S01-T001 — 0002_ai_chat_rag_mcp_agents migration
Phase:  P02 Core Features (the motor)
Purpose: Defines ORM models for the MCP (Model Context Protocol) server and
         tool registry subsystem: McpServer, McpCredential, McpTool,
         McpResource, McpPrompt.

Bounded context: mcp-servers — configuration of external MCP servers, their
authentication credentials, and the catalog of tools/resources/prompts
discovered from each server. Agent-to-tool bindings and runtime invocation
tracking live in agents.py.

Mapped tables (all created by migration 0002_ai_chat_rag_mcp_agents.py):
  - mcp_servers     (FK -> users for created_by)
  - mcp_credentials (FK -> mcp_servers ON DELETE CASCADE)
  - mcp_tools       (FK -> mcp_servers ON DELETE CASCADE)
  - mcp_resources   (FK -> mcp_servers ON DELETE CASCADE)
  - mcp_prompts     (FK -> mcp_servers ON DELETE CASCADE)

Key deps:
  - app.db.base           — Base (DeclarativeBase with naming_convention)
  - sqlalchemy==2.0.49    (Mapped, mapped_column, JSONB)
  - sqlalchemy.dialects.postgresql — UUID, JSONB

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3#mcp-agents
  - docs/source-of-truth/instrucciones.md §3.1#mcp-agents
  - P02-S01-T001 task pack §C.4, §I.1, §D.2

Decisions implemented:
  - Split from mcp_agents.py: 10 MCP+Agent models would exceed ~300 LOC cap.
    Split per bounded sub-context: mcp.py (server/catalog) + agents.py (runtime).
    Documented as WRITE_SET_DRIFT minor (write_set is backend/app/db/models/**).
  - encrypted_secret / encrypted_refresh_token: NEVER log values (§10.5).
  - stdio transport type is blocked in production (enforced at app layer P02-S07).
  - Tools enter as disabled (enabled=False) and require_approval=True by default
    per instrucciones.md §3.1#mcp-agents security policy.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ---------------------------------------------------------------------------
# McpServer — configuration for an external MCP server
# ---------------------------------------------------------------------------
class McpServer(Base):
    """ORM model for the `mcp_servers` table.

    Represents a configured MCP server that can be connected to for tool,
    resource, and prompt discovery. transport_type is 'http', 'sse', or
    'stdio' (stdio prohibited in external prod — enforced at app layer).

    status lifecycle: 'draft' → 'active' → 'inactive'.
    last_sync_at tracks the most recent discovery/health-check timestamp.

    Table: mcp_servers
    PK: id UUID (gen_random_uuid())
    FK: created_by -> users.id (nullable; no CASCADE — informational)

    Refs: §10.3#mcp-agents, instrucciones.md §3.1#mcp-agents
    """

    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Human-readable server name",
    )
    transport_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Transport: 'http' | 'sse' | 'stdio' (stdio prohibited externally)",
    )
    endpoint_url: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="HTTP/SSE endpoint URL; NULL for stdio servers",
    )
    command: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="CLI command for stdio servers (internal only)",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default=sa.text("'draft'"),
        comment="Lifecycle status: 'draft' | 'active' | 'inactive'",
    )
    last_sync_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Timestamp of last successful tool/resource discovery",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", name="mcp_servers_created_by_fkey"),
        nullable=True,
        comment="FK -> users.id (nullable; no CASCADE — informational reference to admin)",
    )


# ---------------------------------------------------------------------------
# McpCredential — encrypted auth for an MCP server
# ---------------------------------------------------------------------------
class McpCredential(Base):
    """ORM model for the `mcp_credentials` table.

    Stores Fernet-encrypted authentication credentials for an MCP server.
    encrypted_secret and encrypted_refresh_token MUST NEVER be logged.

    Table: mcp_credentials
    PK: id UUID (gen_random_uuid())
    FK: server_id -> mcp_servers.id ON DELETE CASCADE

    Refs: §10.3#mcp-agents, 01-non-negotiables.md §Security (Fernet encryption)
    """

    __tablename__ = "mcp_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "mcp_servers.id",
            ondelete="CASCADE",
            name="mcp_credentials_server_id_fkey",
        ),
        nullable=False,
        comment="FK -> mcp_servers.id ON DELETE CASCADE",
    )
    auth_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Credential kind: 'api_key' | 'oauth2' | 'bearer' | 'none'",
    )
    encrypted_secret: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Fernet-encrypted secret — NEVER log this value (§10.5)",
    )
    encrypted_refresh_token: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Fernet-encrypted OAuth2 refresh token — NEVER log (§10.5)",
    )
    expires_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="OAuth2 token expiry; NULL for non-expiring API keys",
    )


# ---------------------------------------------------------------------------
# McpTool — a tool exposed by an MCP server
# ---------------------------------------------------------------------------
class McpTool(Base):
    """ORM model for the `mcp_tools` table.

    Discovered tools from an MCP server. Tools enter as disabled
    (enabled=False) and require_approval=True by default per security policy.
    risk_level informs approval UI: 'low' | 'medium' | 'high' | 'critical'.

    input_schema and output_schema store JSON Schema objects describing
    the tool's parameters and return type (MCP spec §3.1).

    Table: mcp_tools
    PK: id UUID (gen_random_uuid())
    FK: server_id -> mcp_servers.id ON DELETE CASCADE

    Refs: §10.3#mcp-agents, instrucciones.md §3.1#mcp-agents (tools require approval)
    """

    __tablename__ = "mcp_tools"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "mcp_servers.id",
            ondelete="CASCADE",
            name="mcp_tools_server_id_fkey",
        ),
        nullable=False,
        comment="FK -> mcp_servers.id ON DELETE CASCADE",
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Tool name as declared by the MCP server",
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Human-readable tool description from MCP discovery",
    )
    input_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="JSON Schema of tool input parameters",
    )
    output_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="JSON Schema of tool output",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="False by default — must be explicitly enabled by admin",
    )
    requires_approval: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="True = human approval required before each invocation",
    )
    risk_level: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default=sa.text("'medium'"),
        comment="Risk classification: 'low' | 'medium' | 'high' | 'critical'",
    )


# ---------------------------------------------------------------------------
# McpResource — a resource exposed by an MCP server
# ---------------------------------------------------------------------------
class McpResource(Base):
    """ORM model for the `mcp_resources` table.

    Resources are read-only data sources exposed by an MCP server (e.g. file
    contents, API data). URI is the MCP resource identifier.

    Table: mcp_resources
    PK: id UUID (gen_random_uuid())
    FK: server_id -> mcp_servers.id ON DELETE CASCADE

    Refs: §10.3#mcp-agents
    """

    __tablename__ = "mcp_resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "mcp_servers.id",
            ondelete="CASCADE",
            name="mcp_resources_server_id_fkey",
        ),
        nullable=False,
        comment="FK -> mcp_servers.id ON DELETE CASCADE",
    )
    uri: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="MCP resource URI (e.g. 'file:///path/to/resource')",
    )
    name: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Human-readable resource name",
    )
    mime_type: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="MIME type of the resource content (e.g. 'text/plain')",
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Human-readable resource description",
    )


# ---------------------------------------------------------------------------
# McpPrompt — a prompt template exposed by an MCP server
# ---------------------------------------------------------------------------
class McpPrompt(Base):
    """ORM model for the `mcp_prompts` table.

    Prompt templates exposed by an MCP server that agents can use to
    construct standardized LLM requests. arguments_schema describes the
    template's required parameters.

    Table: mcp_prompts
    PK: id UUID (gen_random_uuid())
    FK: server_id -> mcp_servers.id ON DELETE CASCADE

    Refs: §10.3#mcp-agents
    """

    __tablename__ = "mcp_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "mcp_servers.id",
            ondelete="CASCADE",
            name="mcp_prompts_server_id_fkey",
        ),
        nullable=False,
        comment="FK -> mcp_servers.id ON DELETE CASCADE",
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Prompt template name as declared by the MCP server",
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Human-readable description of the prompt template",
    )
    arguments_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="JSON Schema of the prompt's required arguments",
    )
