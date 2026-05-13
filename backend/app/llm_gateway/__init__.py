"""
Hilo People — LLM gateway package public API.

Slice:  P02-S03-T002 — Chat streaming endpoint (new module §K-LLM-GATEWAY)
Phase:  P02 Core Features (the motor)
Purpose: Re-exports the public surface of the llm_gateway module so callers
         can import from 'app.llm_gateway' without knowing internal layout.

         Public API:
           - stream_chat()          — async generator yielding StreamEvent records
           - embed_query()          — compute 1536-dim query embedding for RAG
           - StreamEvent            — typed streaming event dataclass
           - LiteLLMError           — typed LiteLLM error (gateway layer)
           - LiteLLMTimeoutError    — timeout subclass
           - EmbeddingError         — typed embedding error

Key deps:
  - app.llm_gateway.litellm_client (stream_chat, embed_query, StreamEvent)
  - app.llm_gateway.errors         (LiteLLMError, LiteLLMTimeoutError, EmbeddingError)

Source refs:
  - task pack P02-S03-T002 §E.3 (gateway API contract)
  - task pack P02-S03-T002 §F.2 §K-LLM-GATEWAY (drift anchor)
"""

from app.llm_gateway.errors import EmbeddingError, LiteLLMError, LiteLLMTimeoutError
from app.llm_gateway.litellm_client import StreamEvent, embed_query, stream_chat

__all__ = [
    "stream_chat",
    "embed_query",
    "StreamEvent",
    "LiteLLMError",
    "LiteLLMTimeoutError",
    "EmbeddingError",
]
