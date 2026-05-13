"""
Hilo People — Agents audit adapter.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Thin adapter over app.admin._audit.write_admin_ai_audit for the
         three agents audit actions:
           - admin.agent.tools.update     (PATCH /agents/{id}/tools)
           - admin.agent.run.start        (POST /agents/runs — on insert)
           - admin.agent.run.complete     (POST /agents/runs — on terminal state)

         All calls use D-S2 (independent session via write_admin_ai_audit).
         No credential values, system prompts, or raw user input are logged.

Key deps:
  - app.admin._audit.write_admin_ai_audit — D-S2 independent session helper

Source refs:
  - task pack P02-S08-T001 §E.2, §E.3 (audit rows)
  - 01-non-negotiables.md §Security (audit log, no PII/credentials in metadata)
"""

from __future__ import annotations

import uuid

def _write_audit(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Lazy proxy for write_admin_ai_audit to avoid circular import.

    app.agents.audit is imported by app.agents.service_bind_tools, which is
    part of app.agents.router chain. app.agents.router is imported by
    app.agents.__init__, which is imported by app.admin.__init__ (for wiring).
    Importing app.admin._audit at module level would trigger app.admin.__init__
    before app.agents is fully initialized → circular ImportError.

    Deferred import breaks the cycle: by the time _write_audit() is called
    at runtime (not import time), both packages are fully initialized.
    """
    from app.admin._audit import write_admin_ai_audit  # noqa: PLC0415
    return write_admin_ai_audit(*args, **kwargs)


def audit_agent_tools_update(
    *,
    actor_user_id: uuid.UUID,
    agent_id: uuid.UUID,
    added: list[str],
    removed: list[str],
    tool_ids: list[str],
    request_id: str = "",
    ip: str = "",
    user_agent: str = "",
) -> None:
    """Write audit row for agent tool binding update.

    Args:
        actor_user_id: Admin who performed the update.
        agent_id:      UUID of the agent whose bindings changed.
        added:         List of tool UUID strings added in this operation.
        removed:       List of tool UUID strings removed in this operation.
        tool_ids:      Final tool_ids list (the new binding set).
        request_id:    X-Request-ID for correlation.
        ip:            Client IP.
        user_agent:    Client User-Agent.
    """
    _write_audit(
        actor_user_id=actor_user_id,
        action="admin.agent.tools.update",
        entity_type="agent",
        entity_id=agent_id,
        metadata={
            "tool_ids": tool_ids,
            "added": added,
            "removed": removed,
            "request_id": request_id,
            "ip": ip,
            "user_agent": user_agent,
        },
    )


def audit_agent_run_start(
    *,
    actor_user_id: uuid.UUID,
    agent_id: uuid.UUID,
    run_id: uuid.UUID,
    request_id: str = "",
    ip: str = "",
) -> None:
    """Write audit row when an agent run is created (status=pending).

    Args:
        actor_user_id: Admin who started the run.
        agent_id:      UUID of the agent being run.
        run_id:        UUID of the new agent_runs row.
        request_id:    X-Request-ID for correlation.
        ip:            Client IP.
    """
    _write_audit(
        actor_user_id=actor_user_id,
        action="admin.agent.run.start",
        entity_type="agent_run",
        entity_id=run_id,
        metadata={
            "agent_id": str(agent_id),
            "request_id": request_id,
            "ip": ip,
        },
    )


def audit_agent_run_complete(
    *,
    actor_user_id: uuid.UUID,
    agent_id: uuid.UUID,
    run_id: uuid.UUID,
    status: str,
    request_id: str = "",
) -> None:
    """Write audit row when an agent run reaches a terminal state.

    Args:
        actor_user_id: Admin who started the run.
        agent_id:      UUID of the agent.
        run_id:        UUID of the completed agent_runs row.
        status:        Terminal status ('done' | 'failed' | 'cancelled').
        request_id:    X-Request-ID for correlation.
    """
    _write_audit(
        actor_user_id=actor_user_id,
        action="admin.agent.run.complete",
        entity_type="agent_run",
        entity_id=run_id,
        metadata={
            "agent_id": str(agent_id),
            "status": status,
            "request_id": request_id,
        },
    )
