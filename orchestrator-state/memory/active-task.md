# Active task

- ID: P01-S01-T003
- Title: Quote MAIL_FROM_NAME in .env.example to fix bash source failure
- Status: ready
- Phase: P01

## Acceptance
- bash scripts/dev-restart.sh --check exits with backend UP, not 'command not found'

## Allowed paths
- .env.example

## DAG conflict guardrails
### Conflict groups
- infra:env
### Write set
- .env.example

## Verification commands
- `grep 'MAIL_FROM_NAME="Hilo People"' .env.example`
