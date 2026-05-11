# Source-of-truth amendment — FU-20260511145446-fix-verification-data-loader-meta-jsonb-sql-cast

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T004 | bug | fix verification_data loader :meta::jsonb SQL cast | Runtime follow-up P00-S02-T003 | current | planned | medium | human | P00-S02-T003 | backend:verification_data | backend/app/verification_data/loader.py, backend/tests/integration/test_dev_restart_reset.py, backend/tests/integration/test_verification_data_bootstrap.py | — | — | — | — | runtime-followup#FU-20260511145446-fix-verification-data-loader-meta-jsonb-sql-cast | runtime-followup#FU-20260511145446-fix-verification-data-loader-meta-jsonb-sql-cast | pytest backend/tests/integration/test_dev_restart_reset.py backend/tests/integration/test_verification_data_bootstrap.py pasa contra Postgres real con tablas auth ya migradas | cd backend && alembic upgrade head && pytest backend/tests/integration/test_dev_restart_reset.py backend/tests/integration/test_verification_data_bootstrap.py -v |
```
