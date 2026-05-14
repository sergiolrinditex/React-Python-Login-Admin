# Official Doc Note — P02-S03-T006 LiteLLM Provider Mapping (Q1–Q5)

DATE: 2026-05-14
TASK: P02-S03-T006 (Fix chat stream chunks — llm_gateway uses non-existent SDK provider)
SOURCES:
- Prior cache: orchestrator-state/memory/official-doc-notes/P02-S03-T002-litellm-streaming-2026-05-13.md
- Prior cache: orchestrator-state/memory/official-doc-notes/P02-S05-T002-litellm-2026-05-13.md
- https://docs.litellm.ai/docs/providers/litellm_proxy (proxy routing, api_base, api_key semantics)
- https://docs.litellm.ai/docs/exception_mapping (exception classes, import paths)
- https://docs.litellm.ai/docs/providers/openai (direct OpenAI api_base)

---

## Q1 — LiteLLM SDK v1.83.14 — proxy routing canonical form

### ANSWER

Confirmed from P02-S05-T002 Q5 (official docs):
Two model string forms work when routing through a LiteLLM proxy at `http://localhost:4000`:

Form A (preferred for proxy, OpenAI-compatible models):
```python
await litellm.acompletion(
    model="openai/gpt-4o-mini",
    api_base="http://localhost:4000",
    api_key="<litellm-proxy-master-key>",
    ...
)
```

Form B (explicit proxy prefix):
```python
await litellm.acompletion(
    model="litellm_proxy/gpt-4o-mini",
    api_base="http://localhost:4000",
    api_key="<litellm-proxy-master-key>",
    ...
)
```

Both forms confirmed valid by official docs and prior researcher Q5 (P02-S05-T002).
Decision: use `openai/<model_id>` for `provider_type='litellm'` because the proxy is
OpenAI-compatible and this prefix is already used for direct OpenAI, reducing mapping complexity.

Source: https://docs.litellm.ai/docs/providers/litellm_proxy — "api_key: your-litellm-proxy-api-key"
(Prior cache P02-S05-T002 Q5 section "Model string format")

### RESOLVED: provider_type='litellm' → model='openai/<model_id>' + api_base=provider.base_url

---

## Q2 — api_base scoping per-call vs env

### ANSWER

Confirmed from P02-S03-T002 (M.1) and P02-S05-T002 (Q5):
`api_base` passed as a kwarg is per-call and overrides any env var for that specific request.
The LiteLLM SDK v1.83.14 does not cache `api_base` between calls — each `acompletion` call
receives its kwargs independently.

The existing `litellm_client.py` pattern (lines 137-138) already implements this correctly:
```python
if provider.base_url:
    kwargs["api_base"] = provider.base_url
```

Per-call override is deterministic across streaming generator lifecycle — the `api_base` is
captured into the request at `await litellm.acompletion(**kwargs)` call time; concurrent requests
with different providers do NOT interfere.

### RESOLVED: api_base per-call scoping is safe; existing pattern is correct.

---

## Q3 — api_key semantics with the LiteLLM proxy

### ANSWER

Confirmed from P02-S05-T002 Q5:
(a) When calling `acompletion(api_key="<bearer>", api_base="http://localhost:4000")`:
    The SDK sends `Authorization: Bearer <bearer>` to the proxy's `/v1/chat/completions`.
(b) The SDK does NOT strip a `Bearer ` prefix if passed literally. Pass the raw key value.
(c) There is NO separate `proxy_api_key` parameter — use standard `api_key=`.

The proxy's bearer token is the `LITELLM_MASTER_KEY` (or a virtual key generated via `/key/generate`).
The proxy handles the real provider credential internally — the Python client does NOT need the
underlying OpenAI/Anthropic API key when routing through the proxy.

Source: https://docs.litellm.ai/docs/providers/litellm_proxy (Prior cache P02-S05-T002 Q5)

### RESOLVED: api_key=<plain-bearer> is correct; no prefix stripping; no proxy_api_key param.

---

## Q4 — Error taxonomy on bad model= value

### ANSWER

Confirmed from P02-S05-T002 Q2 and P02-S03-T002 M.2:
When `model="litellm/<id>"` reaches `litellm.acompletion`, it raises:
  `litellm.BadRequestError` — "LLM Provider NOT provided…"

The import path: `from litellm import BadRequestError` (no sub-module needed in v1.83.14).
All LiteLLM exceptions inherit from openai.* counterparts.

Current handling in `litellm_client.py:152` catches bare `Exception` — this is correct as a
fallback but we can add a more specific BEFORE the generic catch for logging purposes.
The TECHNICAL_GUIDE §line 345 maps this to `CHAT_STREAM_FAILED` / our `LiteLLMError`.
No new error code needed — `LiteLLMError` is the correct domain translation.

Source: https://docs.litellm.ai/docs/exception_mapping (Prior cache P02-S05-T002 Q2)

### RESOLVED: litellm.BadRequestError → wrapped into our LiteLLMError via existing except Exception.

---

## Q5 — Canonical provider_type → SDK prefix table

### ANSWER

Confirmed from P02-S05-T002 Q5 and official docs. For LiteLLM SDK v1.83.14:

| provider_type (our DB) | SDK model prefix | api_base required? | Notes |
|---|---|---|---|
| litellm | openai/ | YES (proxy URL) | proxy is OpenAI-compat; api_base routes to proxy |
| openai | openai/ | Optional (only if custom base URL) | Direct to api.openai.com by default |
| anthropic | anthropic/ | No (SDK default) | |
| azure_openai | azure/ | YES (Azure endpoint URL) | also needs api_version kwarg |
| ollama | ollama/ | YES (local server URL) | |
| groq | groq/ | No | |
| together_ai | together_ai/ | No | |
| mistral | mistral/ | No | |
| cohere | cohere/ | No | |

For unknown provider_type: raise LiteLLMError at composition time (explicit fail is safer).
Source: https://docs.litellm.ai/docs/providers/* (each provider page)
(Prior cache P02-S05-T002 Q5 section "Model string format")

### RESOLVED: Full mapping table confirmed. D-LITELLM-PROVIDER-MAP locked.

---

## Discrepancies with internal docs

NONE identified. The task pack's recommended mapping:
- `provider_type='litellm'` → `model='openai/<model_id>'` + `api_base=provider.base_url`

...is confirmed correct by the official docs. The prior pack's mention of `litellm_proxy/` as
an alternative is also valid but we choose `openai/` per the pack recommendation for consistency.

---

## RECOMMENDATION SUMMARY

- Use `_PROVIDER_TYPE_TO_SDK_PREFIX` dict in `litellm_client.py` with initial entries per Q5.
- For `provider_type='litellm'`: map to `openai` prefix + always set `api_base=provider.base_url`.
- For `provider_type='openai'` with `base_url`: also pass `api_base` (custom OpenAI-compatible).
- For `provider_type='azure_openai'`: map to `azure` prefix + always set `api_base`.
- Unknown provider_type: raise `LiteLLMError` immediately (do NOT silently default).
- api_base: pass per-call as kwarg; no env var manipulation needed.
- api_key: pass raw bearer value; no `Bearer ` prefix.

RESOLVED: All 5 questions answered from prior confirmed research + official docs.
No real-doc discrepancy with this task pack. Developer may proceed.
