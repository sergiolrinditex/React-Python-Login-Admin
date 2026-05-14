# Official Doc Note — P02-S05-T002 LiteLLM Non-Streaming Completion (Q1–Q5)
Date: 2026-05-13
Task: P02-S05-T002 (Model test and usage endpoints)
Sources:
  - https://docs.litellm.ai/docs/completion (acompletion non-streaming)
  - https://docs.litellm.ai/docs/exception_mapping (exception types)
  - https://docs.litellm.ai/docs/completion/token_usage (cost/usage)
  - https://docs.litellm.ai/docs/proxy/quick_start (proxy / api_base semantics)
  - Context7 /websites/litellm_ai (High, 16491 snippets, Benchmark 86)
  - P02-S03-T002 researcher note (confirmed streaming patterns — cross-reference)

---

## Q1 — Non-streaming completion shape

### Question
For `litellm==1.83.14`, what is the canonical signature and response shape of
`await litellm.acompletion(stream=False, ...)`?

### Answer

#### Call signature
```python
response = await litellm.acompletion(
    model="openai/gpt-4o-mini",           # "<provider_type>/<model_id>"
    messages=[{"role": "user", "content": "Hello"}],
    stream=False,                          # NON-streaming; returns ModelResponse directly
    api_key="sk-...",
    api_base="http://localhost:4000",      # optional; set when base_url override exists
    timeout=30,                            # optional; seconds
    max_tokens=256,                        # optional
)
```
Source: https://docs.litellm.ai/docs/completion — "completion() function signature"

#### Response shape (ModelResponse object)
```python
# Assistant text
text = response.choices[0].message.content   # str | None

# Token usage (always present on non-streaming responses)
tokens_in  = response.usage.prompt_tokens     # int
tokens_out = response.usage.completion_tokens # int
total      = response.usage.total_tokens      # int

# Model identifier as reported by provider
model_used = response.model    # str (may differ from requested model)

# Finish reason
finish_reason = response.choices[0].finish_reason  # "stop" | "length" | "tool_calls" | None
```
Source: https://docs.litellm.ai/docs/completion — "Response Object" section

#### Cost computation
```python
# Option 1 (preferred): hidden_params (populated for non-streaming on completion)
cost = response._hidden_params.get("response_cost", None)  # float | None

# Option 2 (fallback): litellm.completion_cost() with the response object
try:
    cost = litellm.completion_cost(completion_response=response)  # float | None
except Exception:
    cost = None  # Use pricing JSONB fallback
```
Source: https://docs.litellm.ai/docs/completion/token_usage — "Access the calculated response_cost"

#### stream_options on non-streaming?
`stream_options={"include_usage": True}` is a streaming-ONLY parameter.
Do NOT pass it when `stream=False`; it has no effect and may warn depending on provider.

RESOLVED: Confirmed — non-streaming acompletion returns usage directly in `response.usage`.
No `stream_options` needed. Text in `response.choices[0].message.content`.

---

## Q2 — Error taxonomy for non-streaming acompletion

### Question
What exception classes are raised for: (a) network/connection error, (b) timeout,
(c) rate-limit by provider, (d) invalid api_key, (e) model not found at provider?

### Answer

LiteLLM standardises all provider errors to OpenAI exception types (mapped uniformly).
For `acompletion(stream=False)` the full exception hierarchy is:

| Scenario | LiteLLM exception class | Inherits from | When |
|---|---|---|---|
| Connection / network error | `litellm.APIConnectionError` | `openai.APIConnectionError` | HTTP connect failed |
| Timeout | `litellm.Timeout` | `openai.APITimeoutError` | Request or response timeout |
| Provider rate-limit | `litellm.RateLimitError` | `openai.RateLimitError` | Provider returns 429 |
| Invalid api_key | `litellm.AuthenticationError` | `openai.AuthenticationError` | Provider returns 401/403 |
| Model not found at provider | `litellm.NotFoundError` | `openai.NotFoundError` | Provider returns 404 |
| Provider internal error | `litellm.InternalServerError` | `openai.InternalServerError` | Provider 5xx |
| Service unavailable | `litellm.ServiceUnavailableError` | `openai.APIStatusError` | Provider 503 |
| Generic API error | `litellm.APIError` | `openai.APIError` | Other provider errors |

Source: https://docs.litellm.ai/docs/exception_mapping — full exception mapping table

#### Mapping to our error types
- `litellm.Timeout` → wrap in `LiteLLMTimeoutError` (existing class) → 502 with status='timeout'
- All others → wrap in `ModelTestFailedError` (new class, subclass of LlmGatewayError) → 502

#### Pattern for complete_chat.py
```python
import litellm
try:
    response = await litellm.acompletion(...)
except litellm.Timeout as exc:
    raise LiteLLMTimeoutError(...) from exc
except Exception as exc:
    raise ModelTestFailedError(...) from exc
```

RESOLVED: Confirmed — catch `litellm.Timeout` first for timeout path; all other exceptions
(including `AuthenticationError`, `NotFoundError`, `RateLimitError`, `InternalServerError`,
`APIConnectionError`) map to `ModelTestFailedError` → HTTP 502.

---

## Q3 — Dry-run / preview flag on acompletion

### Question
Does LiteLLM v1.83.14 expose a "dry-run" or "preview" flag that returns shape without billing?

### Answer
**NO.** LiteLLM v1.83.14 does NOT expose any `dry_run`, `preview`, or `mock` flag on
`acompletion()`. A call ALWAYS produces a real provider invocation and uses tokens.

The only approach for testing without billing is to:
1. Use the LiteLLM Proxy with a `mock_response` model configured (proxy-level feature).
2. Mock `litellm.acompletion` at the Python function level in tests.

For production use (the `/test` endpoint): a REAL call is made. The sandbox qualifier
refers to using the local `localhost:4000` LiteLLM proxy which itself points to a
sandboxed/verification model.

For test isolation: mock at the litellm boundary (acceptable per non-negotiables §AI/ML).

RESOLVED: Confirmed — no dry-run flag. Real call model stands for the endpoint.
Tests mock at `litellm.acompletion` Python boundary.

---

## Q4 — Cost when completion_cost() returns None

### Question
On which providers/models does `litellm.completion_cost()` NOT compute cost, requiring
our pricing JSONB fallback?

### Answer
`litellm.completion_cost()` returns `None` (or raises) when:
1. **Provider not in LiteLLM's cost map** — e.g. self-hosted Ollama models, custom LiteLLM
   proxy models with no pricing entry.
2. **Model name unknown to LiteLLM** — e.g. a fine-tuned model with a custom ID not in
   the built-in `model_prices_and_context_window.json`.
3. **Provider returns malformed usage** — rare but happens with some Azure deployments.

Confirmed pattern: wrap in try/except, fall back to `_estimate_cost_from_pricing(model, tokens_in, tokens_out)`.
The existing implementation in `litellm_client.py` already uses this pattern (D-COST1).

RESOLVED: Confirmed — try `litellm.completion_cost(completion_response=resp)` first;
if it raises or returns None/0.0, use `_estimate_cost_from_pricing(model, tokens_in, tokens_out)`.
This pattern is already in litellm_client.py and is correctly reused in complete_chat.py.

---

## Q5 — OpenAI vs LiteLLM proxy api_key semantics

### Question
When `provider.base_url=http://localhost:4000` (LiteLLM proxy) vs no base_url (real OpenAI),
is the api_key semantics identical? Any header differences?

### Answer
**Yes, semantics are identical** from the LiteLLM SDK perspective:
- `api_key` is always passed as `Authorization: Bearer <api_key>` in the HTTP request.
- When `api_base="http://localhost:4000"`, the proxy receives the Bearer token and uses
  its own routing/config to make the upstream call. The proxy may override or ignore the
  api_key depending on configuration.
- No extra headers are needed for the proxy path vs the direct OpenAI path.
- The model string format `"<provider_type>/<model_id>"` is interpreted by LiteLLM SDK;
  with `api_base` set, LiteLLM routes to that base URL using the OpenAI-compatible API.

Source: https://docs.litellm.ai/docs/proxy/quick_start — "Using the LiteLLM Proxy as a drop-in
replacement for OpenAI. Same api_key, same api_base pattern."

Special case: if `api_key="sk-litellm-test"` (a fake key), the proxy may accept it
depending on proxy auth config. Our test fixture uses `credential_plain="sk-test"` and
the mock at the LiteLLM boundary bypasses the actual HTTP call anyway.

RESOLVED: Confirmed — api_key semantics identical between proxy and direct.
No header differences. `complete_chat.py` handles both paths with the same kwargs dict,
passing `api_base` only when `provider.base_url` is set.

---

## Summary — All 5 questions RESOLVED

| Q | Status | Action |
|---|---|---|
| Q1 | RESOLVED | Non-streaming: `resp.choices[0].message.content`, `resp.usage.prompt_tokens/completion_tokens`, no `stream_options` |
| Q2 | RESOLVED | Catch `litellm.Timeout` → `LiteLLMTimeoutError`; all others → `ModelTestFailedError` |
| Q3 | RESOLVED | No dry-run flag; mock at `litellm.acompletion` boundary in tests |
| Q4 | RESOLVED | `completion_cost()` → try/except → fallback to `_estimate_cost_from_pricing` |
| Q5 | RESOLVED | api_key semantics identical; no extra headers for proxy path |

No discrepancies found with internal source-of-truth docs.
Implementation can proceed with `complete_chat.py` as specified in §D-LLMG-COMPLETE.
