"""
Loader for the 'mcp_agents' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Loads mcp_agents/servers.json + mcp_agents/agents.json into mcp_servers +
agents (table-tolerant).

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - pydantic 2.12.5
  - structlog 25.5.0
"""
from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger
from app.seeds.io import load_fixture
from app.seeds.loader._common import LoadReport
from app.seeds.schemas.mcp_agents import AgentListSeed, McpServerListSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


async def load_mcp_agents(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
) -> LoadReport:
    """Load the 'mcp_agents' namespace: mcp_agents/servers.json + agents.json.

    Purpose: seed MCP server and agent records for J105 MCP/agents journey.
    Tables targeted: mcp_servers, agents.
    Table-tolerant: logs WARN and skips if tables do not exist.

    Params/Returns/Errors: see load_auth docstring.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="mcp_agents", dry_run=dry_run)
    ns = "mcp_agents"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run)

    servers_data = load_fixture(source_dir, ns, "servers.json", McpServerListSeed)
    agents_data = load_fixture(source_dir, ns, "agents.json", AgentListSeed)

    if dry_run:
        report.duration_ms = (time.monotonic() - t0) * 1000
        _logger.info("seed.namespace.done", namespace=ns, persisted=0, dry_run=True)
        return report

    srv_exist = await table_exists(engine, "mcp_servers")
    if not srv_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="mcp_servers",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("mcp_servers")
    else:
        for server in servers_data.servers:
            tok = server.access_token
            masked_token = tok[:4] + "..." if len(tok) > 4 else "..."
            _logger.debug(
                "seed.mcp_agents.upsert_server.before",
                server_name=server.name,
                token_masked=masked_token,
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO mcp_servers
                          (name, endpoint_url, transport, access_token, is_active)
                        VALUES
                          (:name, :endpoint_url, :transport, :access_token, :is_active)
                        ON CONFLICT (name) DO UPDATE
                          SET endpoint_url = EXCLUDED.endpoint_url,
                              transport = EXCLUDED.transport,
                              access_token = EXCLUDED.access_token,
                              is_active = EXCLUDED.is_active
                        """
                    ),
                    {
                        "name": server.name,
                        "endpoint_url": server.endpoint_url,
                        "transport": server.transport,
                        "access_token": server.access_token,
                        "is_active": server.is_active,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)

    agent_exist = await table_exists(engine, "agents")
    if not agent_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="agents",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("agents")
    else:
        for agent in agents_data.agents:
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO agents
                          (name, description, mcp_server_name, system_prompt, model_id, is_active)
                        VALUES
                          (:name, :description, :mcp_server_name,
                           :system_prompt, :model_id, :is_active)
                        ON CONFLICT (name) DO UPDATE
                          SET description = EXCLUDED.description,
                              mcp_server_name = EXCLUDED.mcp_server_name,
                              system_prompt = EXCLUDED.system_prompt,
                              model_id = EXCLUDED.model_id,
                              is_active = EXCLUDED.is_active
                        """
                    ),
                    {
                        "name": agent.name,
                        "description": agent.description,
                        "mcp_server_name": agent.mcp_server_name,
                        "system_prompt": agent.system_prompt,
                        "model_id": agent.model_id,
                        "is_active": agent.is_active,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
