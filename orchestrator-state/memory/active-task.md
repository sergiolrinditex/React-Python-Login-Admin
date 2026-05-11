# Active task

- ID: P00-S01-T004
- Title: Design tokens and editorial system
- Status: ready
- Phase: P00

## Acceptance
- Tokens and base components implement the Visual Implementation Contract
- no rounded corners
- showcase visible with required states
- VISUAL_CONTRACT_CHECK documents tokens, components, required states, real data/backend and visual evidence

## Allowed paths
- frontend/src/shared/styles/**
- frontend/src/shared/design-system/**
- frontend/src/app/router.tsx
- frontend/src/pages/showcase/**
- scripts/check-design-tokens.sh

## DAG conflict guardrails
### Conflict groups
- theme
### Write set
- frontend/src/shared/styles/**
- frontend/src/shared/design-system/**
- frontend/src/app/router.tsx
- frontend/src/pages/showcase/**
- scripts/check-design-tokens.sh

## Verification commands
- `npm --prefix frontend run build && bash scripts/check-design-tokens.sh`
- `browser visual check /showcase with evidence referenced in handoff`
