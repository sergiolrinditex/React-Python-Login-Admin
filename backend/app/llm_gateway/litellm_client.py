"""
Hilo People — LiteLLM-backed LLM gateway (stream + embed).

Slice:  P02-S03-T002 — Chat streaming endpoint (new module §K-LLM-GATEWAY)
Phase:  P02 Core Features (the motor)
Purpose: Thin async adapter over litellm.acompletion (streaming) and
         litellm.aembedding. Translates provider-specific shapes into
         typed StreamEvent dataclasses. Callers never import litellm directly.

Public API:
  - stream_chat(*) -> AsyncIterator[StreamEvent]   — streaming text generation
  - embed_query(*) -> list[float]                  — 1536-dim query embedding
  - StreamEvent                                    — typed event dataclass

LiteLLM routing:
  - model string format: "<provider_type>/<model_id>" (e.g. "openai/gpt-4o")
  - api_key is passed per-call (decrypted by caller from AiProviderCredential)
  - api_base is passed when AiProvider.base_url is set (for self-hosted / litellm proxy)

Security:
  - api_key NEVER logged (see D-ENC3 in app.security.encryption).
  - prompt / completion content NEVER logged (PII/confidentiality).
  - Only model_id, provider_type, lengths, token counts logged.

Source refs:
  - task pack P02-S03-T002 §E.3 (gateway API contract)
  - task pack P02-S03-T002 §M.1-M.3 (researcher questions: streaming shape, embed shape)
  - 01-non-negotiables.md §AI/ML libraries (volatile — use researcher-confirmed patterns)
  - litellm==1.83.14 docs (https://docs.litellm.ai/docs/streaming)

Decisions:
  - D-STREAM1: litellm.acompletion(..., stream=True) returns an async iterator directly
    after the initial await. Each chunk is a ModelResponse; content is in
    chunk.choices[0].delta.content (None for non-text chunks). Usage arrives in
    the last chunk (or via stream_options={"include_usage": True} on OpenAI).
    We request stream_options for OpenAI-compat providers; for others we rely on
    the last chunk having usage.
  - D-EMBED1: litellm.aembedding returns EmbeddingResponse; data[0].embedding is the
    1536-dim float list. Dimension is enforced client-side (raises EmbeddingError).
  - D-COST1: response_cost from litellm completion_cost() after stream end. If not
    available, fallback to pricing dict on AiModel (D-CHATSTREAM-COST from pack).
  - D-CANCEL1: On asyncio.CancelledError or StopAsyncIteration we aclose() the
    async iterator if it has an aclose() method (avoids HTTP/2 stream leak).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

import litellm

from app.db.models.admin_ai import AiModel, AiProvider
from app.llm_gateway.errors import EmbeddingError, LiteLLMError, LiteLLMTimeoutError

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# Expected embedding dimension (text-embedding-3-small default).
_EXPECTED_EMBED_DIM = 1536

# Suppress litellm's own verbose output unless we are in verbose mode.
litellm.suppress_debug_info = True


@dataclass(frozen=True)
class StreamEvent:
    """Typed event yielded by stream_chat().

    kind values:
      'delta'   — incremental text chunk: payload = {"delta": "<text>"}
      'usage'   — token/cost accounting:  payload = {"tokens_in":int, "tokens_out":int,
                                                       "estimated_cost":float, "latency_ms":int}
      'error'   — fatal mid-stream error: payload = {"code": str, "message": str}

    Attributes:
        kind: Event type (delta | usage | error).
        payload: Event-specific data dict.
    """

    kind: str
    payload: dict[str, Any]


async def stream_chat(
    *,
    model: AiModel,
    provider: AiProvider,
    api_key: str,
    messages: list[dict[str, str]],
    request_id: str,
) -> AsyncIterator[StreamEvent]:
    """Async generator yielding StreamEvent records from the LLM provider.

    Wraps litellm.acompletion with stream=True. Handles provider routing,
    usage extraction, and error translation.

    Args:
        model: AiModel ORM instance (contains model_id, model_type, pricing).
        provider: AiProvider ORM instance (contains provider_type, base_url).
        api_key: Decrypted plain-text API key — NEVER log this value.
        messages: List of {"role": "...", "content": "..."} dicts (OpenAI-compat format).
        request_id: X-Request-ID for log correlation.

    Yields:
        StreamEvent(kind='delta', payload={"delta": str})
        StreamEvent(kind='usage', payload={"tokens_in": int, "tokens_out": int,
                                            "estimated_cost": float, "latency_ms": int})
        StreamEvent(kind='error', payload={"code": str, "message": str})

    Raises:
        LiteLLMTimeoutError: If the provider connection/inference times out.
        LiteLLMError: For any other litellm / provider failure.
    """
    model_str = f"{provider.provider_type}/{model.model_id}"
    t0 = time.perf_counter()

    if _VERBOSE:
        logger.debug(
            "llm_gateway.stream_chat.start request_id=%s model_str=%s msg_count=%d",
            request_id,
            model_str,
            len(messages),
        )  # BEFORE

    kwargs: dict[str, Any] = {
        "model": model_str,
        "messages": messages,
        "stream": True,
        "api_key": api_key,
        "stream_options": {"include_usage": True},
    }
    if provider.base_url:
        kwargs["api_base"] = provider.base_url

    response = None
    try:
        response = await litellm.acompletion(**kwargs)
    except asyncio.TimeoutError as exc:
        logger.error(
            "llm_gateway.stream_chat.timeout request_id=%s model_str=%s",
            request_id,
            model_str,
        )
        raise LiteLLMTimeoutError(
            f"LiteLLM timeout connecting to {model_str}", cause=exc
        ) from exc
    except Exception as exc:
        logger.error(
            "llm_gateway.stream_chat.connect_error request_id=%s model_str=%s error=%s",
            request_id,
            model_str,
            type(exc).__name__,
        )
        raise LiteLLMError(
            f"LiteLLM connection failed for {model_str}: {type(exc).__name__}", cause=exc
        ) from exc

    tokens_in = 0
    tokens_out = 0
    estimated_cost = 0.0

    try:
        async for chunk in response:
            # Extract delta content (None for non-text chunks like role/tool_calls).
            delta_text: str | None = None
            try:
                delta_text = chunk.choices[0].delta.content
            except (AttributeError, IndexError):
                pass

            if delta_text:
                yield StreamEvent(kind="delta", payload={"delta": delta_text})

            # Extract usage from chunk (last chunk usually, or stream_options usage).
            try:
                usage = chunk.usage
                if usage is not None:
                    tokens_in = getattr(usage, "prompt_tokens", 0) or 0
                    tokens_out = getattr(usage, "completion_tokens", 0) or 0
                    # Try litellm response_cost (D-COST1).
                    try:
                        estimated_cost = float(
                            litellm.completion_cost(completion_response=chunk) or 0.0
                        )
                    except Exception:
                        estimated_cost = _estimate_cost_from_pricing(
                            model, tokens_in, tokens_out
                        )
            except AttributeError:
                pass

    except asyncio.CancelledError:
        if _VERBOSE:
            logger.debug(
                "llm_gateway.stream_chat.cancelled request_id=%s model_str=%s",
                request_id,
                model_str,
            )
        await _safe_aclose(response)
        raise
    except Exception as exc:
        logger.error(
            "llm_gateway.stream_chat.mid_stream_error request_id=%s model_str=%s error=%s",
            request_id,
            model_str,
            type(exc).__name__,
        )
        await _safe_aclose(response)
        yield StreamEvent(
            kind="error",
            payload={"code": "LITELLM_MID_STREAM_ERROR", "message": type(exc).__name__},
        )
        return

    latency_ms = int((time.perf_counter() - t0) * 1000)

    if _VERBOSE:
        logger.debug(
            "llm_gateway.stream_chat.done request_id=%s model_str=%s "
            "tokens_in=%d tokens_out=%d latency_ms=%d",
            request_id,
            model_str,
            tokens_in,
            tokens_out,
            latency_ms,
        )  # AFTER

    yield StreamEvent(
        kind="usage",
        payload={
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "estimated_cost": estimated_cost,
            "latency_ms": latency_ms,
        },
    )


async def embed_query(
    *,
    model: AiModel,
    provider: AiProvider,
    api_key: str,
    text: str,
    request_id: str,
) -> list[float]:
    """Compute the embedding vector for a query string.

    Uses litellm.aembedding. The returned vector is expected to be 1536-dim
    (text-embedding-3-small default). Raises EmbeddingError if the dimension
    is wrong or the call fails.

    Args:
        model: AiModel ORM instance for the embeddings model.
        provider: AiProvider ORM instance.
        api_key: Decrypted plain-text API key — NEVER log.
        text: The query string to embed. NOT logged (PII).
        request_id: X-Request-ID for log correlation.

    Returns:
        1536-dim float list (or provider default; dimension validated).

    Raises:
        EmbeddingError: If embedding fails or dimension mismatches.
    """
    model_str = f"{provider.provider_type}/{model.model_id}"

    if _VERBOSE:
        logger.debug(
            "llm_gateway.embed_query.start request_id=%s model_str=%s text_len=%d",
            request_id,
            model_str,
            len(text),
        )  # BEFORE

    kwargs: dict[str, Any] = {
        "model": model_str,
        "input": [text],
        "api_key": api_key,
    }
    if provider.base_url:
        kwargs["api_base"] = provider.base_url

    try:
        result = await litellm.aembedding(**kwargs)
        vector: list[float] = result.data[0].embedding

        if len(vector) != _EXPECTED_EMBED_DIM:
            raise EmbeddingError(
                f"Unexpected embedding dimension {len(vector)}, expected {_EXPECTED_EMBED_DIM}",
            )

        if _VERBOSE:
            logger.debug(
                "llm_gateway.embed_query.done request_id=%s model_str=%s dim=%d",
                request_id,
                model_str,
                len(vector),
            )  # AFTER

        return vector

    except EmbeddingError:
        raise
    except asyncio.TimeoutError as exc:
        logger.error(
            "llm_gateway.embed_query.timeout request_id=%s model_str=%s",
            request_id,
            model_str,
        )
        raise EmbeddingError("Embedding request timed out.", cause=exc) from exc
    except Exception as exc:
        logger.error(
            "llm_gateway.embed_query.error request_id=%s model_str=%s error=%s",
            request_id,
            model_str,
            type(exc).__name__,
        )
        raise EmbeddingError(
            f"Embedding failed for {model_str}: {type(exc).__name__}", cause=exc
        ) from exc


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _estimate_cost_from_pricing(model: AiModel, tokens_in: int, tokens_out: int) -> float:
    """Fallback cost estimate from ai_models.pricing JSONB (D-COST1).

    Args:
        model: AiModel with pricing JSONB {input_cost_per_token, output_cost_per_token}.
        tokens_in: Input token count.
        tokens_out: Output token count.

    Returns:
        Estimated USD cost as float (0.0 if pricing data not available).
    """
    pricing = model.pricing or {}
    in_cost = float(pricing.get("input_cost_per_token", 0.0))
    out_cost = float(pricing.get("output_cost_per_token", 0.0))
    return in_cost * tokens_in + out_cost * tokens_out


async def _safe_aclose(response: Any) -> None:
    """Close the async iterator if it has an aclose() method (D-CANCEL1).

    Prevents HTTP/2 stream leaks when we break out of an async for loop.

    Args:
        response: The litellm async iterator (or any aclose()-able object).
    """
    try:
        if response is not None and hasattr(response, "aclose"):
            await response.aclose()
    except Exception:
        pass  # Best-effort; never let cleanup errors propagate.
