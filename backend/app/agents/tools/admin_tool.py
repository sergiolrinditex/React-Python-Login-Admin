"""
Hilo People — Agent admin tool: placeholder for future admin surface tools.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Placeholder BaseTool for admin-facing agent actions (e.g. create user,
         update policies). Not invoked in the V1 smoke path. Declared here per
         §C.6 (TECHNICAL_GUIDE §10.4#deepagents tools list) to make the module
         structure complete and importable.

         The concrete implementations are deferred to a future slice when
         admin agent capabilities are defined in the source-of-truth.

Source refs:
  - task pack P02-S08-T001 §D.2 (tools/admin_tool.py)
  - TECHNICAL_GUIDE §10.4 (admin_tool listed in tools set)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


class _AdminInput(BaseModel):
    """Placeholder input schema for admin tool."""

    action: str = Field(description="Admin action to perform (placeholder).")


class AdminTool(BaseTool):
    """Placeholder admin tool — not implemented in V1 smoke.

    This tool is registered in the agent's tool set to reserve the name
    'admin_action' for future admin capabilities. Invoking it returns a
    not-implemented message without any side effects.
    """

    name: str = "admin_action"
    description: str = (
        "Perform an administrative action on behalf of HR. "
        "(Not available in V1 — placeholder for future capabilities.)"
    )
    args_schema: type[BaseModel] = _AdminInput
    return_direct: bool = False

    def _run(self, action: str) -> str:
        """Return a not-implemented message. No side effects.

        Args:
            action: Requested admin action (ignored).

        Returns:
            Not-implemented placeholder string.
        """
        if _VERBOSE:
            logger.debug("agents.tools.admin_tool.run action=%s (placeholder)", action)
        return "Admin actions are not available in V1. This capability is planned for a future release."

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """Async variant — delegates to synchronous _run."""
        return self._run(*args, **kwargs)
