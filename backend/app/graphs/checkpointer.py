"""
Hilo People — LangGraph Postgres checkpointer wiring stub.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Provides a factory for creating a LangGraph Postgres checkpointer.
         The concrete setup (schema init, langgraph_checkpoints table) is
         deferred per §J R-2 — no migration in this slice.

         V1 smoke path: the smoke run uses no checkpointer (stateless single
         step). This stub makes the module importable and documents the
         wiring pattern for future slices.

         Decision R-2 rationale (task pack §J R-2):
           langgraph-checkpoint-postgres requires schema setup (usually via
           AsyncConnectionPool or synchronous setup_schema() call that creates
           a 'langgraph_checkpoints' table family). Since we don't need
           persistent state in V1 smoke, we omit the migration and use
           checkpointer=None in create_deep_agent(). Future slices that
           implement stateful approval workflows will:
             1. Add a migration for the langgraph_checkpoints tables.
             2. Replace checkpointer=None with get_postgres_checkpointer().

Key deps:
  - langgraph (1.1.10)
  - langgraph-checkpoint (auto-installed with langgraph)

Source refs:
  - task pack P02-S08-T001 §C.6, §J R-2
  - TECHNICAL_GUIDE §10.4 (graphs/checkpointer.py)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def get_postgres_checkpointer(database_url: str | None = None) -> Any:
    """Create a LangGraph Postgres checkpointer (stub — not used in V1 smoke).

    This function is a stub for future slices. The langgraph-checkpoint-postgres
    package requires schema setup before first use. In V1, create_deep_agent()
    is called with checkpointer=None (stateless execution).

    Args:
        database_url: Postgres connection string. Falls back to DATABASE_URL env var.

    Returns:
        A configured PostgresSaver checkpointer instance (future).

    Raises:
        NotImplementedError: Always in V1 — checkpointer setup requires a
                             dedicated migration slice.

    TODO(future-slice): Replace this stub with:
        from langgraph.checkpoint.postgres import PostgresSaver
        conn_str = database_url or os.getenv('DATABASE_URL', '')
        checkpointer = PostgresSaver.from_conn_string(conn_str)
        checkpointer.setup()  # creates langgraph_checkpoints table family
        return checkpointer
    """
    if _VERBOSE:
        logger.debug("graphs.checkpointer.get_postgres_checkpointer.stub")

    raise NotImplementedError(
        "Postgres checkpointer is deferred to a future migration slice. "
        "Use checkpointer=None in create_deep_agent() for V1 smoke runs. "
        "See task pack P02-S08-T001 §J R-2."
    )
