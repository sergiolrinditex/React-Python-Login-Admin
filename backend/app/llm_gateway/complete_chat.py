"""
Hilo People — LiteLLM non-streaming single-completion helper.

WRITE_SET_DRIFT §D-LLMG-COMPLETE (P02-S05-T002): Non-streaming completion
helper for the admin model-test endpoint. In write_set (`llm_gateway/**`).

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features (the motor)
Purpose: Thin async wrapper around litellm.acompletion(stream=False) that:
  - Accepts model/provider ORM instances + a plain-text api_key (never logged).
  - Returns a typed CompletionResult dataclass with text, tokens, cost, latency.
  - Wraps litellm exceptions into LiteLLMTimeoutError / ModelTestFailedError.
  - Redacts prompt content from all log lines (only logs prompt_len).

Public API:
  - complete_chat(*) -> CompletionResult
  - CompletionResult  — typed result dataclass

Researcher-confirmed shapes (P02-S05-T002 Q1–Q5):
  - resp.choices[0].message.content — assistant text
  - resp.usage.prompt_tokens / resp.usage.completion_tokens — token counts
  - litellm.completion_cost(completion_response=resp) — cost (try/except fallback)
  - litellm.Timeout → LiteLLMTimeoutError (status='timeout')
  - All other exceptions → ModelTestFailedError (status='failure')
  - No stream_options needed for non-streaming
  - api_key semantics identical for proxy and direct OpenAI paths

Security:
  - api_key NEVER logged.
  - prompt content NEVER logged — only prompt_len is logged.
  - output/completion content NEVER logged.

Key deps:
  - litellm==1.83.14
  - app.db.models.admin_ai (AiModel, AiProvider)
  - app.llm_gateway.errors (LiteLLMTimeoutError, ModelTestFailedError)

Source refs:
  - task pack P02-S05-T002 §D.4 §D-LLMG-COMPLETE
  - task pack P02-S05-T002 §G Q1–Q5 (researcher confirmed)
  - 01-non-negotiables.md §AI/ML libraries (volatile — researcher confirmed)
  - 01-non-negotiables.md §Security (NEVER log api_key or prompt content)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass

import litellm

from app.db.models.admin_ai import AiModel, AiProvider
from app.llm_gateway.errors import LiteLLMTimeoutError, ModelTestFailedError
from app.llm_gateway.litellm_client import _estimate_cost_from_pricing  # D-COST1 fallback

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# Default timeout for non-streaming model test calls (seconds).
_DEFAULT_TIMEOUT = 60


@dataclass(frozen=True)
class CompletionResult:
    """Typed result of a non-streaming LLM completion call.

    Attributes:
        text:              Assistant response text.
        prompt_tokens:     Number of prompt (input) tokens consumed.
        completion_tokens: Number of completion (output) tokens generated.
        total_tokens:      Total tokens (prompt + completion).
        cost_usd:          Estimated cost in USD; None if provider pricing unknown.
        latency_ms:        Wall-clock latency in milliseconds.
        model_used:        Model identifier as reported by the provider.
        finish_reason:     Provider finish reason ('stop', 'length', etc.).
    """

    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    latency_ms: int
    model_used: str
    finish_reason: str


async def complete_chat(
    *,
    model: AiModel,
    provider: AiProvider,
    api_key: str,
    prompt: str,
    max_tokens: int = 256,
    timeout: int = _DEFAULT_TIMEOUT,
    request_id: str,
) -> CompletionResult:
    """Perform a single non-streaming completion call against the LLM provider.

    Wraps litellm.acompletion(stream=False). Returns a typed CompletionResult.
    Never logs prompt content or api_key. Only logs prompt_len and metadata.

    Args:
        model:      AiModel ORM instance (pricing JSONB, model_id, model_type).
        provider:   AiProvider ORM instance (provider_type, base_url).
        api_key:    Decrypted plain-text API key — NEVER log this value.
        prompt:     The user prompt text — NEVER log content, only log length.
        max_tokens: Maximum completion tokens (default 256).
        timeout:    Request timeout in seconds (default 60).
        request_id: X-Request-ID for log correlation.

    Returns:
        CompletionResult with text, tokens, cost, latency, model, finish_reason.

    Raises:
        LiteLLMTimeoutError:  Provider connection or inference timed out.
        ModelTestFailedError: Any other litellm / provider failure.
    """
    model_str = f"{provider.provider_type}/{model.model_id}"
    prompt_len = len(prompt)
    t0 = time.perf_counter()

    if _VERBOSE:
        logger.debug(
            "llm_gateway.complete_chat.start request_id=%s model_str=%s "
            "prompt_len=%d max_tokens=%d",
            request_id,
            model_str,
            prompt_len,
            max_tokens,
        )  # BEFORE — prompt CONTENT never logged

    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {
        "model": model_str,
        "messages": messages,
        "stream": False,
        "api_key": api_key,        # NEVER in logs
        "timeout": timeout,
        "max_tokens": max_tokens,
        # stream_options is ONLY for stream=True (Q1 researcher confirmed)
    }
    if provider.base_url:
        kwargs["api_base"] = provider.base_url

    try:
        response = await litellm.acompletion(**kwargs)
    except (asyncio.TimeoutError, litellm.Timeout) as exc:  # type: ignore[attr-defined]
        latency_ms = int((time.perf_counter() - t0) * 1000)
        logger.error(
            "llm_gateway.complete_chat.timeout request_id=%s model_str=%s "
            "latency_ms=%d",
            request_id,
            model_str,
            latency_ms,
        )  # ERROR — no prompt content, no api_key
        raise LiteLLMTimeoutError(
            f"LiteLLM timeout for {model_str} after {latency_ms}ms",
            cause=exc,
        ) from exc
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        logger.error(
            "llm_gateway.complete_chat.error request_id=%s model_str=%s "
            "error=%s latency_ms=%d",
            request_id,
            model_str,
            type(exc).__name__,
            latency_ms,
        )  # ERROR — only exception type (no message that may contain secrets)
        raise ModelTestFailedError(
            f"LiteLLM invocation failed for {model_str}: {type(exc).__name__}",
            cause=exc,
            status="failure",
        ) from exc

    latency_ms = int((time.perf_counter() - t0) * 1000)

    # Extract text from the response (Q1 researcher confirmed shape).
    try:
        text = response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        text = ""

    # Extract token usage (always present on non-streaming, Q1 confirmed).
    tokens_in = 0
    tokens_out = 0
    total_tokens = 0
    try:
        usage = response.usage
        if usage is not None:
            tokens_in = getattr(usage, "prompt_tokens", 0) or 0
            tokens_out = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or (tokens_in + tokens_out)
    except AttributeError:
        pass

    # Extract finish reason.
    finish_reason = "stop"
    try:
        finish_reason = response.choices[0].finish_reason or "stop"
    except (AttributeError, IndexError):
        pass

    # Extract model as reported by provider.
    model_used = model_str
    try:
        model_used = response.model or model_str
    except AttributeError:
        pass

    # Compute cost (Q4: try litellm.completion_cost first; fallback to pricing JSONB).
    cost_usd = _extract_cost(response, model, tokens_in, tokens_out)

    if _VERBOSE:
        logger.debug(
            "llm_gateway.complete_chat.ok request_id=%s model_str=%s "
            "tokens_in=%d tokens_out=%d cost_usd=%s latency_ms=%d finish=%s",
            request_id,
            model_str,
            tokens_in,
            tokens_out,
            str(cost_usd),
            latency_ms,
            finish_reason,
        )  # AFTER — no output content, no api_key
    else:
        logger.info(
            "llm_gateway.complete_chat.ok request_id=%s model_str=%s "
            "latency_ms=%d tokens_in=%d tokens_out=%d",
            request_id,
            model_str,
            latency_ms,
            tokens_in,
            tokens_out,
        )

    return CompletionResult(
        text=text,
        prompt_tokens=tokens_in,
        completion_tokens=tokens_out,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        model_used=model_used,
        finish_reason=finish_reason,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_cost(
    response: object,
    model: AiModel,
    tokens_in: int,
    tokens_out: int,
) -> float | None:
    """Try to extract cost from the litellm response; fall back to pricing JSONB.

    Tries two approaches per Q4 researcher confirmation:
    1. litellm.completion_cost(completion_response=response)
    2. _estimate_cost_from_pricing(model, tokens_in, tokens_out) (pricing JSONB fallback)

    Args:
        response:   ModelResponse object from litellm.acompletion.
        model:      AiModel ORM instance with pricing JSONB.
        tokens_in:  Input token count.
        tokens_out: Output token count.

    Returns:
        Float USD cost, or None if not determinable.
    """
    # Option 1: litellm.completion_cost (preferred, may return 0.0 or None for unknown models)
    try:
        cost = litellm.completion_cost(completion_response=response)
        if cost is not None and cost > 0.0:
            return float(cost)
    except Exception:
        pass

    # Option 2: pricing JSONB fallback via imported helper (D-COST1, DRY — reuses
    # litellm_client._estimate_cost_from_pricing, no duplication).
    estimated = _estimate_cost_from_pricing(model, tokens_in, tokens_out)
    if estimated > 0.0:
        return estimated

    return None
