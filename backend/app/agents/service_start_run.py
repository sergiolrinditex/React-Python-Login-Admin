"""
Hilo People — Agents service: start_agent_run use case (orchestration).

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Implements POST /api/v1/agents/runs smoke execution path:
           1. Validate agent exists + enabled
           2. INSERT agent_runs(status='pending')
           3. Enumerate approved bound tools (service_start_run_tools)
           4. Build DeepAgent graph via deepagents_runtime
           5. UPDATE status='running'
           6. Execute single blocking smoke step
           7. UPDATE status='done'/output/finished_at (service_start_run_persistence)
           8. Record mcp_tool_invocations (service_start_run_persistence)
           9. Write audit rows for start + complete (D-S2)
          On any error in steps 3–7:
           - UPDATE status='failed'/output=redacted_error
           - Write complete audit row
           - Raise AgentRunFailedError → 502

         Tool-resolution helpers live in service_start_run_tools.py.
         DB-write helpers for execution results live in service_start_run_persistence.py.

Business rules:
  - agent.enabled=False → raises AgentDisabledError (409 AGENT_DISABLED).
  - Bound tools with requires_approval=True that lack an mcp_approvals row
    are EXCLUDED from this run (V1: log + exclude, don't fail per §E.3 step 5).

Key deps:
  - app.agents.repository_agents (get_agent_by_id)
  - app.agents.repository_runs (create_agent_run, update_agent_run_status)
  - app.agents.deepagents_runtime (build_agent, invoke_agent)
  - app.agents.audit (audit_agent_run_start, audit_agent_run_complete)
  - app.agents.service_start_run_tools (build_approved_tools_list)
  - app.agents.service_start_run_persistence (record_run_tool_invocations, fail_run)

Source refs:
  - task pack P02-S08-T001 §E.3
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.audit import audit_agent_run_complete, audit_agent_run_start
from app.agents.deepagents_runtime import build_agent, invoke_agent
from app.agents.errors import AgentDisabledError, AgentRunFailedError
from app.agents.repository_agents import get_agent_by_id
from app.agents.repository_runs import create_agent_run, update_agent_run_status
from app.agents.service_start_run_persistence import fail_run, record_run_tool_invocations
from app.agents.service_start_run_tools import build_approved_tools_list

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def start_agent_run(
    session: Session,
    *,
    agent_id: uuid.UUID,
    input_text: str,
    actor_user_id: uuid.UUID,
    request_id: str = "",
    ip: str = "",
) -> dict[str, Any]:
    """Execute a single blocking smoke step for an agent run.

    Args:
        session:       Active SQLAlchemy Session.
        agent_id:      UUID of the agent to run.
        input_text:    User task input text.
        actor_user_id: Admin initiating the run (for audit + user_id FK).
        request_id:    X-Request-ID for log correlation.
        ip:            Client IP for audit.

    Returns:
        Dict with 'run_id' (UUID) and 'status' (str).

    Raises:
        AgentNotFoundError:   Agent not found in DB.
        AgentDisabledError:   Agent exists but enabled=False.
        AgentRunFailedError:  Any failure during graph execution.
    """
    if _VERBOSE:
        logger.debug(
            "agents.service.start_run.start agent_id=%s input_len=%d request_id=%s",
            str(agent_id), len(input_text), request_id,
        )  # BEFORE

    # --- 1. Validate agent ---
    agent_data = get_agent_by_id(session, agent_id)
    if not agent_data["enabled"]:
        logger.warning(
            "agents.service.start_run.disabled agent_id=%s request_id=%s",
            str(agent_id), request_id,
        )
        raise AgentDisabledError(f"Agent is disabled: {agent_id}")

    # --- 2. INSERT pending run ---
    run = create_agent_run(
        session,
        agent_id=agent_id,
        user_id=actor_user_id,
        input_text=input_text,
    )
    session.commit()

    audit_agent_run_start(
        actor_user_id=actor_user_id,
        agent_id=agent_id,
        run_id=run.id,
        request_id=request_id,
        ip=ip,
    )

    # --- 3. Enumerate approved bound tools ---
    approved_tools = build_approved_tools_list(session, agent_data, run.id, request_id)

    # --- 4–7. Execute smoke step ---
    try:
        graph = build_agent(
            agent_config=agent_data.get("config") or {},
            bound_tools=approved_tools,
            run_id=run.id,
            request_id=request_id,
        )

        # UPDATE status='running'
        update_agent_run_status(session, run=run, status="running")
        session.commit()

        output_text = invoke_agent(graph, input_text=input_text, run_id=run.id, request_id=request_id)

        # --- 8. Record tool invocations ---
        record_run_tool_invocations(session, graph, approved_tools, run.id)

        # UPDATE status='done'
        update_agent_run_status(
            session, run=run, status="done",
            output=output_text, set_finished_at=True,
        )
        session.commit()

    except Exception as exc:
        logger.error(
            "agents.service.start_run.error run_id=%s error=%s request_id=%s",
            str(run.id), type(exc).__name__, request_id, exc_info=True,
        )
        fail_run(session, run=run, error=exc)

        audit_agent_run_complete(
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            run_id=run.id,
            status="failed",
            request_id=request_id,
        )
        raise AgentRunFailedError(f"Agent run failed: {type(exc).__name__}") from exc

    audit_agent_run_complete(
        actor_user_id=actor_user_id,
        agent_id=agent_id,
        run_id=run.id,
        status="done",
        request_id=request_id,
    )

    if _VERBOSE:
        logger.debug(
            "agents.service.start_run.ok run_id=%s status=done request_id=%s",
            str(run.id), request_id,
        )  # AFTER

    return {"run_id": run.id, "status": "done"}
