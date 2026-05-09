"""
Namespace loaders for the verification seed bundle.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Each public async function loads one namespace. All loaders:
  1. Validate fixtures via Pydantic schemas (fail-fast on invalid data).
  2. Check whether required tables exist (table-tolerant: missing = WARN + skip).
  3. Upsert rows idempotently using INSERT … ON CONFLICT DO UPDATE.
  4. Return a LoadReport with counts and skipped tables.

CHANGE from T003: all loaders now accept bundle_type kwarg ('synthetic'/'productive').
  The bootstrap CLI reads MANIFEST._bundle_type and passes it to all loaders.
  Synthetic path remains unchanged for backward compatibility.

Public API (re-exported here for backwards compatibility):
  - LoadReport
  - load_auth
  - load_rag_chat
  - load_history
  - load_admin_ai
  - load_rag_docs
  - load_mcp_agents

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - pydantic 2.12.5
  - structlog 25.5.0
"""
from __future__ import annotations

from app.seeds.loader._common import LoadReport
from app.seeds.loader.admin_ai import load_admin_ai
from app.seeds.loader.auth import load_auth
from app.seeds.loader.history import load_history
from app.seeds.loader.mcp_agents import load_mcp_agents
from app.seeds.loader.rag_chat import load_rag_chat
from app.seeds.loader.rag_docs import load_rag_docs

__all__ = [
    "LoadReport",
    "load_admin_ai",
    "load_auth",
    "load_history",
    "load_mcp_agents",
    "load_rag_chat",
    "load_rag_docs",
]
