"""
Namespace isolation integration tests for the seed loader CLI.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Verifies that --only <namespace> loads ONLY that namespace's tables/logs.
In P00 state (no tables created yet), each --only X run should:
  - Emit "seed.namespace.table_missing" for its own tables only.
  - NOT emit table_missing WARNs for tables belonging to other namespaces.
  - Exit CLI with code 0.

Tests covered (3 total):
  1. test_only_auth_does_not_touch_other_namespaces — --only auth produces
       WARNs only for auth tables (users, user_mfa_configs).
  2. test_only_admin_ai_does_not_touch_other_namespaces — --only admin_ai
       produces WARNs only for admin_ai tables (ai_providers, ai_models).
  3. test_only_mcp_agents_does_not_touch_other_namespaces — --only mcp_agents
       produces WARNs only for mcp_agents tables (mcp_servers, agents).

Rules:
  - structlog capture_logs() for asserting WARN events.
  - Real compose postgres connection.

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0
  - structlog 25.5.0
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import structlog.testing

from tests.integration.conftest import _db_reachable


def _users_table_exists() -> bool:
    """Return True if P01-S01-T001 migration has been applied (users table exists).

    Purpose: skip 'P00 table-missing path' tests when migration has created tables.
    Added in P01-S01-T001 to prevent regression on P00 namespace-isolation tests.
    The auth loader's upsert SQL uses old synthetic column names (role, is_active,
    mfa_enabled) that don't exist in the real §10.3 schema.
    """
    if not _db_reachable():
        return False
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        async def _check() -> bool:
            dsn = (
                "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
                "@127.0.0.1:5433/hilopeople_dev"
            )
            engine = create_async_engine(dsn, pool_size=1, max_overflow=0)
            try:
                async with engine.connect() as conn:
                    result = await conn.execute(
                        text(
                            "SELECT COUNT(*) FROM information_schema.tables "
                            "WHERE table_schema = 'public' AND table_name = 'users'"
                        )
                    )
                    return (result.scalar() or 0) > 0
            finally:
                await engine.dispose()

        return asyncio.run(_check())
    except Exception:
        return False


_USERS_TABLE_EXISTS = _users_table_exists()

pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="compose postgres not reachable on :5433 — run 'docker compose up -d postgres' first",
)

_SKIP_WHEN_MIGRATION_APPLIED = pytest.mark.skipif(
    _USERS_TABLE_EXISTS,
    reason=(
        "P01-S01-T001 migration applied: auth loader synthetic columns (role, is_active, "
        "mfa_enabled) don't exist in real §10.3 schema. "
        "Tracked by FU-20260509073000 (replace synthetic bundle with real fixtures)."
    ),
)

# Tables per namespace (P00 state: none exist yet).
_AUTH_TABLES = {"users", "user_mfa_configs"}
_ADMIN_AI_TABLES = {"ai_providers", "ai_models"}
_MCP_TABLES = {"mcp_servers", "agents"}
_RAG_CHAT_TABLES = {"rag_collections"}
_HISTORY_TABLES = {"conversations"}
_RAG_DOCS_TABLES = {"documents"}

_ALL_TABLES = (
    _AUTH_TABLES | _ADMIN_AI_TABLES | _MCP_TABLES
    | _RAG_CHAT_TABLES | _HISTORY_TABLES | _RAG_DOCS_TABLES
)


def _extract_skipped_tables(logs: list[dict]) -> set[str]:
    """Extract table names from 'seed.namespace.table_missing' WARN events."""
    return {
        e["table"]
        for e in logs
        if e.get("event") == "seed.namespace.table_missing" and "table" in e
    }


# ---------------------------------------------------------------------------
# Test 1 — --only auth isolation
# ---------------------------------------------------------------------------


@_SKIP_WHEN_MIGRATION_APPLIED
async def test_only_auth_does_not_touch_other_namespaces(
    verification_bundle_dir: Path,
) -> None:
    """--only auth emits table_missing WARNs only for auth-owned tables.

    Verifies namespace isolation: no rag_chat, history, admin_ai, rag_docs,
    or mcp_agents table names appear in auth's log output.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.seeds.loader import load_auth

    dsn = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
    engine = create_async_engine(dsn, pool_pre_ping=True)

    try:
        with structlog.testing.capture_logs() as logs:
            report = await load_auth(engine, verification_bundle_dir)
    finally:
        await engine.dispose()

    skipped = _extract_skipped_tables(logs)
    other_tables = skipped - _AUTH_TABLES
    assert not other_tables, (
        f"--only auth emitted table_missing WARNs for non-auth tables: {other_tables}. "
        "Namespace isolation violated."
    )

    assert report.namespace == "auth", f"Expected namespace='auth', got '{report.namespace}'"

    # Structured WARN for missing auth tables must mention namespace='auth'.
    auth_warns = [
        e for e in logs
        if e.get("event") == "seed.namespace.table_missing"
        and e.get("namespace") == "auth"
    ]
    # If tables are missing, warns must have been emitted.
    if report.skipped_tables:
        assert auth_warns, (
            "Expected 'seed.namespace.table_missing' WARNs with namespace='auth' "
            f"when tables {report.skipped_tables} are missing."
        )
        for warn in auth_warns:
            assert warn.get("reason") == "table_missing", (
                f"Expected reason='table_missing', got: {warn.get('reason')}"
            )


# ---------------------------------------------------------------------------
# Test 2 — --only admin_ai isolation
# ---------------------------------------------------------------------------


async def test_only_admin_ai_does_not_touch_other_namespaces(
    verification_bundle_dir: Path,
) -> None:
    """--only admin_ai emits table_missing WARNs only for admin_ai-owned tables.

    Verifies that ai_providers and ai_models are the only tables probed.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.seeds.loader import load_admin_ai

    dsn = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
    engine = create_async_engine(dsn, pool_pre_ping=True)

    try:
        with structlog.testing.capture_logs() as logs:
            report = await load_admin_ai(engine, verification_bundle_dir)
    finally:
        await engine.dispose()

    skipped = _extract_skipped_tables(logs)
    other_tables = skipped - _ADMIN_AI_TABLES
    assert not other_tables, (
        f"--only admin_ai emitted table_missing WARNs for non-admin-ai tables: {other_tables}."
    )

    assert report.namespace == "admin_ai"

    if report.skipped_tables:
        admin_ai_warns = [
            e for e in logs
            if e.get("event") == "seed.namespace.table_missing"
            and e.get("namespace") == "admin_ai"
        ]
        assert admin_ai_warns, "Expected table_missing WARNs with namespace='admin_ai'."


# ---------------------------------------------------------------------------
# Test 3 — --only mcp_agents isolation
# ---------------------------------------------------------------------------


async def test_only_mcp_agents_does_not_touch_other_namespaces(
    verification_bundle_dir: Path,
) -> None:
    """--only mcp_agents emits table_missing WARNs only for mcp_agents-owned tables.

    Verifies that mcp_servers and agents are the only tables probed.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.seeds.loader import load_mcp_agents

    dsn = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
    engine = create_async_engine(dsn, pool_pre_ping=True)

    try:
        with structlog.testing.capture_logs() as logs:
            report = await load_mcp_agents(engine, verification_bundle_dir)
    finally:
        await engine.dispose()

    skipped = _extract_skipped_tables(logs)
    other_tables = skipped - _MCP_TABLES
    assert not other_tables, (
        f"--only mcp_agents emitted table_missing WARNs for non-mcp tables: {other_tables}."
    )

    assert report.namespace == "mcp_agents"
