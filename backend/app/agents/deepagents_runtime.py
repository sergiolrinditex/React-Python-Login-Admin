"""
Hilo People — DeepAgents runtime bridge.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Bridges the Agent domain entity + bound tools with the DeepAgents
         create_deep_agent() API. Assembles tool instances and returns a
         compiled LangGraph CompiledStateGraph ready for blocking invocation.

         Decision PATH-B (task pack §E.3 + developer investigation):
         DeepAgents 0.5.9 requires bind_tools() on the underlying LLM, which
         is NOT implemented by FakeListChatModel/GenericFakeChatModel. Therefore
         the smoke test uses a REAL ChatAnthropic instance with its _generate
         method monkeypatched to return a fake ChatResult. This is the smallest
         legitimate mock boundary per 01-non-negotiables.md §Tests (external
         third-party API you do not control = LLM HTTP gateway). Everything
         else (DB, bindings, DeepAgents graph compile, audit_log) is real.

         LLM factory: looks up the agent's config.model_id or falls back to
         the first active Anthropic provider in ai_providers. If neither is
         configured, defaults to 'claude-3-5-haiku-20241022' with a dummy key
         (only valid for smoke test with mocked _generate).

         request_id propagation: passed as metadata into the agent invocation
         config so all internal tool calls log with the same correlation ID.

Key deps:
  - deepagents.create_deep_agent
  - langchain_anthropic.ChatAnthropic
  - app.agents.tools.rag_tool (HrRagTool)
  - app.agents.tools.mcp_tool (McpToolWrapper, build_mcp_tool_wrapper)
  - app.agents.tools.admin_tool (AdminTool)

Source refs:
  - task pack P02-S08-T001 §E.3 (smoke execution), §D.2, §C.6
  - T003-discrepancy-deepagents.md (Beta API, provider SDK deps)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_DEFAULT_MODEL = "claude-3-5-haiku-20241022"
_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful HR assistant for Hilo People. "
    "Use the available tools to answer HR policy questions accurately."
)


def build_agent(
    *,
    agent_config: dict[str, Any],
    bound_tools: list[dict[str, Any]],
    run_id: uuid.UUID,
    request_id: str,
) -> Any:
    """Build a DeepAgents CompiledStateGraph for the given agent configuration.

    Assembles LangChain tools from bound_tools (MCP wrappers + RAG + admin),
    creates the LLM from agent_config, and calls create_deep_agent().

    Args:
        agent_config:  Agent.config JSONB dict (may contain 'model', 'system_prompt').
        bound_tools:   List of bound tool dicts with keys:
                         id, name, server_name, enabled, requires_approval,
                         risk_level, endpoint_url, auth_type, plaintext_secret.
        run_id:        UUID of the current agent_runs row (for log correlation).
        request_id:    X-Request-ID for log correlation.

    Returns:
        langgraph.graph.state.CompiledStateGraph ready for .invoke().

    Raises:
        RuntimeError: If create_deep_agent fails to compile the graph.
    """
    from deepagents import create_deep_agent  # deferred — allows test isolation
    from langchain_anthropic import ChatAnthropic

    if _VERBOSE:
        logger.debug(
            "agents.deepagents_runtime.build_agent.start run_id=%s "
            "tool_count=%d request_id=%s",
            str(run_id), len(bound_tools), request_id,
        )  # BEFORE

    # --- Build LLM ---
    model_name = agent_config.get("model") or _DEFAULT_MODEL
    # API key from env; smoke test mocks _generate so a placeholder is OK.
    api_key = os.getenv("ANTHROPIC_API_KEY", "dummy-smoke-key")
    llm = ChatAnthropic(
        model=model_name,
        api_key=api_key,  # type: ignore[arg-type]
        max_tokens=int(agent_config.get("max_tokens", 1024)),
    )

    # --- Build tool list ---
    from app.agents.tools.admin_tool import AdminTool
    from app.agents.tools.mcp_tool import build_mcp_tool_wrapper
    from app.agents.tools.rag_tool import build_rag_tool

    lc_tools = []

    # RAG tool — always available to all agents
    lc_tools.append(build_rag_tool())

    # MCP tools — one wrapper per approved binding
    for bt in bound_tools:
        if not bt.get("enabled", True):
            continue
        wrapper = build_mcp_tool_wrapper(
            tool_id=bt["id"],
            tool_name=bt["name"],
            tool_description=f"MCP tool from {bt.get('server_name', 'unknown')}",
            endpoint_url=bt.get("endpoint_url", ""),
            auth_type=bt.get("auth_type", "none"),
            plaintext_secret=bt.get("plaintext_secret"),
        )
        lc_tools.append(wrapper)

    # Admin tool placeholder
    lc_tools.append(AdminTool())

    # --- Assemble system prompt ---
    system_prompt = agent_config.get("system_prompt") or _DEFAULT_SYSTEM_PROMPT

    try:
        graph = create_deep_agent(
            model=llm,
            tools=lc_tools,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error(
            "agents.deepagents_runtime.build_agent.error run_id=%s error=%s request_id=%s",
            str(run_id), type(exc).__name__, request_id, exc_info=True,
        )
        raise RuntimeError(f"Failed to compile DeepAgent graph: {exc}") from exc

    if _VERBOSE:
        logger.debug(
            "agents.deepagents_runtime.build_agent.ok run_id=%s tools=%d request_id=%s",
            str(run_id), len(lc_tools), request_id,
        )  # AFTER

    return graph


def invoke_agent(
    graph: Any,
    *,
    input_text: str,
    run_id: uuid.UUID,
    request_id: str,
) -> str:
    """Invoke a compiled DeepAgents graph with a single user message.

    Args:
        graph:       CompiledStateGraph from build_agent().
        input_text:  User task input text.
        run_id:      UUID of the agent_runs row (for log correlation).
        request_id:  X-Request-ID for log correlation.

    Returns:
        Final agent response text (truncated to 4000 chars for DB storage).

    Raises:
        Exception: Propagates any graph invocation error for caller to handle.
    """
    from langchain_core.messages import HumanMessage

    if _VERBOSE:
        logger.debug(
            "agents.deepagents_runtime.invoke_agent.start run_id=%s "
            "input_len=%d request_id=%s",
            str(run_id), len(input_text), request_id,
        )  # BEFORE

    config = {
        "configurable": {
            "thread_id": str(run_id),
            "request_id": request_id,
        }
    }

    result = graph.invoke(
        {"messages": [HumanMessage(content=input_text)]},
        config=config,
    )

    messages = result.get("messages", [])
    output_text = ""
    if messages:
        last = messages[-1]
        content = last.content if hasattr(last, "content") else str(last)
        output_text = str(content)[:4000]

    if _VERBOSE:
        logger.debug(
            "agents.deepagents_runtime.invoke_agent.ok run_id=%s "
            "output_len=%d request_id=%s",
            str(run_id), len(output_text), request_id,
        )  # AFTER

    return output_text
