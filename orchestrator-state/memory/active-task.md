# Active task

- ID: P00-S01-T005
- Title: i18n resources ES/EN/FR
- Status: ready
- Phase: P00

## Acceptance
- Namespaces common/auth/chat/account/admin-ai/rag/mcp/errors exist in es/en/fr with fallback es

## Allowed paths
- frontend/src/i18n/**
- frontend/public/locales/**

## DAG conflict guardrails
### Conflict groups
- i18n
### Write set
- frontend/src/i18n/**
- frontend/public/locales/**

## Verification commands
- `npm --prefix frontend run test -- --run -t i18n`
