# Source-of-truth amendment — FU-20260513085435-add-partial-unique-index-for-is-default-true-per

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S05-T003 | bug | Add partial unique index for is_default=true per model_type in ai_models | Runtime follow-up P02-S05-T001 | current | planned | medium | human | P02-S05-T001 | api:admin-ai | backend/app/admin/providers.py, backend/app/admin/model_catalog.py, backend/tests/integration/test_admin_ai.py | — | — | — | — | runtime-followup#FU-20260513085435-add-partial-unique-index-for-is-default-true-per | runtime-followup#FU-20260513085435-add-partial-unique-index-for-is-default-true-per | Migration 0003 with partial unique index applied, existing integration tests (T18) still pass, a concurrent-PATCH test proves the DB rejects the second concurrent SET is_default=true for same model_type. | Run pytest backend/tests/integration -k admin_ai_models, try concurrent PATCHes setting is_default=true on two models of same type, verify DB raises unique_violation instead of silently allowing two defaults. |
```
