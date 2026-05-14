# Source-of-truth amendment — FU-20260513201155-fix-chat-stream-chunks-llm-gateway-uses-non-exis

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S03-T006 | bug | Fix chat stream chunks — llm_gateway uses non-existent SDK provider 'litellm/<model>' | Runtime follow-up P02-S03-T004 | current | planned | high | human | P02-S03-T004 | ai:streaming | backend/app/llm_gateway/litellm_client.py, backend/app/chat/streaming/service.py, backend/tests/integration/test_chat_streaming_live.py | J101 | — | — | — | runtime-followup#FU-20260513201155-fix-chat-stream-chunks-llm-gateway-uses-non-exis | runtime-followup#FU-20260513201155-fix-chat-stream-chunks-llm-gateway-uses-non-exis | (1) live curl POST /chat/conversations/{id}/stream returns text/event-stream with sequence meta → chunk(*) → usage → done, (2) model_str composition produces a SDK-valid provider prefix per provider.provider_type ('litellm' provider_type → 'openai/<model_id>' + api_base=provider.base_url), (3) live integration test (gated by env LITELLM_PROXY_UP=1) asserts the sequence, (4) existing 51 streaming tests still pass | After admin sign-in: POST /chat/conversations then POST /chat/conversations/{id}/stream with {message:'hello'} → returns 200 text/event-stream containing all four event types, back.log shows no BadRequestError |
```
