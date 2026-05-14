# Source-of-truth amendment — FU-20260513201144-fix-ready-500-ping-db-uses-sync-engine-connect-o

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S03-T005 | bug | Fix /ready 500 — _ping_db uses sync engine.connect() on async asyncpg engine | Runtime follow-up P02-S03-T004 | current | planned | medium | human | P02-S03-T004 | infra:health-router | backend/app/api/router.py, backend/app/db/engine.py, backend/tests/integration/test_health.py | J100 | — | — | — | runtime-followup#FU-20260513201144-fix-ready-500-ping-db-uses-sync-engine-connect-o | runtime-followup#FU-20260513201144-fix-ready-500-ping-db-uses-sync-engine-connect-o | (1) GET /ready returns 200 under happy path, (2) integration test asserts /ready 200 with real Postgres up + 503 when DB down, (3) tests run with both ENABLE_VERBOSE_LOGGING=true and =false | curl -i http://localhost:8000/ready returns 200 OK with JSON {db:ok, redis:ok} when stack is up, back.log shows no MissingGreenlet trace |
```
