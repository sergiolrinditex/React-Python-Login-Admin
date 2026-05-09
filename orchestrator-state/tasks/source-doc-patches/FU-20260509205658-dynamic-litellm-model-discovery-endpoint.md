# Source-of-truth amendment — FU-20260509205658-dynamic-litellm-model-discovery-endpoint

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T006 | feature | Dynamic LiteLLM model discovery endpoint | Runtime follow-up P00-S02-T005 | current | planned | medium | human | P00-S02-T005 | admin_ai_endpoints | backend/app/features/admin_ai/** | J103 | — | — | — | runtime-followup#FU-20260509205658-dynamic-litellm-model-discovery-endpoint | runtime-followup#FU-20260509205658-dynamic-litellm-model-discovery-endpoint | POST /api/v1/admin/ai/providers/{id}/discover-models implemented, reconciles against ai_models, returns the diff | real call against gemini-direct provider returns >= 3 chat models, persists rows in ai_models with auto_discovered=true |
```
