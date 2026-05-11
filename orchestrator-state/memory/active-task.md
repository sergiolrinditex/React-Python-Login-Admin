# Active task

- ID: P01-S02-T001
- Title: POST /api/v1/auth/sign-up
- Status: blocked
- Phase: P01

## Acceptance
- Sign-up validates corporate email and legal acceptance
- audit log written

## Allowed paths
- backend/app/auth/**
- backend/tests/integration/test_auth_signup.py

## DAG conflict guardrails
### Conflict groups
- api:auth
### Write set
- backend/app/auth/**
- backend/tests/integration/test_auth_signup.py

## Verification commands
- `pytest backend/tests/integration -k auth_signup && curl with reales/proporcionados user`
