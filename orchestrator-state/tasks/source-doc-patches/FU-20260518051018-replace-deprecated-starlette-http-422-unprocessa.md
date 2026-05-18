# Source-of-truth amendment — FU-20260518051018-replace-deprecated-starlette-http-422-unprocessa

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T014 | techdebt | Replace deprecated Starlette HTTP_422_UNPROCESSABLE_ENTITY with HTTP_422_UNPROCESSABLE_CONTENT across backend | Runtime follow-up P04-S01-T007 | current | planned | low | human | P04-S01-T007 | backend:starlette-version-uplift | backend/app/**/*.py, backend/tests/**/*.py, backend/pyproject.toml (only if version bump required) | — | — | — | — | runtime-followup#FU-20260518051018-replace-deprecated-starlette-http-422-unprocessa | runtime-followup#FU-20260518051018-replace-deprecated-starlette-http-422-unprocessa | pytest backend/tests/integration/test_admin_ai.py reports 0 warnings (or warnings that do not mention HTTP_422_UNPROCESSABLE_ENTITY) in both ENABLE_VERBOSE_LOGGING=on and off modes. Same for any other integration suite using the constant. | grep -R 'HTTP_422_UNPROCESSABLE_ENTITY' backend/ returns 0 matches, pytest -W error::DeprecationWarning backend/tests/integration/test_admin_ai.py passes 26/26 (or any failures are unrelated to the Starlette alias). |
```
