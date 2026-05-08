# Active task

- ID: P00-S01-T004
- Title: Design tokens and editorial system
- Status: ready
- Phase: P00

## Acceptance
- Tokens match Hilo editorial system
- no rounded corners
- showcase visible

## Allowed paths
- frontend/src/shared/styles/**
- frontend/src/shared/design-system/**

## DAG conflict guardrails
### Conflict groups
- theme
### Write set
- frontend/src/shared/styles/**
- frontend/src/shared/design-system/**

## Verification commands
- `npm --prefix frontend run build and visual check /showcase`
