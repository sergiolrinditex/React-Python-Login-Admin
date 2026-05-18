# Source-of-truth amendment — FU-20260517220254-test-isolation-test-migrations-downgrade-pollute

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T010 | test | Test isolation: test_migrations downgrade pollutes RAG/MCP suite (~63 failures, 68 errors) | Runtime follow-up P04-S01-T007 | current | planned | medium | human | P04-S01-T007 | back:admin-ai | backend/tests/conftest.py, backend/tests/integration/conftest.py, backend/tests/integration/test_migrations_0001_auth.py | — | — | — | — | runtime-followup#FU-20260517220254-test-isolation-test-migrations-downgrade-pollute | runtime-followup#FU-20260517220254-test-isolation-test-migrations-downgrade-pollute | Full pytest backend/tests/integration -v runs with no failures attributable to dropped DB schema, RAG, MCP and admin-ai integration tests all pass in a single run after the migrations downgrade test. | pytest backend/tests/integration -v shows zero UndefinedTable / OperationalError failures caused by cross-test schema teardown, rerun stable across two consecutive invocations. |
```
