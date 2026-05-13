"""
Hilo People — Agent RAG tool: wraps app.rag.retrieve as a LangChain BaseTool.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Provides a LangChain-compatible BaseTool that DeepAgents can call
         to retrieve relevant HR document chunks via cosine-similarity search.

         For the smoke test the agent is created without a real embedding
         (the tool is registered but not invoked in the smoke path unless
         the LLM requests it). The tool is importable without any external
         LLM call.

Key deps:
  - langchain_core.tools.BaseTool
  - app.rag.retrieve, RetrieverFilters

Source refs:
  - task pack P02-S08-T001 §D.2 (tools/rag_tool.py)
  - instrucciones.md §3.1#mcp-agents (rag_tool in DeepAgents tools list)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_MAX_CHUNKS = 5
_RAG_TOP_K = 5


class _RagInput(BaseModel):
    """Input schema for the RAG retrieval tool."""

    query: str = Field(description="Query text to retrieve relevant HR document chunks.")
    language: str = Field(default="es", description="Language filter ('es', 'en', 'fr').")
    top_k: int = Field(default=_RAG_TOP_K, ge=1, le=20, description="Max chunks to return.")


class HrRagTool(BaseTool):
    """LangChain BaseTool wrapping app.rag.retrieve.

    Allows DeepAgents to call the RAG retriever to fetch relevant HR
    policy document chunks based on semantic similarity.

    Name follows snake_case as required by most LLM tool-calling APIs.
    """

    name: str = "hr_rag_retrieval"
    description: str = (
        "Search the HR document knowledge base for relevant policy information. "
        "Use this when answering questions about company policies, benefits, "
        "vacation rules, or procedures. Returns the most relevant text chunks."
    )
    args_schema: type[BaseModel] = _RagInput
    return_direct: bool = False

    def _run(self, query: str, language: str = "es", top_k: int = _RAG_TOP_K) -> str:
        """Invoke the RAG retriever synchronously.

        Args:
            query:    Search query text.
            language: Language filter code.
            top_k:    Max chunks to return.

        Returns:
            Formatted string of relevant chunks, or an empty-results message.
        """
        if _VERBOSE:
            logger.debug(
                "agents.tools.rag_tool.run.start query_len=%d language=%s top_k=%d",
                len(query), language, top_k,
            )  # BEFORE

        try:
            from app.rag import RetrieverFilters, retrieve  # deferred — keeps tool importable without DB

            filters = RetrieverFilters(
                language=language,
                top_k=min(top_k, _MAX_CHUNKS),
                min_score=0.0,
                collection_ids=None,
            )
            chunks = retrieve(query_text=query, filters=filters)

            if not chunks:
                result = "No relevant HR policy documents found for this query."
            else:
                lines = []
                for i, chunk in enumerate(chunks, 1):
                    lines.append(f"[{i}] {chunk.content} (score={chunk.score:.3f})")
                result = "\n".join(lines)

            if _VERBOSE:
                logger.debug(
                    "agents.tools.rag_tool.run.ok chunks=%d", len(chunks)
                )  # AFTER

            return result

        except Exception as exc:
            logger.error(
                "agents.tools.rag_tool.run.error error=%s",
                type(exc).__name__, exc_info=True,
            )
            return f"RAG retrieval failed: {type(exc).__name__}"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """Async variant — delegates to synchronous _run."""
        return self._run(*args, **kwargs)


def build_rag_tool() -> HrRagTool:
    """Factory for the HR RAG retrieval tool.

    Returns:
        Configured HrRagTool instance ready for DeepAgents registration.
    """
    return HrRagTool()
