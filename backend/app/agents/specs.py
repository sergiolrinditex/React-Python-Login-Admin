"""
AgentSpec domain dataclass and JSON fixture loader.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Responsibility:
  - Defines `AgentSpec`, the in-memory domain representation of a configured
    agent.  Mirrors the shape of `AgentSeed` (from app.seeds.schemas.mcp_agents)
    but lives in the domain layer — no Pydantic, no I/O, no DB access.
  - Provides `load_specs_from_json(path)` to materialise `AgentSpec` objects
    from the productive verification fixture at data/verification/mcp_agents/agents.json.
    This is the Mode A loader described in the task pack §Resolución R1 (T008 default).
    Mode B (SQL from agents table) is deferred to P02-S08-T001.

Architecture note (Clean Architecture):
  `AgentSpec` is a domain dataclass — it imports NOTHING external.  The JSON
  loader in this file is an adapter (data layer concern) and performs I/O via
  stdlib only.  The function `load_specs_from_json` validates the raw JSON using
  `AgentSeed.model_validate` to guarantee correctness against the canonical seed
  schema, then converts each validated seed into an `AgentSpec`.

`mcp_server_name` is loaded but NOT used by the routing layer in T008.
It is carried in `AgentSpec` so that P02-S08-T001 can map it to MCP tools
without introducing schema drift.

Dependencies:
  - app.seeds.schemas.mcp_agents.AgentSeed (validation only; NOT a domain import)
  - Python stdlib: pathlib, json, dataclasses
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.seeds.schemas.mcp_agents import AgentSeed

_logger = get_logger("app.agents.specs")


# ---------------------------------------------------------------------------
# Domain dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentSpec:
    """In-memory representation of a configured agent.

    Attributes:
      name              — unique agent identifier (routing key).
      description       — human-readable description.
      agent_type        — 'supervisor' or 'subagent'.
      framework         — e.g. 'deepagents'.
      parent_agent_name — name of the supervisor (None for supervisor agents).
      subagent_topics   — keyword topics for routing (None for supervisor).
      system_prompt     — instruction prompt for the agent.
      model_id          — LiteLLM model string (e.g. 'gemini/gemini-2.5-flash').
      mcp_server_name   — MCP server binding name (None or unresolved in T008).
      is_active         — whether this agent is selectable.

    NOTE: `mcp_server_name` is loaded but NOT resolved to MCP tools in T008.
    Resolution is deferred to P02-S08-T001.
    """

    name: str
    description: str
    agent_type: str
    framework: str
    parent_agent_name: str | None
    subagent_topics: list[str] | None
    system_prompt: str
    model_id: str
    mcp_server_name: str | None = None
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# JSON fixture loader (Mode A — T008 default)
# ---------------------------------------------------------------------------


def _seed_to_spec(seed: AgentSeed) -> AgentSpec:
    """Convert a validated AgentSeed into a domain AgentSpec.

    Params:
      seed — validated AgentSeed instance.
    Returns: AgentSpec with same fields.
    Errors: none (all fields are already validated by AgentSeed).
    """
    return AgentSpec(
        name=seed.name,
        description=seed.description,
        agent_type=seed.agent_type,
        framework=seed.framework,
        parent_agent_name=seed.parent_agent_name,
        subagent_topics=list(seed.subagent_topics) if seed.subagent_topics else None,
        system_prompt=seed.system_prompt,
        model_id=seed.model_id,
        mcp_server_name=seed.mcp_server_name,
        is_active=seed.is_active,
    )


def load_specs_from_json(fixture_path: str | Path) -> list[AgentSpec]:
    """Load and validate AgentSpec objects from a JSON fixture file.

    This is Mode A loading (T008): reads the productive seed fixture at
    data/verification/mcp_agents/agents.json, validates each entry using
    AgentSeed.model_validate, and returns domain AgentSpec objects.

    Mode B (SQL from agents table) is deferred to P02-S08-T001.

    Params:
      fixture_path — path to the agents JSON fixture (str or Path).
                     Must point to a file with top-level key "agents".

    Returns: list of AgentSpec (may be empty if no agents in file).

    Errors:
      FileNotFoundError — if fixture_path does not exist.
      ValueError        — if JSON schema is invalid or AgentSeed validation fails.
      json.JSONDecodeError — if file content is not valid JSON.
    """
    path = Path(fixture_path)
    _logger.debug(
        "agents.specs.load.before",
        fixture_path=str(path),
    )

    if not path.exists():
        _logger.error(
            "agents.specs.load.error",
            fixture_path=str(path),
            error_class="FileNotFoundError",
            error_message_truncated="Fixture file not found",
        )
        raise FileNotFoundError(f"Agent fixture not found: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _logger.error(
            "agents.specs.load.error",
            fixture_path=str(path),
            error_class="JSONDecodeError",
            error_message_truncated=str(exc)[:200],
        )
        raise

    if not isinstance(raw, dict) or "agents" not in raw:
        raise ValueError(
            f"Fixture {path} must have top-level key 'agents'. Got keys: {list(raw.keys())!r}"
        )

    raw_agents: list[dict[str, Any]] = raw["agents"]
    specs: list[AgentSpec] = []

    for idx, entry in enumerate(raw_agents):
        try:
            seed = AgentSeed.model_validate(entry)
        except Exception as exc:
            _logger.error(
                "agents.specs.load.error",
                fixture_path=str(path),
                entry_index=idx,
                entry_name=entry.get("name", "<unknown>"),
                error_class=type(exc).__name__,
                error_message_truncated=str(exc)[:200],
            )
            raise ValueError(
                f"Fixture entry #{idx} ({entry.get('name', '?')!r}) failed validation: {exc}"
            ) from exc
        specs.append(_seed_to_spec(seed))

    _logger.debug(
        "agents.specs.load.after",
        fixture_path=str(path),
        loaded_count=len(specs),
        supervisor_count=sum(1 for s in specs if s.agent_type == "supervisor"),
        subagent_count=sum(1 for s in specs if s.agent_type == "subagent"),
    )
    return specs
