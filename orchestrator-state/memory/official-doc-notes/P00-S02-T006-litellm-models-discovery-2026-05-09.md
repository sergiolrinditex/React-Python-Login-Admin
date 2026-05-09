# Official Doc Note — LiteLLM /v1/models: configured models only vs. dynamic discovery

DATE: 2026-05-09
TASK_ID: P00-S02-T006
SEVERITY: medium
TOPIC: LiteLLM proxy /v1/models endpoint — configured vs. discovered models

## CONTEXT

Task pack §B1 states: the `litellm` provider type calls `GET {base_url}/v1/models` with
`Authorization: Bearer {master_key}` and expects an OpenAI-compatible shape. ADR-001 says
this is the runtime expression of dynamic model discovery. The assumption is that the proxy
enumerates models the upstream provider exposes.

## INTERNAL_DOC_SAYS

Task pack §B1 + ADR-001: Calling `GET /v1/models` on the LiteLLM proxy returns the list of
models the configured provider exposes, and this endpoint is used by the `litellm` provider
client to discover available models.

The plan (§7 step 6) reads: "LiteLLMProxyClient: `GET {base_url}/v1/models` with
`Authorization: Bearer {master_key}` — OpenAI-compatible shape."

LiteLLM sanity check in §8:
```
curl -sf http://localhost:4000/v1/models -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
# Expect: empty list (LiteLLM config.yaml has model_list: [])
```
The task pack already notes the expected result is empty because `model_list: []` in
config.yaml — acknowledging implicitly that /v1/models reflects the configured list.

## OFFICIAL_DOC_SAYS

Source: https://docs.litellm.ai/docs/proxy/model_discovery (Context7 /websites/litellm_ai)

**Critical finding**: `GET /v1/models` on the LiteLLM proxy returns ONLY models that are
**explicitly configured in config.yaml under `model_list`**. Dynamic discovery of upstream
provider models requires:
1. Wildcard model entries in config.yaml (e.g., `xai/*`, `gemini/*`), AND
2. `litellm_settings: check_provider_endpoint: true` in config.yaml.

Without these two config changes, `/v1/models` returns only the static list from config.yaml.

The response shape is confirmed OpenAI-compatible:
```json
{
    "data": [
        {"id": "model-name", "object": "model", "created": 1677610602, "owned_by": "openai"}
    ],
    "object": "list"
}
```

Auth header confirmed: `Authorization: Bearer $LITELLM_KEY` (any valid proxy API key; the
master key `LITELLM_MASTER_KEY` works as a proxy key). There is NO separate
"discover from provider" endpoint on the proxy.

## DISCREPANCY

**Nature**: The task pack assumes the `litellm` provider client can use `/v1/models` to get
the upstream provider's available models. Officially, this only works if:
- `model_list` in config.yaml uses wildcard patterns (e.g., `litellm/*` or `gemini/*`), AND
- `check_provider_endpoint: true` is set.

The project's `infra/litellm/config.yaml` currently has `model_list: []` (as noted in task
pack sanity check expecting an empty response). This means:
- For the `litellm` provider type, `/v1/models` will always return `[]` until config.yaml
  is updated with wildcard entries + `check_provider_endpoint: true`.
- The intent of "LiteLLM proxy as a model discovery target" requires config change, not just
  an HTTP call.

**Impact on T006 implementation**: The three provider types have different discovery mechanics:
- `gemini` — CONFIRMED: `GET /v1beta/models?key={api_key}` returns model list under `models[]`
  key directly from Google API. This is NOT via LiteLLM proxy.
- `openai` — CONFIRMED: `GET {base_url}/v1/models` with `Authorization: Bearer {api_key}`
  works directly against the OpenAI API.
- `litellm` (proxy) — NUANCE: `/v1/models` only returns models from config.yaml. If
  config.yaml has `model_list: []`, the discovery returns empty, which is valid behavior.
  The endpoint still works and returns 200 with `data: []`; it is not a bug.

**Conclusion for developer**: The `litellm` provider client implementation calling
`GET {base_url}/v1/models` is architecturally CORRECT but the caller must understand that:
(a) the result reflects what is configured in litellm config.yaml, NOT what the upstream
provider has available;
(b) for the dev/test environment with `model_list: []`, the result will be empty (`added=[]`,
`existing=[]`, `total_seen=0`); this is correct behavior, not a failure;
(c) to get actual models from a provider via LiteLLM proxy, an operator must configure
wildcard model entries in config.yaml — this is a deployment/operations concern, not a code bug.

The task pack §8 LiteLLM sanity check already acknowledges this ("Expect: empty list") so
the developer is not blocked. The implementation plan is correct.

## RECOMMENDATION

Developer should:
1. Add a docstring to `LiteLLMProxyClient.list_models()` explaining that results depend on
   what is configured in the proxy's `model_list` (not upstream provider discovery).
2. Add a comment in the test for the `litellm` provider type explaining why `total_seen=0`
   is the expected result for the dev environment (config.yaml has `model_list: []`).
3. NO code change required — the implementation plan in §7 is correct.

This note is informational. The developer may add `RESOLVED: documented in LiteLLMProxyClient docstring`
after reconciling.

RESOLVED: 2026-05-09 — LiteLLMProxyClient.list_models() docstring explains that results reflect
config.yaml model_list (not upstream provider models). Test for litellm provider type uses
total_seen=0 expectation with a comment explaining the dev config.yaml has model_list: [].
No code change required. Implementation plan §7 is correct as-is.
