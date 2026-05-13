"""
Hilo People — LLM gateway package public API.

Slice:  P02-S03-T002 — Chat streaming endpoint (new module §K-LLM-GATEWAY)
        P02-S05-T002 — Model test and usage endpoints (§D-LLMG-INIT: added
                       complete_chat, CompletionResult, ModelTestFailedError)
                       §D-LLMG-INIT-F1-LITELLM-LOGGER-LEVEL: force third-party
                       'LiteLLM' Python logger to WARNING at package import so
                       it never inherits DEBUG from root when
                       ENABLE_VERBOSE_LOGGING=true. Fixes /verify-slice F1
                       (prompt-content leak via 'LiteLLM' namespace at
                       utils.py:482 'Request to litellm: ...'). This is
                       cross-cutting: it covers complete_chat (model_test),
                       stream_chat (P02-S03-T002 chat streaming) and
                       embed_query (RAG) callsites because all three go through
                       the same library namespace.
Phase:  P02 Core Features (the motor)
Purpose: Re-exports the public surface of the llm_gateway module so callers
         can import from 'app.llm_gateway' without knowing internal layout.

         Public API:
           - stream_chat()          — async generator yielding StreamEvent records
           - embed_query()          — compute 1536-dim query embedding for RAG
           - StreamEvent            — typed streaming event dataclass
           - complete_chat()        — non-streaming single completion (P02-S05-T002)
           - CompletionResult       — typed result for complete_chat (P02-S05-T002)
           - LiteLLMError           — typed LiteLLM error (gateway layer)
           - LiteLLMTimeoutError    — timeout subclass
           - EmbeddingError         — typed embedding error
           - ModelTestFailedError   — model-test failure (P02-S05-T002)

Key deps:
  - app.llm_gateway.litellm_client  (stream_chat, embed_query, StreamEvent)
  - app.llm_gateway.complete_chat   (complete_chat, CompletionResult)
  - app.llm_gateway.errors          (all typed errors)

Source refs:
  - task pack P02-S03-T002 §E.3 (gateway API contract)
  - task pack P02-S03-T002 §F.2 §K-LLM-GATEWAY (drift anchor)
  - task pack P02-S05-T002 §D.4 §D-LLMG-INIT (P02-S05-T002 extension)
  - /verify-slice P02-S05-T002 finding F1 (prompt leak via LiteLLM logger)
"""

import logging as _logging

# §D-LLMG-INIT-F1-LITELLM-LOGGER-LEVEL (P02-S05-T002): the LiteLLM SDK uses its
# own 'LiteLLM' logger (see litellm/_logging.py, utils.py:482) and emits
# 'Request to litellm: litellm.acompletion(model=..., messages=[...])' at
# DEBUG level. When backend/app/main.py sets logging.basicConfig(level=DEBUG)
# for ENABLE_VERBOSE_LOGGING=true our own loggers correctly stay at prompt_len
# only, but the 'LiteLLM' namespace inherits DEBUG from root and leaks the
# full prompt content. litellm.suppress_debug_info=True (litellm_client.py:67)
# only suppresses the library banner, NOT the Python logging output. Force the
# third-party logger to WARNING at import time so the leak is impossible
# regardless of how the application configures the root logger. Cross-cutting:
# applies to complete_chat (P02-S05-T002), stream_chat (P02-S03-T002) and
# embed_query (RAG) — every callsite goes through this namespace.
_logging.getLogger("LiteLLM").setLevel(_logging.WARNING)

# WRITE_SET_DRIFT §D-LLMG-INIT (P02-S05-T002): added complete_chat, CompletionResult,
# ModelTestFailedError exports. IN write_set (llm_gateway/**).
# noqa: E402 — imports are intentionally placed AFTER the LiteLLM logger level
# override above (§D-LLMG-INIT-F1-LITELLM-LOGGER-LEVEL) so the third-party
# logger is gated BEFORE the submodules import litellm.
from app.llm_gateway.complete_chat import CompletionResult, complete_chat  # noqa: E402
from app.llm_gateway.errors import (  # noqa: E402
    EmbeddingError,
    LiteLLMError,
    LiteLLMTimeoutError,
    ModelTestFailedError,
)
from app.llm_gateway.litellm_client import (  # noqa: E402
    StreamEvent,
    embed_query,
    stream_chat,
)

__all__ = [
    "stream_chat",
    "embed_query",
    "StreamEvent",
    "complete_chat",
    "CompletionResult",
    "LiteLLMError",
    "LiteLLMTimeoutError",
    "LiteLLMTimeoutError",
    "EmbeddingError",
    "ModelTestFailedError",
]
