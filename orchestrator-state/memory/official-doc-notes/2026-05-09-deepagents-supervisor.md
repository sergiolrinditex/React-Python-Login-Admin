# deepagents 0.5.7 — Supervisor/Subagent Pattern (P00-S02-T005)

**Date**: 2026-05-09
**Task**: P00-S02-T005
**Severity**: INFORMATIONAL (pattern confirmed; seed field names need alignment with real API)
**Sources**:
- Context7 /langchain-ai/deepagents (GitHub repo, deepagents 0.5.7)
- Context7 /websites/langchain_oss_python_deepagents (official LangChain deepagents docs)

---

## Key Finding: deepagents uses coordinator-worker, NOT "supervisor" terminology

The deepagents library does NOT have a "Supervisor" class or `agent_type=supervisor` concept
in its public API. The pattern is:

### Canonical deepagents Architecture

```
Main agent (coordinator) = create_deep_agent(model=..., tools=[...], subagents=[...])
Subagents = dicts or SubAgent TypedDicts in the `subagents=[...]` list
```

There is no distinction between "supervisor" and "subagent" at the `create_deep_agent` level.
The **main agent IS the orchestrator/coordinator** — it uses an internal `task` tool to delegate
to subagents. There is no separate `Supervisor` class.

### Canonical SubAgent shape (confirmed from official docs)

```python
from deepagents import SubAgent

subagent: SubAgent = {
    "name": "researcher",                 # string — routing key
    "description": "Research agent...",   # string — used by main agent to decide routing
    "system_prompt": "You are...",        # string — optional
    "tools": [web_search],               # list of tools — optional
    "model": "google_genai:gemini-2.5-flash",  # optional, overrides main agent model
    "skills": ["/skills/research/"],     # optional
}
```

### AsyncSubAgent shape (for remote deployments)

```python
from deepagents import AsyncSubAgent

remote_subagent: AsyncSubAgent = {
    "name": "deep-researcher",
    "description": "Performs intensive research...",
    "graph_id": "research-agent",         # Graph name on remote LangGraph deployment
    "url": "https://my-deployment.langchain.app",  # optional
}
```

### Full create_deep_agent signature

```python
agent = create_deep_agent(
    model="google_genai:gemini-2.5-flash",    # or any langchain model string
    tools=[...],                               # main agent tools
    system_prompt="...",                       # orchestrator prompt
    subagents=[subagent_1, subagent_2],       # SubAgent dicts
    name="main-agent",                         # optional
    memory=["./AGENTS.md"],                    # optional middleware
    skills=["./skills/"],                      # optional middleware
    backend=FilesystemBackend(root_dir="./"),  # optional
)
```

---

## Implication for AgentSeed schema in T005

The task pack proposes `AgentSeed` with fields:
- `agent_type: Literal["supervisor","subagent"]`
- `framework: Literal["deepagents","langchain","custom"]`
- `parent_agent_name: str | None`
- `subagent_topics: list[str] | None`

### Assessment

**`agent_type="supervisor"` vs `"subagent"`**: The deepagents library distinguishes between
the MAIN AGENT (coordinator, created by `create_deep_agent`) and SUBAGENTS (entries in the
`subagents=[]` list). The `agent_type` field in the seed is a PROJECT-LEVEL abstraction that
P02-S08 will use to know which DB row becomes the `create_deep_agent(...)` call and which
become entries in `subagents=[...]`. This is VALID as a seed convention — it is NOT a deepagents
API field, it is a config field that the runtime layer in P02-S08 will read.

**`parent_agent_name`**: Also a project-level convention, not a deepagents API field. The runtime
in P02-S08 resolves which subagents belong to which main agent by looking up `parent_agent_name`.
This is a reasonable seed design.

**`subagent_topics`**: NOT a deepagents API field. Deepagents uses `description` for routing
(the main agent reads descriptions to decide which subagent to delegate to). The `subagent_topics`
list is a project-level metadata field that P02-S08 can use to build the subagent's `description`
string or a custom topic router. This is fine as seed metadata.

**`framework: "deepagents"`**: Correct for entries using deepagents 0.5.7.

### Recommended seed field mapping to deepagents API (for P02-S08 runtime)

| Seed field | deepagents runtime mapping |
|---|---|
| `agent_type="supervisor"` | becomes the main `create_deep_agent(...)` call |
| `agent_type="subagent"` | becomes an entry in `subagents=[...]` |
| `parent_agent_name` | identifies which supervisor owns this subagent |
| `subagent_topics` | used to build `description` and/or topic routing in system_prompt |
| `name` | maps to SubAgent `"name"` key |
| `model_name` (from ai_models) | maps to `"model"` key in SubAgent dict (optional override) |
| `mcp_server_name` (from mcp_servers) | maps to MCP tool injected into `"tools"` list |

### No naming changes needed for the seed schema

The T005 `AgentSeed` field names are coherent with the deepagents pattern. They don't map
1:1 to deepagents API keys (which is correct — they are seed/config fields, not runtime calls).
The `agent_type`, `parent_agent_name`, `subagent_topics` and `framework` fields will NOT require
renaming when P02-S08 is implemented.

---

## Conclusion

The deepagents 0.5.7 supervisor pattern is confirmed:
- Main agent = coordinator, created by `create_deep_agent(subagents=[...])`
- Subagents = typed dicts with `name`, `description`, `system_prompt`, `tools`, `model`
- No `Supervisor` class; no `subagent_topics` in deepagents API (project-level field)
- The `AgentSeed` field names in the task pack are VALID project abstractions over the deepagents API

Developer can proceed with the `AgentSeed` schema as designed. P02-S08 runtime will map
`agent_type=supervisor` → main `create_deep_agent` call; `subagent` → `subagents=[]` entries.

RESOLVED: n/a — no discrepancy with project intent. Field names confirmed future-proof.
