# Source-of-truth amendment — FU-20260518050950-fix-stale-acceptance-keyword-in-checklist-regist

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T012 | bug | Fix stale acceptance keyword in checklist + registry for P04-S01-T007 admin-ai integration tests | Runtime follow-up P04-S01-T007 | current | planned | medium | human | P04-S01-T007 | source-of-truth:checklist-coverage-registry | docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md, orchestrator-state/tasks/registry.json | — | — | — | — | runtime-followup#FU-20260518050950-fix-stale-acceptance-keyword-in-checklist-regist | runtime-followup#FU-20260518050950-fix-stale-acceptance-keyword-in-checklist-regist | Coverage Registry row for P04-S01-T007 uses an acceptance string that, executed verbatim, runs the 26 in-scope tests of backend/tests/integration/test_admin_ai.py (file-path form, or a -k keyword that actually matches the test names). | Run the exact acceptance string from checklist line for P04-S01-T007: pytest collects >=26 items and reports 26 passed. registry.json acceptance field for P04-S01-T007 matches the checklist verbatim. |
```
