# Source-of-truth amendment — FU-20260510104826-test-admin-ai-discover-models-event-loop-conflic

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T016 | test | test_admin_ai_discover_models event-loop conflict under live uvicorn | Runtime follow-up P00-S02-T012 | current | planned | medium | human | P00-S02-T012 | admin_ai_endpoints | backend/tests/integration/test_admin_ai_discover_models.py | J103 | — | — | — | runtime-followup#FU-20260510104826-test-admin-ai-discover-models-event-loop-conflic | runtime-followup#FU-20260510104826-test-admin-ai-discover-models-event-loop-conflic | Both tests pass deterministically when run with .env.local loaded AND dev uvicorn :8000 up (or skip cleanly with explanatory marker) | 1) Start dev backend, 2) source .env + .env.local, 3) pytest tests/integration/test_admin_ai_discover_models.py -v -> all pass or skip-with-reason, 0 RuntimeError event-loop errors |
```
