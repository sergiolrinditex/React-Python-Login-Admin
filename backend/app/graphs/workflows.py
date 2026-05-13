"""
Hilo People — LangGraph workflow stubs for agent runs.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Minimal LangGraph workflow definitions for the smoke test path.
         The V1 smoke run uses DeepAgents create_deep_agent() directly
         (which internally builds a LangGraph StateGraph). This module
         provides the structural stub that future approval-workflow slices
         will extend.

         V1 scope (per §I.4 YAGNI — NOT doing):
           - LangGraph human-in-the-loop approval workflow
           - MCP write-tool approval gates via mcp_approvals table
           - Multi-step conversation persistence

         Future slices will add:
           - graphs/workflows.py::build_approval_workflow() — LangGraph
             StateGraph with human review node + mcp_approvals writes
           - graphs/workflows.py::build_long_run_workflow() — for async
             multi-step runs with Postgres checkpointing

Key deps:
  - langgraph.graph (StateGraph — imported lazily to avoid import cost)

Source refs:
  - task pack P02-S08-T001 §C.6, §I.4
  - TECHNICAL_GUIDE §10.4 (graphs/workflows.py description)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def get_smoke_workflow_info() -> dict[str, Any]:
    """Return metadata about the V1 smoke workflow configuration.

    The smoke run uses DeepAgents create_deep_agent() directly rather than
    a custom StateGraph. This function documents the configuration for
    observability and audit purposes.

    Returns:
        Dict with workflow metadata for logging/audit.
    """
    if _VERBOSE:
        logger.debug("graphs.workflows.get_smoke_workflow_info.start")

    info = {
        "workflow_type": "deepagents_single_step",
        "checkpointer": None,
        "approval_workflow": False,
        "version": "v1_smoke",
        "langgraph_version": _get_langgraph_version(),
    }

    if _VERBOSE:
        logger.debug(
            "graphs.workflows.get_smoke_workflow_info.ok type=%s",
            info["workflow_type"],
        )
    return info


def _get_langgraph_version() -> str:
    """Return the installed langgraph version string.

    Returns:
        Version string or 'unknown' if not determinable.
    """
    try:
        import langgraph
        return getattr(langgraph, "__version__", "unknown")
    except ImportError:
        return "not_installed"
