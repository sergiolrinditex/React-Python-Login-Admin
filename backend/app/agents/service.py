"""
Hilo People — Agents service: public re-export shim + rate limiters.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Single import surface for agent service functions, split across:
           - service_list.py       — list_agents use case
           - service_bind_tools.py — bind_tools use case
           - service_start_run.py  — start_agent_run use case

         Also hosts singleton RateLimiter for POST /agents/runs.
         Must be in this shim (not in sub-modules) so the FastAPI dependency
         graph captures stable object identity across the process lifetime.

Key deps:
  - app.security.rate_limit.RateLimiter (Redis sliding-window)
  - service_list / service_bind_tools / service_start_run

Source refs:
  - task pack P02-S08-T001 §E.3 (rate limit: 5 req/min/user for start_run)
  - 01-non-negotiables.md §File size
"""

from __future__ import annotations

from app.agents.service_bind_tools import bind_tools
from app.agents.service_list import list_agents
from app.agents.service_start_run import start_agent_run
from app.security.rate_limit import RateLimiter

# Conservative rate limit per task pack §E.3: 5 req/min/user
start_run_limiter = RateLimiter(
    prefix="AGENTS_START_RUN",
    per_minute=5,
    burst=5,
    window_seconds=60,
)

__all__ = [
    "list_agents",
    "bind_tools",
    "start_agent_run",
    "start_run_limiter",
]
