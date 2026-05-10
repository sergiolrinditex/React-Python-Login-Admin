# Source-of-truth amendment — FU-20260509220235-fix-admin-ai-seed-loader-column-api-key-does-not

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T010 | bug | Fix admin_ai seed loader: column api_key does not exist in ai_providers (should use ai_provider_credentials) | Runtime follow-up P00-S02-T006 | current | planned | medium | human | P00-S02-T006 | admin_ai_endpoints | backend/app/seeds/loader.py | J103 | — | — | — | runtime-followup#FU-20260509220235-fix-admin-ai-seed-loader-column-api-key-does-not | runtime-followup#FU-20260509220235-fix-admin-ai-seed-loader-column-api-key-does-not | python -m app.seeds.bootstrap_verification_data --source data/verification --only admin_ai exits 0 with upsert success log (no ProgrammingError) | Run seed loader with real DB and admin_ai tables present → SELECT count(*) FROM ai_providers returns >= 1 |
```
