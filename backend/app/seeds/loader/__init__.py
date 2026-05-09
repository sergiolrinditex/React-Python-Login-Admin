"""
Namespace loaders for the verification seed bundle.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Each public async function loads one namespace. All loaders:
  1. Validate fixtures via Pydantic schemas (fail-fast on invalid data).
  2. Check whether required tables exist (table-tolerant: missing = WARN + skip).
  3. Upsert rows idempotently using INSERT … ON CONFLICT DO UPDATE.
  4. Return a LoadReport with counts and skipped tables.

Public API (re-exported here for backwards compatibility — callers keep using
`from app.seeds.loader import load_auth, ...` exactly as before):
  - LoadReport
  - load_auth
  - load_rag_chat
  - load_history
  - load_admin_ai
  - load_rag_docs
  - load_mcp_agents

NOTE on encryption: admin_ai loader writes plaintext synthetic credentials.
  This is acceptable because they are labelled 'synthetic-' and have no real
  value. When P02-S02-T001 adds encryption-at-rest, a follow-up will add
  encrypt-on-write there. Documented per task pack §Security.

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
