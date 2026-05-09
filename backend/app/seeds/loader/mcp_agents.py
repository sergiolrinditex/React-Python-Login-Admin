"""
Loader for the 'mcp_agents' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Loads mcp_agents/servers.json + mcp_agents/agents.json into mcp_servers + agents.
Table-tolerant: tables don't exist until P02-S07/P02-S08.

CHANGE from T003:
  - McpServerSeed validates with bundle_type context.
  - Productive bundles: access_token resolved from access_token_env via resolve_env_var().
    Public servers may omit both access_token and access_token_env.
  - AgentSeed: updated SQL to include new fields (agent_type, framework,
    parent_agent_name, subagent_topics). mcp_server_name now optional.
  - SECURITY: real tokens NEVER in logs.

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
from app.seeds.loader._common import BundleType, LoadReport, resolve_env_var
from app.seeds.schemas.mcp_agents import AgentListSeed, McpServerListSeed, McpServerSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


def _validate_servers(
    servers_data: McpServerListSeed, bundle_type: BundleType
) -> list[McpServerSeed]:
    """Validate each server with bundle_type context."""
    from app.seeds.io import BundleLoadError  # noqa: PLC0415

    validated = []
    for raw in servers_data.servers:
        try:
            s = McpServerSeed.validate_with_bundle_type(raw.model_dump(), bundle_type)
            validated.append(s)
        except ValueError as exc:
            raise BundleLoadError(
                Path("mcp_agents/servers.json"),
                f"Server '{raw.name}': {exc}",
            ) from exc
    return validated


async def load_mcp_agents(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
    bundle_type: BundleType = "synthetic",
) -> LoadReport:
    """Load the 'mcp_agents' namespace: mcp_agents/servers.json + agents.json.

    Purpose: seed MCP server and agent records for J105 MCP/agents journey.
    Tables targeted: mcp_servers, agents.
    Table-tolerant: logs WARN and skips if tables do not exist.

    Params:
      engine      — async engine.
      source_dir  — bundle root directory.
      dry_run     — validate only; no DB writes.
      bundle_type — forwarded to schema validators.
    Returns: LoadReport.
    Errors: BundleLoadError if fixture missing/invalid or productive env var missing.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="mcp_agents", dry_run=dry_run)
    ns = "mcp_agents"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run, bundle_type=bundle_type)

    servers_data = load_fixture(source_dir, ns, "servers.json", McpServerListSeed)
    agents_data = load_fixture(source_dir, ns, "agents.json", AgentListSeed)

    validated_servers = _validate_servers(servers_data, bundle_type)

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
        for server in validated_servers:
            # Resolve access token from env var for productive bundles.
            access_token: str | None = None
            if server.access_token_env:
                access_token = resolve_env_var(server.access_token_env, required=False)
                _logger.debug(
                    "seed.mcp_agents.upsert_server.before",
                    server_name=server.name,
                    token_source=f"env:{server.access_token_env}",
                    token_masked="[resolved_from_env]",
                )
            elif server.access_token:
                access_token = server.access_token
                tok = server.access_token
                masked = tok[:4] + "..." if len(tok) > 4 else "..."
                _logger.debug(
                    "seed.mcp_agents.upsert_server.before",
                    server_name=server.name,
                    token_masked=masked,
                )
            else:
                _logger.debug(
                    "seed.mcp_agents.upsert_server.before",
                    server_name=server.name,
                    token_masked="[none — public server]",
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
                        "access_token": access_token,
                        "is_active": server.is_active,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)
            _logger.debug("seed.mcp_agents.upsert_server.after", server_name=server.name)

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
            _logger.debug(
                "seed.mcp_agents.upsert_agent.before",
                agent_name=agent.name,
                agent_type=agent.agent_type,
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO agents
                          (name, description, agent_type, framework, mcp_server_name,
                           parent_agent_name, subagent_topics, system_prompt, model_id, is_active)
                        VALUES
                          (:name, :description, :agent_type, :framework, :mcp_server_name,
                           :parent_agent_name, :subagent_topics, :system_prompt, :model_id,
                           :is_active)
                        ON CONFLICT (name) DO UPDATE
                          SET description = EXCLUDED.description,
                              agent_type = EXCLUDED.agent_type,
                              framework = EXCLUDED.framework,
                              mcp_server_name = EXCLUDED.mcp_server_name,
                              parent_agent_name = EXCLUDED.parent_agent_name,
                              subagent_topics = EXCLUDED.subagent_topics,
                              system_prompt = EXCLUDED.system_prompt,
                              model_id = EXCLUDED.model_id,
                              is_active = EXCLUDED.is_active
                        """
                    ),
                    {
                        "name": agent.name,
                        "description": agent.description,
                        "agent_type": agent.agent_type,
                        "framework": agent.framework,
                        "mcp_server_name": agent.mcp_server_name,
                        "parent_agent_name": agent.parent_agent_name,
                        "subagent_topics": agent.subagent_topics,
                        "system_prompt": agent.system_prompt,
                        "model_id": agent.model_id,
                        "is_active": agent.is_active,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)
            _logger.debug("seed.mcp_agents.upsert_agent.after", agent_name=agent.name)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
