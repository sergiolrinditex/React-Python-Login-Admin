"""
Hilo People — MCP service: public re-export shim + rate limiters.

Slice:  P02-S07-T001 — MCP server and tool endpoints
Phase:  P02 Core Features
Purpose: Single import surface for MCP service functions, split across:
           - service_register.py  — register_server use case
           - service_sync.py      — sync_server use case
           - service_update_tool.py — update_mcp_tool use case

         Also hosts singleton RateLimiter instances consumed by router.py
         via Depends(). Must be in this shim (not in sub-modules) so the
         FastAPI dependency graph captures stable object identity.

Key deps:
  - app.security.rate_limit.RateLimiter
  - service_register / service_sync / service_update_tool

Source refs:
  - task pack P02-S07-T001 §D-RL (rate limit singletons for POST /servers + sync)
  - 01-non-negotiables.md §File size
"""

from __future__ import annotations

from app.mcp.service_register import register_server
from app.mcp.service_sync import sync_server
from app.mcp.service_update_tool import update_mcp_tool
from app.security.rate_limit import RateLimiter

# ---------------------------------------------------------------------------
# Singleton rate limiters (D-RL in task pack)
# ---------------------------------------------------------------------------
register_server_limiter = RateLimiter(
    prefix="MCP_REGISTER",
    per_minute=10,
    burst=10,
    window_seconds=60,
)

sync_server_limiter = RateLimiter(
    prefix="MCP_SYNC",
    per_minute=5,
    burst=5,
    window_seconds=60,
)

__all__ = [
    "register_server",
    "sync_server",
    "update_mcp_tool",
    "register_server_limiter",
    "sync_server_limiter",
]
