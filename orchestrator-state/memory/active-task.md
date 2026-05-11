# Active task

- ID: P00-S01-T002
- Title: Frontend dependency pack
- Status: blocked
- Phase: P00

## Acceptance
- React Router, TanStack Query, forms and i18n deps installed
- first provider wired

## Allowed paths
- frontend/package.json
- frontend/package-lock.json
- frontend/src/app/providers.tsx

## DAG conflict guardrails
### Conflict groups
- dependency:frontend
### Write set
- frontend/package.json
- frontend/package-lock.json
- frontend/src/app/providers.tsx

## Verification commands
- `bash -lc "npm --prefix frontend run test -- --run"`
