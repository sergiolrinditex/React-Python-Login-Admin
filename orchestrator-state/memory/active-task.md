# Active task

- ID: P00-S02-T005
- Title: Replace synthetic verification bundle with People Tech delivery
- Status: ready
- Phase: P00

## Acceptance
- data/verification/ contains files exactly matching People Tech delivery (signed manifest)
- loader's synthetic- guard relaxed or moved to env-flag
- J100..J105 verified end-to-end with the real bundle.

## Allowed paths

## DAG conflict guardrails
### Conflict groups
- seed:data
### Write set
- data/verification/**

## Verification commands
- `Journey verifications J100..J105 reproduced against the People Tech bundle`
- `pytest backend/tests/integration -k seed green`
- `no synthetic- placeholders remaining in data/verification/.`
