"""
Hilo People — SQLAlchemy 2.x ORM models: Agents and MCP runtime.

Slice:  P02-S01-T001 — 0002_ai_chat_rag_mcp_agents migration
Phase:  P02 Core Features (the motor)
Purpose: Defines ORM models for the autonomous agent runtime subsystem:
         Agent, McpAgentBinding, AgentRun, McpToolInvocation, McpApproval.

Bounded context: agents-runtime — agent definitions, tool binding catalog,
run tracking, per-invocation audit trail, and human approval workflow for
write-risk tools.

Mapped tables (all created by migration 0002_ai_chat_rag_mcp_agents.py):
  - agents              (no FK — root entity)
  - mcp_agent_bindings  (FK -> agents + mcp_tools; composite PK)
  - agent_runs          (FK -> agents + users ON DELETE SET NULL)
  - mcp_tool_invocations (FK -> mcp_tools + agent_runs)
  - mcp_approvals       (FK -> mcp_tool_invocations + users)

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
    agents.py contains agent runtime (5 models); mcp.py contains server catalog (5 models).
    WRITE_SET_DRIFT minor (backend/app/db/models/**).
  - agent_runs.agent_id / user_id: ON DELETE SET NULL (audit history preserved).
  - mcp_tool_invocations: every invocation auditado per instrucciones.md §3.1#mcp-agents.
  - mcp_approvals: records both requester and approver for GDPR-compliant audit trail.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ---------------------------------------------------------------------------
# Agent — an autonomous AI agent configuration
# ---------------------------------------------------------------------------
class Agent(Base):
    """ORM model for the `agents` table.

    Defines a configured autonomous agent with its tool bindings and
    runtime configuration. config stores agent-specific settings (e.g.
    system prompt override, max steps, memory strategy).

    enabled=False means the agent cannot be triggered by users.

    Table: agents
    PK: id UUID (gen_random_uuid())
    No FK constraints (root entity).

    Refs: §10.3#mcp-agents, instrucciones.md §3.1#mcp-agents
    """

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Human-readable agent name",
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Agent purpose and capabilities description",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="False = agent not available to users; must be enabled by admin",
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="Agent runtime config (system_prompt, max_steps, memory_strategy, etc.)",
    )


# ---------------------------------------------------------------------------
# McpAgentBinding — many-to-many: agents x mcp_tools
# ---------------------------------------------------------------------------
class McpAgentBinding(Base):
    """ORM model for the `mcp_agent_bindings` table.

    Join table that associates agents with MCP tools they are authorized to
    use. enabled=False disables a specific tool for this agent without removing
    the binding (useful for temporary disabling during incident response).

    Table: mcp_agent_bindings
    PK: (agent_id, tool_id) composite
    FK: agent_id -> agents.id ON DELETE CASCADE
    FK: tool_id  -> mcp_tools.id ON DELETE CASCADE

    Refs: §10.3#mcp-agents
    """

    __tablename__ = "mcp_agent_bindings"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "agents.id",
            ondelete="CASCADE",
            name="mcp_agent_bindings_agent_id_fkey",
        ),
        primary_key=True,
        comment="PK part 1 + FK -> agents.id ON DELETE CASCADE",
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "mcp_tools.id",
            ondelete="CASCADE",
            name="mcp_agent_bindings_tool_id_fkey",
        ),
        primary_key=True,
        comment="PK part 2 + FK -> mcp_tools.id ON DELETE CASCADE",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="False = tool disabled for this agent (binding preserved for audit)",
    )


# ---------------------------------------------------------------------------
# AgentRun — a single execution of an agent
# ---------------------------------------------------------------------------
class AgentRun(Base):
    """ORM model for the `agent_runs` table.

    Records a single agent execution triggered by a user. agent_id and user_id
    use ON DELETE SET NULL to preserve the run history for cost/audit analysis
    even when the agent or user is deleted.

    status lifecycle: 'pending' → 'running' → 'done' | 'failed' | 'cancelled'.
    output is NULL until the run completes.

    Table: agent_runs
    PK: id UUID (gen_random_uuid())
    FK: agent_id -> agents.id ON DELETE SET NULL
    FK: user_id  -> users.id ON DELETE SET NULL

    Refs: §10.3#mcp-agents, instrucciones.md §3.1#mcp-agents (toda invocación auditada)
    """

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "agents.id",
            ondelete="SET NULL",
            name="agent_runs_agent_id_fkey",
        ),
        nullable=True,
        comment="FK -> agents.id ON DELETE SET NULL (preserve run history)",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="agent_runs_user_id_fkey",
        ),
        nullable=True,
        comment="FK -> users.id ON DELETE SET NULL (preserve run history)",
    )
    input: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="User input / task description sent to the agent",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Run status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'",
    )
    output: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Agent final output; NULL until run completes",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    finished_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Timestamp when run completed (success or failure)",
    )


# ---------------------------------------------------------------------------
# McpToolInvocation — audit record for each MCP tool call
# ---------------------------------------------------------------------------
class McpToolInvocation(Base):
    """ORM model for the `mcp_tool_invocations` table.

    Records every tool invocation made by an agent run. arguments_json stores
    the input parameters; result_json stores the tool response (may be NULL
    if invocation was denied or timed out). latency_ms tracks execution time.

    Table: mcp_tool_invocations
    PK: id UUID (gen_random_uuid())
    FK: tool_id      -> mcp_tools.id ON DELETE SET NULL
    FK: agent_run_id -> agent_runs.id ON DELETE CASCADE

    Refs: §10.3#mcp-agents, instrucciones.md §3.1#mcp-agents (toda invocación auditada)
    """

    __tablename__ = "mcp_tool_invocations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "mcp_tools.id",
            ondelete="SET NULL",
            name="mcp_tool_invocations_tool_id_fkey",
        ),
        nullable=True,
        comment="FK -> mcp_tools.id ON DELETE SET NULL (preserve invocation audit)",
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "agent_runs.id",
            ondelete="CASCADE",
            name="mcp_tool_invocations_agent_run_id_fkey",
        ),
        nullable=False,
        comment="FK -> agent_runs.id ON DELETE CASCADE",
    )
    arguments_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="Tool input arguments as JSON",
    )
    result_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Tool output as JSON; NULL if invocation was denied or failed pre-execution",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Invocation status: 'pending_approval' | 'approved' | 'denied' | 'success' | 'error'",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="Tool execution latency in ms; NULL if not yet executed",
    )
    error: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Error message if status='error'",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


# ---------------------------------------------------------------------------
# McpApproval — human approval record for a tool invocation
# ---------------------------------------------------------------------------
class McpApproval(Base):
    """ORM model for the `mcp_approvals` table.

    Records the approval or denial of an MCP tool invocation that requires
    human review (requires_approval=True on the tool). requested_by is the
    user who triggered the agent run; approved_by is the admin who reviewed.

    status: 'pending' | 'approved' | 'denied'. reason documents the decision.

    Table: mcp_approvals
    PK: id UUID (gen_random_uuid())
    FK: invocation_id -> mcp_tool_invocations.id ON DELETE CASCADE
    FK: requested_by  -> users.id (nullable; no CASCADE — audit trace)
    FK: approved_by   -> users.id (nullable; no CASCADE — audit trace)

    Refs: §10.3#mcp-agents, instrucciones.md §3.1#mcp-agents (write tools require human approval)
    """

    __tablename__ = "mcp_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    invocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "mcp_tool_invocations.id",
            ondelete="CASCADE",
            name="mcp_approvals_invocation_id_fkey",
        ),
        nullable=False,
        comment="FK -> mcp_tool_invocations.id ON DELETE CASCADE",
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", name="mcp_approvals_requested_by_fkey"),
        nullable=True,
        comment="FK -> users.id (no CASCADE — audit trace preserved if user deleted)",
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", name="mcp_approvals_approved_by_fkey"),
        nullable=True,
        comment="FK -> users.id (no CASCADE — audit trace preserved if admin deleted)",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Approval status: 'pending' | 'approved' | 'denied'",
    )
    reason: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Admin's reason for the approval/denial decision",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
