# Source-of-truth amendment — FU-20260514053554-complete-chat-py-uses-non-existent-sdk-provider-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S03-T008 | bug | complete_chat.py uses non-existent SDK provider 'litellm/<model>' (same as P02-S03-T006) | Runtime follow-up P02-S03-T006 | current | planned | high | human | P02-S03-T006 | ai:streaming | backend/app/llm_gateway/complete_chat.py, backend/tests/unit/test_llm_gateway_complete_chat.py | J103 | — | — | — | runtime-followup#FU-20260514053554-complete-chat-py-uses-non-existent-sdk-provider- | runtime-followup#FU-20260514053554-complete-chat-py-uses-non-existent-sdk-provider- | complete_chat.py imports and uses _compose_sdk_model_args from litellm_client (or relocated to a shared module), unit test verifies provider_type='litellm' produces model='openai/<model_id>' + api_base=provider.base_url | POST /api/v1/admin/ai/models/{id}/test against seeded litellm provider returns 200 with usage, no BadRequestError in back.log |
```
