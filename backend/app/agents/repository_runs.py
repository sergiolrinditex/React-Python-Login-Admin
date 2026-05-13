"""
Hilo People — Agents repository: run and invocation operations.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: DB read/write for agent_runs and mcp_tool_invocations tables.
         Extracted from repository_agents.py for file-size compliance.

Operations:
  - create_agent_run           — INSERT agent_runs(status='pending')
  - update_agent_run_status    — UPDATE status + optional output/finished_at
  - record_tool_invocation     — INSERT mcp_tool_invocations

Key deps:
  - app.db.models.agents (AgentRun, McpToolInvocation)
  - sqlalchemy==2.0.49

Source refs:
  - task pack P02-S08-T001 §E.3 (run lifecycle), §C.4 (status vocabulary)
  - 01-non-negotiables.md §Database (parametrized queries, transactions)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.agents import AgentRun, McpToolInvocation

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def create_agent_run(
    session: Session,
    *,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    input_text: str,
) -> AgentRun:
    """Insert a new AgentRun row with status='pending'. Caller flushes/commits.

    Args:
        session:    Active SQLAlchemy Session.
        agent_id:   FK -> agents.id.
        user_id:    FK -> users.id (the admin initiating the run).
        input_text: User input text (max 4000 chars, validated upstream).

    Returns:
        Flushed AgentRun ORM instance with id populated.
    """
    if _VERBOSE:
        logger.debug(
            "agents.repository.create_run.start agent_id=%s user_id=%s",
            str(agent_id), str(user_id),
        )  # BEFORE

    run = AgentRun(
        agent_id=agent_id,
        user_id=user_id,
        input=input_text,
        status="pending",
        output=None,
        finished_at=None,
    )
    session.add(run)
    session.flush()

    if _VERBOSE:
        logger.debug(
            "agents.repository.create_run.ok run_id=%s", str(run.id)
        )  # AFTER
    return run


def update_agent_run_status(
    session: Session,
    *,
    run: AgentRun,
    status: str,
    output: str | None = None,
    set_finished_at: bool = False,
) -> None:
    """Update the status (and optionally output/finished_at) of an AgentRun.

    Status vocabulary: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'

    Args:
        session:         Active Session.
        run:             AgentRun ORM instance (mutated in-place).
        status:          New status string.
        output:          Agent output text (set on terminal states).
        set_finished_at: If True, sets finished_at to DB clock (func.now()).
    """
    if _VERBOSE:
        logger.debug(
            "agents.repository.update_run_status.start run_id=%s status=%s",
            str(run.id), status,
        )  # BEFORE

    run.status = status
    if output is not None:
        run.output = output
    if set_finished_at:
        run.finished_at = sa.func.now()
    session.flush()

    if _VERBOSE:
        logger.debug(
            "agents.repository.update_run_status.ok run_id=%s status=%s",
            str(run.id), status,
        )  # AFTER


def record_tool_invocation(
    session: Session,
    *,
    agent_run_id: uuid.UUID,
    tool_id: uuid.UUID,
    arguments_json: dict[str, Any],
    result_json: dict[str, Any] | None,
    status: str,
    latency_ms: int | None = None,
    error: str | None = None,
) -> McpToolInvocation:
    """Insert an McpToolInvocation row for audit. Caller flushes/commits.

    Status vocabulary for invocations:
      'pending_approval' | 'approved' | 'denied' | 'success' | 'error'

    Args:
        session:        Active Session.
        agent_run_id:   FK -> agent_runs.id.
        tool_id:        FK -> mcp_tools.id.
        arguments_json: Tool input arguments.
        result_json:    Tool output (None if denied or timed out).
        status:         Invocation outcome status.
        latency_ms:     Execution latency in ms (None if not executed).
        error:          Error message (None on success).

    Returns:
        Flushed McpToolInvocation instance.
    """
    if _VERBOSE:
        logger.debug(
            "agents.repository.record_invocation.start run_id=%s tool_id=%s status=%s",
            str(agent_run_id), str(tool_id), status,
        )  # BEFORE

    invocation = McpToolInvocation(
        tool_id=tool_id,
        agent_run_id=agent_run_id,
        arguments_json=arguments_json,
        result_json=result_json,
        status=status,
        latency_ms=latency_ms,
        error=error,
    )
    session.add(invocation)
    session.flush()

    if _VERBOSE:
        logger.debug(
            "agents.repository.record_invocation.ok invocation_id=%s",
            str(invocation.id),
        )  # AFTER
    return invocation
