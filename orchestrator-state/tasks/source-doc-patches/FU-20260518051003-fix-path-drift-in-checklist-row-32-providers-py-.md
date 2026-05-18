# Source-of-truth amendment — FU-20260518051003-fix-path-drift-in-checklist-row-32-providers-py-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T013 | documentation | Fix path drift in checklist row 32: providers.py/model_catalog.py are packages, not single files | Runtime follow-up P04-S01-T007 | current | planned | low | human | P04-S01-T007 | source-of-truth:checklist-coverage-registry | docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md | — | — | — | — | runtime-followup#FU-20260518051003-fix-path-drift-in-checklist-row-32-providers-py- | runtime-followup#FU-20260518051003-fix-path-drift-in-checklist-row-32-providers-py- | Checklist row referencing P04-S01-T007 admin-ai integration tests cites the actual package paths (or globs) consistent with the registry write_set: backend/app/admin/providers/** and backend/app/admin/model_catalog/**. | Visual diff confirms row 32 paths match ls backend/app/admin/providers/ (directory exists, contains __init__.py and submodules). |
```
