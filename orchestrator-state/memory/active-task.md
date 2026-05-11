# Active task

- ID: P00-S02-T004
- Title: fix verification_data loader :meta::jsonb SQL cast
- Status: ready
- Phase: P00

## Acceptance
- pytest backend/tests/integration/test_dev_restart_reset.py backend/tests/integration/test_verification_data_bootstrap.py pasa contra Postgres real con tablas auth ya migradas

## Allowed paths
- backend/app/verification_data/loader.py
- backend/tests/integration/test_dev_restart_reset.py
- backend/tests/integration/test_verification_data_bootstrap.py

## DAG conflict guardrails
### Conflict groups
- backend:verification_data
### Write set
- backend/app/verification_data/loader.py
- backend/tests/integration/test_dev_restart_reset.py
- backend/tests/integration/test_verification_data_bootstrap.py

## Verification commands
- `cd backend && alembic upgrade head && pytest backend/tests/integration/test_dev_restart_reset.py backend/tests/integration/test_verification_data_bootstrap.py -v`
