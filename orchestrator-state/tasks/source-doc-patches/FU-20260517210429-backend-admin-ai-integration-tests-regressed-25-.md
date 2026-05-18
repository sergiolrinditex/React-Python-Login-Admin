# Source-of-truth amendment — FU-20260517210429-backend-admin-ai-integration-tests-regressed-25-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T007 | bug | Backend admin AI integration tests regressed (25 failures in test_admin_ai.py) | Runtime follow-up P04-S01-T003 | current | planned | high | human | P04-S01-T003 | back:admin-ai | backend/app/admin/providers/**, backend/app/admin/model_catalog/**, backend/tests/integration/test_admin_ai.py | J103 | — | — | — | runtime-followup#FU-20260517210429-backend-admin-ai-integration-tests-regressed-25- | runtime-followup#FU-20260517210429-backend-admin-ai-integration-tests-regressed-25- | pytest backend/tests/integration -k admin_ai_models passes 25/25 (or test scope updated with explicit rationale in source-of-truth). | full backend admin-ai integration suite green AND a fresh /verify-slice for the J103 admin AI happy path still passes. |
```
