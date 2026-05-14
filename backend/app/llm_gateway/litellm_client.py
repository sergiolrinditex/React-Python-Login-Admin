"""
Hilo People — LiteLLM-backed LLM gateway (stream + embed).

Slice:  P02-S03-T002 — Chat streaming endpoint (new module §K-LLM-GATEWAY)
        P02-S03-T006 — Fix model_str composition: introduce _compose_sdk_model_args helper
Phase:  P02 Core Features (the motor)
Purpose: Thin async adapter over litellm.acompletion (streaming) and
         litellm.aembedding. Translates provider-specific shapes into
         typed StreamEvent dataclasses. Callers never import litellm directly.

Public API:
  - stream_chat(*) -> AsyncIterator[StreamEvent]   — streaming text generation
  - embed_query(*) -> list[float]                  — 1536-dim query embedding
  - StreamEvent                                    — typed event dataclass

LiteLLM routing:
  - model string format: "<sdk_prefix>/<model_id>" where sdk_prefix is determined
    by _compose_sdk_model_args() from provider.provider_type (D-LITELLM-PROVIDER-MAP).
    Example: provider_type='litellm' → model='openai/gpt-4o-mini' + api_base=proxy_url.
  - api_key is passed per-call (decrypted by caller from AiProviderCredential)
  - api_base is passed when AiProvider.base_url is set (for self-hosted / litellm proxy)

Security:
  - api_key NEVER logged (see D-ENC3 in app.security.encryption).
  - prompt / completion content NEVER logged (PII/confidentiality).
  - Only model_id, provider_type, lengths, token counts logged.

Source refs:
  - task pack P02-S03-T002 §E.3 (gateway API contract)
  - task pack P02-S03-T002 §M.1-M.3 (researcher questions: streaming shape, embed shape)
  - task pack P02-S03-T006 §ROOT_CAUSE + §DECISIONS_TO_RECORD
  - official-doc-notes/P02-S03-T006-litellm-provider-map-2026-05-14.md (Q1–Q5 resolved)
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
  - D-LITELLM-PROVIDER-MAP (P02-S03-T006): Canonical mapping from AiProvider.provider_type
    to LiteLLM SDK prefix. Single source of truth in _PROVIDER_TYPE_TO_SDK_PREFIX dict.
    Applied via _compose_sdk_model_args() used by ALL call sites in this module.
  - D-T006-COMPOSE-HELPER (P02-S03-T006): Both stream_chat and embed_query route through
    _compose_sdk_model_args(). complete_chat.py adoption deferred to follow-up (Option A).
  - D-T006-LIVE-TEST-GATE (P02-S03-T006): Live integration test gated by LITELLM_PROXY_UP=1.
    CI default = SKIPPED. /verify-slice exports it after hard reset + real data load.
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

# ---------------------------------------------------------------------------
# Provider mapping — D-LITELLM-PROVIDER-MAP (P02-S03-T006)
# ---------------------------------------------------------------------------

# Maps AiProvider.provider_type (DB value) → LiteLLM SDK model string prefix.
# Root cause of P02-S03-T006: the old code used f"{provider.provider_type}/{model.model_id}"
# which sent model="litellm/gpt-4o-mini" to the SDK — a non-existent prefix that raises
# BadRequestError("LLM Provider NOT provided").
#
# The LiteLLM proxy (provider_type='litellm') is OpenAI-compatible and must be addressed
# with model="openai/<model_id>" + api_base=<proxy_url>.
#
# Source: official-doc-notes/P02-S03-T006-litellm-provider-map-2026-05-14.md Q1+Q5 RESOLVED.
# Update this dict when adding new provider types — do NOT duplicate inline.
_PROVIDER_TYPE_TO_SDK_PREFIX: dict[str, str] = {
    "litellm": "openai",  # LiteLLM proxy is OpenAI-compatible; api_base routes to proxy
    "openai": "openai",  # Direct OpenAI or custom OpenAI-compatible endpoint
    "anthropic": "anthropic",  # Direct Anthropic
    "azure_openai": "azure",  # Azure OpenAI; also needs api_base=<azure-endpoint>
    "ollama": "ollama",  # Local Ollama server; also needs api_base=<local-url>
    "groq": "groq",  # Groq cloud
    "together_ai": "together_ai",  # Together AI
    "mistral": "mistral",  # Mistral AI
    "cohere": "cohere",  # Cohere
}

# provider_type values that REQUIRE api_base to be set (raise if not configured).
# 'openai' is NOT here because it has a sensible default (api.openai.com);
# custom base_url for openai is optional.
_REQUIRE_BASE_URL: frozenset[str] = frozenset({"litellm", "azure_openai", "ollama"})


def _compose_sdk_model_args(
    provider: "AiProvider",
    model: "AiModel",
    request_id: str = "",
) -> tuple[str, dict[str, str]]:
    """Compose the SDK-valid model string and extra kwargs for a LiteLLM call.

    Single source of truth for provider_type → SDK prefix mapping (D-LITELLM-PROVIDER-MAP).
    All call sites in this module MUST use this helper — never compose model_str inline.

    Args:
        provider: AiProvider ORM instance (provider_type, base_url).
        model: AiModel ORM instance (model_id).
        request_id: X-Request-ID for log correlation (empty string if unavailable).

    Returns:
        Tuple of (model_str, extra_kwargs) where:
          model_str: SDK-valid prefixed string, e.g. "openai/gpt-4o-mini".
          extra_kwargs: dict of additional kwargs to merge into the acompletion/aembedding call.
                        May include {"api_base": url}. Never includes api_key.

    Raises:
        LiteLLMError: If provider_type is unknown (explicit failure is safer than wrong routing).
    """
    provider_type: str = provider.provider_type or ""
    model_id: str = model.model_id or ""
    base_url: str | None = provider.base_url or None

    if _VERBOSE:
        logger.debug(
            "llm_gateway.compose.start request_id=%s provider_type=%s model_id=%s"
            " base_url_present=%s",
            request_id,
            provider_type,
            model_id,
            base_url is not None,
        )  # BEFORE

    sdk_prefix = _PROVIDER_TYPE_TO_SDK_PREFIX.get(provider_type)

    if sdk_prefix is None:
        logger.error(
            "llm_gateway.compose.unsupported_provider_type request_id=%s provider_type=%s",
            request_id,
            provider_type,
        )  # ERROR — always visible
        raise LiteLLMError(
            f"Unsupported provider_type='{provider_type}'. "
            "Add it to _PROVIDER_TYPE_TO_SDK_PREFIX in litellm_client.py.",
        )

    model_str = f"{sdk_prefix}/{model_id}"
    extra_kwargs: dict[str, str] = {}

    # api_base rules (D-LITELLM-PROVIDER-MAP):
    #   - litellm/azure_openai/ollama: always require base_url; pass it as api_base.
    #   - openai with base_url set: pass api_base (custom OpenAI-compatible endpoint).
    #   - others: pass api_base only when explicitly set on the provider row.
    if provider_type in _REQUIRE_BASE_URL:
        if base_url:
            extra_kwargs["api_base"] = base_url
        # Missing base_url for required providers: log warning; the SDK call will fail with
        # a useful error rather than silently routing to the wrong endpoint.
        elif _VERBOSE:
            logger.warning(
                "llm_gateway.compose.missing_base_url request_id=%s provider_type=%s"
                " — base_url is required but not set on the provider row",
                request_id,
                provider_type,
            )
    elif base_url:
        extra_kwargs["api_base"] = base_url

    if _VERBOSE:
        logger.debug(
            "llm_gateway.compose.done request_id=%s sdk_provider=%s model_str=%s"
            " api_base_present=%s",
            request_id,
            sdk_prefix,
            model_str,
            "api_base" in extra_kwargs,
        )  # AFTER — never log api_key value, never log full api_base if it contains tokens

    return model_str, extra_kwargs


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
    # D-T006-COMPOSE-HELPER: compose via helper — single source of truth for provider mapping.
    model_str, sdk_extra = _compose_sdk_model_args(provider, model, request_id)
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
        **sdk_extra,  # may include api_base; never includes api_key
    }

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
            f"LiteLLM connection failed for {model_str}: {type(exc).__name__}",
            cause=exc,
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
    # D-T006-COMPOSE-HELPER: compose via helper — single source of truth for provider mapping.
    model_str, sdk_extra = _compose_sdk_model_args(provider, model, request_id)

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
        **sdk_extra,  # may include api_base; never includes api_key
    }

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


def _estimate_cost_from_pricing(
    model: AiModel, tokens_in: int, tokens_out: int
) -> float:
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
