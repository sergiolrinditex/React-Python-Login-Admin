# Active task

- ID: P00-S02-T003
- Title: Seed data and reset verification bundle
- Status: needs_debug
- Phase: P00

## Acceptance
- Prod-like seed users/documents/providers/MCP/agents are idempotent and resettable

## Allowed paths
- backend/app/seeds/**
- scripts/dev-restart.sh

## DAG conflict guardrails
### Conflict groups
- seed:data
### Write set
- backend/app/seeds/**
- scripts/dev-restart.sh

## Verification commands
- `python -m app.seeds.bootstrap_verification_data --source data/verification && bash scripts/dev-restart.sh --reset`
