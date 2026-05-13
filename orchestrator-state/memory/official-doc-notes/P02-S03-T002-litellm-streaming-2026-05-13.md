# Official Doc Note — P02-S03-T002 LiteLLM Streaming (M.1 + M.2 + M.3)
Date: 2026-05-13
Task: P02-S03-T002 (Chat streaming endpoint)
Sources:
  - https://docs.litellm.ai/docs/completion/stream (streaming patterns)
  - https://docs.litellm.ai/stream (stream_options usage)
  - https://docs.litellm.ai/docs/completion/token_usage (cost/usage)
  - https://docs.litellm.ai/docs/exception_mapping (exception types)
  - https://docs.litellm.ai/docs/observability/custom_callback (response_cost callback)
  - https://github.com/BerriAI/litellm/blob/main/litellm/litellm_core_utils/streaming_handler.py (source)
  - Context7 /websites/litellm_ai (High, 16491 snippets, Benchmark 86)

---

## M.1 — acompletion(stream=True): async iterator, delta extraction, usage, cost

### Question
Exact async iteration pattern, delta text extraction, usage (tokens_in/out) location, and cost
field for streaming acompletion.

### Answer

#### Async iteration (official pattern)
```python
response = await litellm.acompletion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True,
    stream_options={"include_usage": True},   # required for usage on last chunk
)
async for chunk in response:
    delta = chunk.choices[0].delta.content or ""
    # usage available only on the final usage chunk (choices == [])
    if chunk.usage is not None:
        tokens_in  = chunk.usage.prompt_tokens
        tokens_out = chunk.usage.completion_tokens
```

Source: https://docs.litellm.ai/docs/completion/stream — "async for chunk in response: print(chunk)"
Source: https://docs.litellm.ai/stream — "chunk.choices[0].delta.content"

#### Usage / stream_options
- Must pass `stream_options={"include_usage": True}` to get usage on the final chunk.
- Official docs: "an additional chunk will be streamed before the data: [DONE] message. The
  usage field on this chunk shows the token usage statistics for the entire request, and the
  choices field will always be an empty array. All other chunks will also include a usage field,
  but with a null value."
- Guard: detect usage chunk by `chunk.usage is not None` (or `chunk.choices == []`).
- "Supported across all providers. Works the same as openai." — cross-provider (OpenAI, Anthropic,
  Azure) uses the same abstraction.

Source: https://docs.litellm.ai/stream — "Streaming Token Usage" section

#### Cost / response_cost
Two approaches confirmed:

1. **`_hidden_params["response_cost"]`** — available on the completed response object:
   ```python
   response._hidden_params["response_cost"]  # float, USD
   ```
   Source: https://docs.litellm.ai/docs/completion/token_usage — "Access the calculated response
   cost directly from the completion response object."

2. **Success callback `kwargs["response_cost"]`** — for streaming, use a success callback:
   ```python
   def track_cost_callback(kwargs, completion_response, start_time, end_time):
       response_cost = kwargs.get("response_cost", 0)
   litellm.success_callback = [track_cost_callback]
   ```
   Source: https://docs.litellm.ai/docs/observability/custom_callback

3. **`litellm.completion_cost()`** — can compute from accumulated prompt+completion strings:
   ```python
   cost = litellm.completion_cost(model="gpt-3.5-turbo", prompt=prompt, completion=content)
   ```
   Or use `stream_chunk_builder(chunks)` to reconstruct response then read `._hidden_params["response_cost"]`.

**Recommended pattern for P02-S03-T002**: use `stream_options={"include_usage": True}` to get
`tokens_in` / `tokens_out` from the final chunk, then call `litellm.completion_cost()` with the
model name and token counts — or read `_hidden_params["response_cost"]` if LiteLLM populates it
after stream ends (confirmed pattern via callback). Do NOT depend on `_hidden_params` being set
synchronously during iteration; prefer `completion_cost()` post-stream.

### Status
ASSUMPTION_CONFIRMED — the task pack assumes `stream_options={"include_usage": True}` and
`chunk.choices[0].delta.content` pattern. Both confirmed correct by official docs.

The pack writes `tokens_in`, `tokens_out` to `llm_usage_logs`. Confirmed: use final chunk's
`chunk.usage.prompt_tokens` / `chunk.usage.completion_tokens` after detecting usage chunk.

---

## M.2 — LiteLLM mid-stream errors, cancellation, timeouts

### Question
Typed exceptions fired mid-stream, clean cancellation on client disconnect, timeout configuration.

### Answer

#### Mid-stream typed exceptions (all inherit from openai.*):
| Exception class | HTTP analog | When |
|---|---|---|
| `litellm.Timeout` (= `openai.APITimeoutError`) | 408 | request or stream timeout |
| `litellm.RateLimitError` | 429 | provider rate-limits mid-stream |
| `litellm.APIError` | 500 | provider internal error |
| `litellm.APIConnectionError` | 500 | connection broken mid-stream |
| `litellm.ServiceUnavailableError` | 503 | provider down |
| `litellm.InternalServerError` | ≥500 | provider server error |

Source: https://docs.litellm.ai/docs/exception_mapping — full exception mapping table.
"LiteLLM standardizes provider errors to OpenAI exception types."
Example: `openai.APITimeoutError` raised while iterating `for chunk in response`.

#### Stream cancellation / aclose()
From source inspection of `streaming_handler.py`:
- `aclose()` is implemented on the `CustomStreamWrapper`.
- It uses `anyio.CancelScope(shield=True)` internally to protect cleanup awaits:
  "Shield from anyio cancellation so cleanup awaits can complete. Without this, CancelledError is
  thrown into every await during task group cancellation, preventing HTTP connection release."
- Pattern to cancel and clean up:
  ```python
  try:
      async for chunk in response:
          ...
  except asyncio.CancelledError:
      await response.aclose()   # official aclose() on the stream object
      raise                     # re-raise so FastAPI/anyio can propagate
  ```
- `asyncio.CancelledError` DOES propagate naturally when a FastAPI handler is cancelled (via
  anyio task group). The generator must have `await` points for cancellation to land.

#### Timeouts
- **Per-request**: pass `timeout=<seconds>` to `acompletion()` directly.
- **Streaming-specific**: `stream_timeout=<seconds>` per model in Router config.
- Example:
  ```python
  response = await litellm.acompletion(
      model="...", messages=[...], stream=True, timeout=30
  )
  ```
  Source: https://docs.litellm.ai/docs/proxy/timeout (Router model_list `stream_timeout`)

### Status
ASSUMPTION_CONFIRMED — the task pack assumes typed exception handling (502 on upstream fail).
Confirmed: catch `litellm.APIError` / `litellm.APIConnectionError` / `litellm.ServiceUnavailableError`
as the 502 trigger before first byte. Mid-stream: catch `litellm.Timeout`, `litellm.RateLimitError`,
`litellm.APIConnectionError`; emit `event: error` then close.

---

## M.3 — aembedding() signature and response shape

### Question
Exact async embedding call signature, response shape, and how to enforce dim=1536 for
text-embedding-3-small.

### Answer

#### Call signature
```python
response = await litellm.aembedding(
    model="text-embedding-3-small",
    input=["Your text string"],       # list[str] or single str
    dimensions=1536,                  # explicit, only supported on text-embedding-3+
)
```
Source: https://docs.litellm.ai/docs/embedding/supported_embedding —
"The `dimensions` parameter is only supported in text-embedding-3 and later models."

#### Response shape (OpenAI-format)
```python
response.data[0]["embedding"]   # list[float], length = dimensions
response.data[0].embedding      # also accessible as attribute
response.usage.prompt_tokens    # token count
```
Pattern confirmed: `len(response.data[0]['embedding'])` gives dimension count.
Source: Context7 snippet `print(f"Embedding dimensions: {len(response.data[0]['embedding'])}")`.

#### Dimension enforcement
- Pass `dimensions=1536` explicitly. Default for text-embedding-3-small is 1536 already, but
  passing it explicitly is the safe pattern.
- LiteLLM passes `dimensions` through to OpenAI API as a native param.
- To validate: `assert len(embedding_vector) == 1536` after call.

### Status
ASSUMPTION_CONFIRMED — pack assumes `aembedding(model="text-embedding-3-small", input=[...])`.
Confirmed correct. Add `dimensions=1536` for safety. Response shape confirmed as
`response.data[0].embedding` (list[float]).

RESOLVED: N/A — no discrepancy.
