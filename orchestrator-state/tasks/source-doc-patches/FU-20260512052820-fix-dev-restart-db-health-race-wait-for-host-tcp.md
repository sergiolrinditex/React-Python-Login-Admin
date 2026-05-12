# Source-of-truth amendment — FU-20260512052820-fix-dev-restart-db-health-race-wait-for-host-tcp

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P01-S02-T012 | bug | fix dev-restart db_health race: wait for host TCP, not container-internal pg_isready | Runtime follow-up P01-S02-T008 | current | planned | medium | human | P01-S02-T008 | tooling:dev-restart | scripts/dev-restart.profile.sh | — | — | — | — | runtime-followup#FU-20260512052820-fix-dev-restart-db-health-race-wait-for-host-tcp | runtime-followup#FU-20260512052820-fix-dev-restart-db-health-race-wait-for-host-tcp | Two consecutive 'bash scripts/dev-restart.sh --reset' commands both exit 0 and persist users>=1, with no manual sleep between them. wait_for db_health returns only after both container-internal pg_isready AND a real host-side connection (127.0.0.1:5432 with valid credentials) succeed within 60s. If host-side connection fails after 60s the script fails non-zero (no silent fallback). | Run: bash scripts/dev-restart.sh --reset, echo $?, bash scripts/dev-restart.sh --reset, both must print 0. psql count(*) FROM users must return >= 1 after each. Negative control: stop postgres container (docker compose stop postgres), run bash scripts/dev-restart.sh --reset → must fail within 60s with a clear 'Postgres did not become ready' message. |
```
