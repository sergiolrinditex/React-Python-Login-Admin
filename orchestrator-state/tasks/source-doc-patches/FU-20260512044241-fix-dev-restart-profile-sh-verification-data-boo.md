# Source-of-truth amendment — FU-20260512044241-fix-dev-restart-profile-sh-verification-data-boo

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P01-S02-T008 | tooling | fix dev-restart.profile.sh verification-data bootstrap source path | Runtime follow-up P01-S02-T002 | current | planned | medium | human | P01-S02-T002 | tooling:dev-restart | scripts/dev-restart.profile.sh | — | — | — | — | runtime-followup#FU-20260512044241-fix-dev-restart-profile-sh-verification-data-boo | runtime-followup#FU-20260512044241-fix-dev-restart-profile-sh-verification-data-boo | scripts/dev-restart.sh --reset completes the seed step (loads data/verification users) without falling back to the manual workaround. tests/orchestrator-level smoke covers the seed assertion (count > 0). | Run scripts/dev-restart.sh --reset on a clean DB. Assert: (a) script exits 0, (b) back.log contains 'verification_data.auth.users.ok inserted=N' with N>=1, (c) psql 'SELECT count(*) FROM users' >= 1. |
```
