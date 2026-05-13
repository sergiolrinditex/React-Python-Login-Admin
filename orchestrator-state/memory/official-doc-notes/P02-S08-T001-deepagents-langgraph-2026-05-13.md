# Official Doc Note: P02-S08-T001 — DeepAgents 0.5.9 + LangGraph 1.1.10 Runtime API

DATE: 2026-05-13
TASK_ID: P02-S08-T001
TOPIC: DeepAgents 0.5.9 invocation API, model independence, LangGraph Postgres checkpointer, MCP tool binding, error/state taxonomy
VERIFIED_BY: official-docs-researcher

---

## Sources consulted

| Source | URL / path | Access timestamp |
|---|---|---|
| DeepAgents graph.py source (installed 0.5.9) | `/Users/sergiolr/Library/Python/3.11/lib/python/site-packages/deepagents/graph.py` | 2026-05-13 live read |
| DeepAgents _models.py source (installed 0.5.9) | `/Users/sergiolr/Library/Python/3.11/lib/python/site-packages/deepagents/_models.py` | 2026-05-13 live read |
| DeepAgents official docs (Context7 /websites/langchain_oss_python_deepagents) | https://docs.langchain.com/oss/python/deepagents | 2026-05-13 via Context7 |
| DeepAgents README (GitHub) | https://raw.githubusercontent.com/langchain-ai/deepagents/main/README.md | 2026-05-13 via WebFetch |
| DeepAgents PyPI JSON 0.5.9 | https://pypi.org/pypi/deepagents/0.5.9/json | 2026-05-13 via WebFetch |
| LangGraph Python docs (Context7 /websites/langchain_oss_python_langgraph) | https://docs.langchain.com/oss/python/langgraph | 2026-05-13 via Context7 |
| LangGraph errors.py source (installed 1.1.10) | `/Users/sergiolr/Library/Python/3.11/lib/python/site-packages/langgraph/errors.py` | 2026-05-13 live read |
| langgraph-checkpoint-postgres PyPI JSON | https://pypi.org/pypi/langgraph-checkpoint-postgres/json | 2026-05-13 via WebFetch |
| langchain-mcp-adapters PyPI JSON | https://pypi.org/pypi/langchain-mcp-adapters/json | 2026-05-13 via WebFetch |
| FakeListChatModel source (installed langchain_community) | `/Users/sergiolr/Library/Python/3.11/lib/python/site-packages/langchain_community/chat_models/fake.py` | 2026-05-13 live read |

---

## Q1 — DeepAgents 0.5.9 minimal blocking invocation API

### Answer: CONFIRMED

**Import path and entry function:**
```python
from deepagents import create_deep_agent
```

**Full signature (from installed source, `deepagents/graph.py` L206-225):**
```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    checkpointer: Checkpointer | None = None,
    # ... other optional params
) -> CompiledStateGraph:
```

**Returns:** A `CompiledStateGraph` (LangGraph compiled graph). This is a LangGraph runnable; call `.invoke(...)` on it.

**Minimal blocking invocation (from official docs, source: https://docs.langchain.com/oss/python/deepagents):**
```python
from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",   # provider:model string OR BaseChatModel instance
    tools=[my_tool],                       # Sequence[BaseTool | Callable | dict]
    system_prompt="You are a helpful assistant",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "hello"}]}
)
```

**Key facts for `build_agent()` implementation:**
- `model` accepts either a `"provider:model"` string (resolved via `init_chat_model`) OR a pre-initialized `BaseChatModel` instance (passed through unchanged by `resolve_model`).
- `tools` accepts: `BaseTool` subclass instances, plain Python callables with docstrings, or dicts. No `bind_tools(...)` call needed — tools are wired into the middleware stack internally.
- `agent.invoke({...})` is the blocking synchronous call. Returns a dict with `messages` and other state keys from `AgentState`.
- The returned graph has `recursion_limit: 9_999` preset in metadata.
- `system_prompt` is placed BEFORE the SDK default prompt (user instructions always win).

**Official doc source:** https://docs.langchain.com/oss/python/deepagents (Context7, High reputation, 2026-05-13)

---

## Q2 — DeepAgents 0.5.9 model independence (no-LLM smoke path)

### Answer: Path A IS VIABLE — use FakeListChatModel (BaseChatModel subclass)

**Finding:** `create_deep_agent(model=...)` accepts any `BaseChatModel` instance directly. The `_models.py::resolve_model()` function (L33-34):
```python
if isinstance(model, BaseChatModel):
    return model   # passed through unchanged — no API key check
```

**Confirmed available FakeLLM class (verified via installed package):**
```python
from langchain_community.chat_models import FakeListChatModel

fake_llm = FakeListChatModel(responses=["OK — smoke complete"])
agent = create_deep_agent(
    model=fake_llm,        # BaseChatModel — no API key required, no network call
    tools=[my_tool],
    system_prompt="smoke test agent",
)
result = agent.invoke({"messages": [{"role": "user", "content": "hello"}]})
```

`FakeListChatModel` MRO confirmed: `FakeListChatModel → SimpleChatModel → BaseChatModel → ...`

**Note on `langsmith` tracing:** `langsmith` is a mandatory dep of `deepagents==0.5.9` (`langsmith>=0.8.0`). With no `LANGCHAIN_API_KEY` in env, langsmith tracing is disabled silently — no error is raised. Confirmed by langsmith behavior: tracing is only active when `LANGCHAIN_TRACING_V2=true` + key present.

**Path B applicability:** Path B (mocking the LLM HTTP client) is NOT required for smoke tests. `FakeListChatModel` avoids all network calls at the LLM layer. The only mock needed for TC16 (MCP unreachable) is the MCP HTTP client layer, per `01-non-negotiables.md` §acceptable mocks.

**Conclusion for TC11 smoke path (happy path):** Use `FakeListChatModel(responses=["smoke response"])` as model. No `pytest.skip` needed. Tools are wired normally; tool invocation may or may not occur depending on whether `FakeListChatModel` emits a tool-call AIMessage vs plain text. For guaranteed deterministic output, configure `responses=` to return a non-tool-call message.

**Caveat:** `FakeListChatModel` does NOT emit `AIMessage` with `tool_calls` — it returns plain `AIMessage` with the string as content. This means the smoke agent will not actually invoke MCP tools in the happy path (no tool call generated by the fake LLM). TC17 assertion should be `assert mcp_tool_invocations == 0` (zero rows, documented as passing because the agent ran and produced output without calling MCP). This is explicitly covered by TC17 wording in §G.2.

**Alternative (if tool-call smoke is required):** Pass a real model string with a real key. For CI environments without real LLM keys, mock only the HTTP gateway (e.g., `unittest.mock.patch` on `anthropic.Anthropic._post`) — this is the legitimate mock boundary for third-party services per `01-non-negotiables.md`.

---

## Q3 — LangGraph 1.1.10 Postgres checkpointer pattern

### Answer: CONFIRMED with important version note

**Installed versions:**
- `langgraph==1.1.10` (confirmed)
- `langgraph-checkpoint-postgres==3.0.5` (installed; latest stable on PyPI is 3.1.0 released 2026-05-12)

**Import path (confirmed working):**
```python
from langgraph.checkpoint.postgres import PostgresSaver
# Async variant:
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
```

**Minimal wiring pattern (from official LangGraph docs, source: https://docs.langchain.com/oss/python/langgraph/add-memory):**
```python
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, MessagesState, START

DB_URI = "postgresql://user:pass@localhost:5432/dbname?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # Creates required tables on first run

    builder = StateGraph(MessagesState)
    builder.add_node(my_node)
    builder.add_edge(START, "my_node")
    graph = builder.compile(checkpointer=checkpointer)
```

**Key facts for `graphs/checkpointer.py` stub:**
- `PostgresSaver.from_conn_string(DB_URI)` is the factory (context manager or plain call).
- **`checkpointer.setup()` MUST be called on first use** to create the required schema tables (`langgraph_checkpoints_blobs`, `langgraph_checkpoints`, `langgraph_checkpoint_migrations`). Official docs: "When using Postgres checkpointers for the first time, make sure to call `.setup()` method on them to create required tables."
- **For the smoke stub in this slice:** The stub should wrap `checkpointer.setup()` in a guard (e.g., call it in a `setup_checkpointer()` function triggered at service startup). No separate Alembic migration is needed for LangGraph checkpointer tables — the SDK manages them internally.
- `psycopg>=3.2.0` and `psycopg-pool>=3.2.0` are required peer deps of `langgraph-checkpoint-postgres`. Both are already in the project requirements.
- `thread_id` in `config["configurable"]["thread_id"]` scopes checkpointed state to a run session.

**Missing dep check:** `langgraph-checkpoint-postgres` is NOT declared in `backend/requirements.txt` or `backend/pyproject.toml`. It is transitively available (installed 3.0.5) but not explicitly pinned. **This is a gap the developer must resolve** — explicit pin `langgraph-checkpoint-postgres==3.0.5` should be added before using it.

---

## Q4 — MCP tool binding into DeepAgents

### Answer: TWO PATHS — langchain-mcp-adapters is the canonical bridge BUT is not yet in the project requirements

**Path A — langchain-mcp-adapters (canonical, official):**

Official docs show (source: https://docs.langchain.com/oss/python/deepagents/mcp):
```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent  # (or create_deep_agent)

client = MultiServerMCPClient({
    "my_server": {
        "transport": "http",
        "url": "http://localhost:8080/mcp",
    }
})
tools = await client.get_tools()  # returns List[BaseTool]
agent = create_deep_agent(model="...", tools=tools)
```

- PyPI: `langchain-mcp-adapters==0.2.2` (latest stable, 2026-05-13)
- Deps: `langchain-core>=1.0.0,<2.0.0`, `mcp>=1.9.2` (project has `mcp==1.27.1` ✅)
- **`MultiServerMCPClient.get_tools()` returns `List[BaseTool]`** — these are fully compatible with `create_deep_agent(tools=...)`.
- **langchain-mcp-adapters is NOT installed in this environment** (verified: import fails).
- **langchain-mcp-adapters is NOT in the project requirements** (`requirements.txt` / `pyproject.toml`).

**Path B — custom `BaseTool` subclass (fallback, no new dep):**

Since `langchain-mcp-adapters` is not yet a declared project dep and this slice is already R-3 medium risk, the safer default for V1 smoke is a thin custom `BaseTool` subclass in `backend/app/agents/tools/mcp_tool.py` that delegates directly to `app.mcp.client` JSON-RPC layer:

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel

class McpToolInput(BaseModel):
    arguments: dict

class McpToolAdapter(BaseTool):
    name: str
    description: str
    mcp_tool_name: str
    mcp_server_id: str
    args_schema: type[BaseModel] = McpToolInput

    def _run(self, arguments: dict) -> str:
        # delegates to app.mcp.client — audited JSON-RPC call
        ...
```

`BaseTool` subclass instances are accepted by `create_deep_agent(tools=[...])` as confirmed by the signature `tools: Sequence[BaseTool | Callable | dict[str, Any]]`.

**Recommendation for this slice:** Use Path B (custom BaseTool) to avoid adding a new unplanned dependency. Path A (`langchain-mcp-adapters`) should be formally added as a dependency in a follow-up slice if the pattern proves useful across multiple agents. Do NOT add `langchain-mcp-adapters` to requirements without proper declaration in source-of-truth.

---

## Q5 — Agent run lifecycle error/state taxonomy

### Answer: CONFIRMED — `cancelled` is NOT in the DeepAgents/LangGraph vocabulary; `failed` is the only error terminal in V1

**LangGraph exception hierarchy (from installed `langgraph/errors.py`, confirmed 1.1.10):**

| Exception | Base | Meaning | Maps to agent_runs.status |
|---|---|---|---|
| `GraphRecursionError` | `RecursionError` | Exhausted `recursion_limit` steps | `failed` (terminal, non-retryable in V1) |
| `GraphInterrupt` | `GraphBubbleUp` | Graph paused by `interrupt()` call for human-in-the-loop | Not applicable to smoke path (no interrupt nodes) |
| `NodeInterrupt` | `GraphInterrupt` | **Deprecated in 1.x** — use `interrupt()` function instead | Not applicable |
| `InvalidUpdateError` | `Exception` | Concurrent or invalid state update | `failed` (terminal) |
| `EmptyInputError` | `Exception` | Graph received empty input | `failed` (terminal) |
| `TaskNotFound` | `Exception` | Executor can't find task (distributed mode only) | Not applicable in V1 sync path |

**Retryable vs terminal classification for `service_start_run.py`:**

| Exception category | Retry? | Status mapping |
|---|---|---|
| `GraphRecursionError` | No — structural issue | `failed` |
| `GraphInterrupt` | Resume via `Command(resume=...)` — but V1 smoke has no interrupt nodes | N/A |
| `InvalidUpdateError` | No — code bug | `failed` |
| Tool exceptions (MCP connection error, HTTP error) | Per-tool RetryPolicy only | `failed` (after retries) |
| LLM HTTP timeout / rate limit | Via `RetryPolicy(max_attempts=N, retry_on=ConnectionError)` in graph node | `failed` after exhaustion |
| Any unhandled `Exception` | No — bubble up to service layer | `failed` |

**`cancelled` state:** LangGraph has no built-in notion of "user-triggered cancellation" in 0.5.x or 1.x (synchronous path). There is no `cancel_run()` API. `cancelled` is not in the DeepAgents vocabulary either. **Document the gap in handoff:** V1 accepts `cancelled` as a reserved status in `agent_runs.status` for future use but it is never written by the engine in V1. Only `pending → running → done` (success) or `pending → running → failed` (exception) are emitted.

**`done` vs `succeeded`:** LangGraph state machines use "END" (graph terminates normally). The task pack vocabulary uses `done` not `succeeded` — this is an internal DB column naming choice, NOT constrained by LangGraph. Use `done` as pinned in the task pack DDL.

**Official source for error handling:** https://docs.langchain.com/oss/python/langgraph/fault-tolerance (Context7, 2026-05-13).
Official source for interrupt: https://docs.langchain.com/oss/python/langgraph/interrupts (Context7, 2026-05-13).

---

## Discrepancy section

### Discrepancy 1 (MEDIUM — action required before developer uses checkpointer)
**`langgraph-checkpoint-postgres` not explicitly declared in project requirements.**

- TECHNICAL_GUIDE §10.4 describes `graphs/checkpointer.py` as a deliverable for this slice.
- `PostgresSaver` is importable today (transitively installed 3.0.5) but NOT pinned in `requirements.txt` or `pyproject.toml`.
- Impact: If `langgraph-checkpoint-postgres` is upgraded transitively and breaks the API, there is no version lock.
- **Recommendation:** Developer should add `langgraph-checkpoint-postgres==3.0.5` to `backend/requirements.txt` and `backend/pyproject.toml` as part of this slice.

### Discrepancy 2 (LOW — informational, no code change required)
**`langchain-mcp-adapters` is the official canonical bridge for MCP → DeepAgents tool binding, but it is not yet a declared project dependency.**

- TECHNICAL_GUIDE §10.4 specifies `agents/tools/mcp_tool.py` as a custom adapter — this is consistent with Path B (custom BaseTool subclass).
- No discrepancy with TECHNICAL_GUIDE §10.4 for the V1 smoke slice; the custom BaseTool approach is correct.
- If future slices adopt `langchain-mcp-adapters`, a source-of-truth amendment + requirements update is needed.

### Discrepancy 3 (LOW — informational, no code change required)
**`NodeInterrupt` is deprecated in LangGraph 1.x** (confirmed in installed source: `@deprecated("NodeInterrupt is deprecated. Please use interrupt() instead.")`). Any existing code that imports `NodeInterrupt` should use `from langgraph.types import interrupt` instead.

### No discrepancy with TECHNICAL_GUIDE §10.4
The core structure described in TECHNICAL_GUIDE §10.4 is consistent with the verified API:
- `agents/deepagents_runtime.py`: `create_deep_agent(model, tools, system_prompt, checkpointer=...)` — correct.
- Tools as `BaseTool` instances in `agents/tools/rag_tool.py`, `agents/tools/mcp_tool.py`, `agents/tools/admin_tool.py` — correct.
- `graphs/workflows.py` as LangGraph StateGraph workflows — correct.
- `graphs/checkpointer.py` using `PostgresSaver` — correct (with the pin gap noted above).

---

## Summary for developer

| Q | Answer | Action required |
|---|---|---|
| Q1 | `from deepagents import create_deep_agent`; `agent.invoke({"messages": [...]})` | None — use as shown |
| Q2 | Pass `FakeListChatModel(responses=["smoke"])` as model — no API key needed | Use `langchain_community.chat_models.FakeListChatModel` for TC11-TC17 |
| Q3 | `from langgraph.checkpoint.postgres import PostgresSaver`; call `.setup()` on first use | Add `langgraph-checkpoint-postgres==3.0.5` to requirements (discrepancy 1) |
| Q4 | Custom `BaseTool` subclass in `mcp_tool.py` delegating to `app.mcp.client` — Path B | No new dep needed for V1 smoke |
| Q5 | `cancelled` not in LangGraph vocabulary; `failed` is the only error terminal; `done` = normal completion | Document cancelled as reserved in handoff RFC |

---

RESOLVED: yes — all 5 questions answered from official sources (installed package source, official LangGraph docs via Context7, PyPI). No discrepancy blocks implementation. Three low/medium non-blocking discrepancies documented; only Discrepancy 1 (missing explicit pin for langgraph-checkpoint-postgres) requires a small concrete action from the developer before using the checkpointer.
TIMESTAMP: 2026-05-13T00:00:00Z
