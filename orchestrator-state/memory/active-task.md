# Active task

- ID: P01-S02-T002
- Title: POST /api/v1/auth/sign-in
- Status: blocked
- Phase: P01

## Acceptance
- Sign-in verifies Argon2 password, returns MFA challenge or access token, does not leak user existence

## Allowed paths
- backend/app/auth/**
- backend/tests/integration/test_auth_signin.py

## DAG conflict guardrails
### Conflict groups
- api:auth
### Write set
- backend/app/auth/**
- backend/tests/integration/test_auth_signin.py

## Verification commands
- `pytest backend/tests/integration -k auth_signin && curl with seed user`
