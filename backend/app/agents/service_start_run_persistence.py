"""
Hilo People — Agents service: persistence helpers for start_agent_run.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Provides DB-write helpers for the start_agent_run use case.
         Extracted from service_start_run.py to satisfy the ≤300 LoC rule.

         Responsibility: "Write execution results back to the database."
           - record_run_tool_invocations — writes mcp_tool_invocations rows
           - fail_run                    — marks agent_run as failed in DB

Key deps:
  - app.agents.repository_runs (record_tool_invocation, update_agent_run_status)
  - app.agents.tools.mcp_tool (McpToolWrapper — to read last_result)

Source refs:
  - task pack P02-S08-T001 §E.3 steps 7–8
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.agents.repository_runs import record_tool_invocation, update_agent_run_status

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def record_run_tool_invocations(
    session: Session,
    graph: Any,
    approved_tools: list[dict[str, Any]],
    run_id: Any,
) -> None:
    """Write mcp_tool_invocations rows for any tool that ran during the graph.

    Reads last_result from each McpToolWrapper in the graph's tools list.
    If a tool was never invoked (last_result is None), nothing is written.

    Args:
        session:       Active Session.
        graph:         CompiledStateGraph (tools accessible via graph.nodes).
        approved_tools: Tool dicts used to build the graph.
        run_id:        agent_runs row UUID.
    """
    from app.agents.tools.mcp_tool import McpToolWrapper

    # Iterate graph nodes to find McpToolWrapper instances that ran
    for node_name, node in getattr(graph, "_nodes", {}).items():
        if not hasattr(node, "runnable"):
            continue
        runnable = node.runnable
        if hasattr(runnable, "tools"):
            for tool in runnable.tools:
                if isinstance(tool, McpToolWrapper) and tool.last_result is not None:
                    res = tool.last_result
                    record_tool_invocation(
                        session,
                        agent_run_id=run_id,
                        tool_id=res.tool_id,
                        arguments_json=res.arguments_json,
                        result_json=res.result_json,
                        status=res.status,
                        latency_ms=res.latency_ms,
                        error=res.error,
                    )


def fail_run(session: Session, *, run: Any, error: Exception) -> None:
    """Set an agent run to 'failed' status with a redacted error summary.

    Args:
        session: Active Session.
        run:     AgentRun ORM instance to update.
        error:   The exception that caused the failure.
    """
    redacted = f"Run failed: {type(error).__name__}"
    try:
        update_agent_run_status(
            session, run=run, status="failed",
            output=redacted, set_finished_at=True,
        )
        session.commit()
    except Exception as inner:
        logger.error(
            "agents.service.fail_run.error run_id=%s inner_error=%s",
            str(run.id), type(inner).__name__,
        )
        try:
            session.rollback()
        except Exception:
            pass
