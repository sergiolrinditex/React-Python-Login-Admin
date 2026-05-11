# Task DAG

> DERIVED artifact. Do not edit manually. Source of truth: Coverage Registry `Depends on` column.

- Mode: `explicit_dag`
- Nodes: 61
- Edges: 119

## Parallel waves

### Wave 1

- `P00-S01-T001` — Repo scaffold + scripts + env _(depends_on: —; conflict_groups: setup:bootstrap; write_set: package.json, frontend/package.json, backend/pyproject.toml, backend/requirements*.txt, backend/app/main.py, scripts/**, .env.example; risk: low; verify_mode: auto)_

### Wave 2

- `P00-S01-T002` — Frontend dependency pack _(depends_on: P00-S01-T001; conflict_groups: dependency:frontend; write_set: frontend/package.json, frontend/package-lock.json, frontend/src/app/providers.tsx; risk: low; verify_mode: auto)_
- `P00-S01-T003` — Backend dependency pack _(depends_on: P00-S01-T001; conflict_groups: dependency:backend; write_set: backend/pyproject.toml, backend/requirements*.txt, backend/app/core/**; risk: low; verify_mode: auto)_
- `P00-S01-T004` — Design tokens and editorial system _(depends_on: P00-S01-T001; conflict_groups: theme; write_set: frontend/src/shared/styles/**, frontend/src/shared/design-system/**; risk: medium; verify_mode: human)_
- `P00-S02-T001` — Docker compose services _(depends_on: P00-S01-T001; conflict_groups: infra:compose; write_set: docker-compose.yml, backend/Dockerfile, frontend/Dockerfile; risk: medium; verify_mode: human)_

### Wave 3

- `P00-S01-T005` — i18n resources ES/EN/FR _(depends_on: P00-S01-T002, P00-S01-T004; conflict_groups: i18n; write_set: frontend/src/i18n/**, frontend/public/locales/**; risk: medium; verify_mode: human)_
- `P00-S02-T002` — Health live ready endpoints _(depends_on: P00-S02-T001; conflict_groups: api:health; write_set: backend/app/main.py, backend/app/api/router.py, backend/tests/test_health.py; risk: low; verify_mode: auto)_

### Wave 4

- `P00-S02-T003` — Verification data loader and reset _(depends_on: P00-S02-T002; conflict_groups: data:verification; write_set: backend/app/verification_data/**, scripts/dev-restart.sh; risk: medium; verify_mode: human)_
- `P01-S01-T001` — 0001_auth_users_employee_audit.py _(depends_on: P00-S02-T002; conflict_groups: db:migrations; write_set: backend/alembic/versions/0001_auth_users_employee_audit.py, backend/app/db/models/user.py, backend/app/db/models/auth.py; risk: medium; verify_mode: human)_

### Wave 5

- `P01-S02-T001` — POST /api/v1/auth/sign-up _(depends_on: P01-S01-T001; conflict_groups: api:auth; write_set: backend/app/auth/**, backend/tests/integration/test_auth_signup.py; risk: medium; verify_mode: human)_
- `P02-S01-T001` — 0002_ai_chat_rag_mcp_agents.py _(depends_on: P01-S01-T001; conflict_groups: db:migrations; write_set: backend/alembic/versions/0002_ai_chat_rag_mcp_agents.py, backend/app/db/models/**; risk: medium; verify_mode: human)_
- `P02-S02-T001` — Security encryption permissions rate limit _(depends_on: P01-S01-T001, P00-S01-T003; conflict_groups: security:core; write_set: backend/app/security/**, backend/tests/unit/test_security.py; risk: medium; verify_mode: human)_

### Wave 6

- `P01-S02-T002` — POST /api/v1/auth/sign-in _(depends_on: P01-S02-T001; conflict_groups: api:auth; write_set: backend/app/auth/**, backend/tests/integration/test_auth_signin.py; risk: medium; verify_mode: human)_
- `P01-S02-T005` — Forgot and reset password endpoints _(depends_on: P01-S02-T001; conflict_groups: api:auth, mail; write_set: backend/app/auth/reset_tokens.py, backend/app/mail/**, backend/tests/integration/test_password_reset.py; risk: medium; verify_mode: human)_
- `P02-S05-T001` — Admin AI providers and models endpoints _(depends_on: P02-S01-T001, P02-S02-T001; conflict_groups: api:admin-ai; write_set: backend/app/admin/providers.py, backend/app/admin/model_catalog.py, backend/tests/integration/test_admin_ai.py; risk: high; verify_mode: human)_
- `P02-S07-T001` — MCP server and tool endpoints _(depends_on: P02-S01-T001, P02-S02-T001; conflict_groups: api:mcp; write_set: backend/app/mcp/**, backend/tests/integration/test_mcp_registry.py; risk: high; verify_mode: human)_
- `P03-S01-T002` — SignUpPage _(depends_on: P01-S02-T001, P00-S01-T004, P00-S01-T005; conflict_groups: front:auth; write_set: frontend/src/pages/auth/SignUpPage.tsx; risk: medium; verify_mode: human)_

### Wave 7

- `P01-S02-T003` — POST /api/v1/auth/refresh _(depends_on: P01-S02-T002; conflict_groups: api:auth; write_set: backend/app/auth/refresh_tokens.py, backend/tests/integration/test_auth_refresh.py; risk: medium; verify_mode: human)_
- `P01-S02-T006` — POST /api/v1/auth/2fa/verify _(depends_on: P01-S02-T002; conflict_groups: api:auth; write_set: backend/app/auth/mfa.py, backend/tests/integration/test_mfa.py; risk: medium; verify_mode: human)_
- `P02-S04-T001` — RAG retriever + citation smoke _(depends_on: P02-S01-T001, P02-S05-T001; conflict_groups: ai:rag; write_set: backend/app/rag/**, backend/tests/ai/test_rag_retriever.py; risk: medium; verify_mode: human)_
- `P02-S05-T002` — Model test and usage endpoints _(depends_on: P02-S05-T001; conflict_groups: api:llm-gateway; write_set: backend/app/llm_gateway/**, backend/app/admin/usage.py, backend/tests/integration/test_model_test.py; risk: high; verify_mode: human)_
- `P03-S01-T003` — ForgotPasswordPage _(depends_on: P01-S02-T005, P00-S01-T004, P00-S01-T005; conflict_groups: front:auth; write_set: frontend/src/pages/auth/ForgotPasswordPage.tsx; risk: medium; verify_mode: human)_
- `P04-S02-T003` — McpServersPage _(depends_on: P02-S07-T001, P00-S01-T004; conflict_groups: front:mcp; write_set: frontend/src/pages/admin/mcp/McpServersPage.tsx; risk: high; verify_mode: human)_

### Wave 8

- `P01-S02-T004` — POST /api/v1/auth/logout _(depends_on: P01-S02-T003; conflict_groups: api:auth; write_set: backend/app/auth/router.py, backend/tests/integration/test_auth_logout.py; risk: medium; verify_mode: human)_
- `P01-S02-T007` — Current user and language endpoints _(depends_on: P01-S02-T006; conflict_groups: api:users; write_set: backend/app/users/**, backend/tests/integration/test_users_me.py; risk: medium; verify_mode: human)_
- `P02-S04-T002` — Celery vectorization worker _(depends_on: P02-S04-T001; conflict_groups: worker:rag; write_set: backend/app/workers/tasks_documents.py, backend/app/workers/tasks_embeddings.py, backend/tests/integration/test_vectorization_worker.py; risk: medium; verify_mode: human)_
- `P02-S08-T001` — Agents endpoints and DeepAgents/LangGraph smoke _(depends_on: P02-S07-T001, P02-S04-T001; conflict_groups: api:agents, ai:agents; write_set: backend/app/agents/**, backend/app/graphs/**, backend/tests/ai/test_agents_smoke.py; risk: high; verify_mode: human)_
- `P03-S01-T004` — ResetSentPage _(depends_on: P03-S01-T003; conflict_groups: front:auth; write_set: frontend/src/pages/auth/ResetSentPage.tsx; risk: medium; verify_mode: human)_
- `P04-S01-T001` — AdminDashboardPage _(depends_on: P02-S05-T002, P00-S01-T004; conflict_groups: front:admin; write_set: frontend/src/pages/admin/AdminDashboardPage.tsx; risk: medium; verify_mode: human)_
- `P04-S02-T004` — McpWizardPage _(depends_on: P02-S07-T001, P04-S02-T003; conflict_groups: front:mcp; write_set: frontend/src/pages/admin/mcp/McpWizardPage.tsx; risk: high; verify_mode: human)_
- `P04-S03-T002` — UsagePage _(depends_on: P02-S05-T002, P00-S01-T004; conflict_groups: front:usage; write_set: frontend/src/pages/admin/usage/UsagePage.tsx; risk: medium; verify_mode: human)_

### Wave 9

- `P01-S03-T001` — Auth state provider and protected route guards _(depends_on: P01-S02-T002, P01-S02-T006, P01-S02-T007, P00-S01-T002; conflict_groups: front:auth, router; write_set: frontend/src/features/auth/**, frontend/src/app/router.tsx; risk: medium; verify_mode: human)_
- `P02-S03-T001` — Chat conversation CRUD endpoints _(depends_on: P02-S01-T001, P01-S02-T007; conflict_groups: api:chat; write_set: backend/app/chat/**, backend/tests/integration/test_chat_conversations.py; risk: medium; verify_mode: human)_
- `P02-S06-T001` — RAG document endpoints _(depends_on: P02-S04-T002; conflict_groups: api:rag-docs; write_set: backend/app/rag/documents.py, backend/tests/integration/test_rag_documents.py; risk: high; verify_mode: human)_
- `P04-S01-T002` — AdminAiModelsPage _(depends_on: P02-S05-T001, P04-S01-T001; conflict_groups: front:admin-ai; write_set: frontend/src/pages/admin/ai/AdminAiModelsPage.tsx; risk: high; verify_mode: human)_
- `P04-S02-T005` — AgentsPage _(depends_on: P02-S08-T001, P04-S02-T003; conflict_groups: front:agents; write_set: frontend/src/pages/admin/agents/AgentsPage.tsx; risk: high; verify_mode: human)_
- `P04-S03-T001` — AuditLogPage _(depends_on: P01-S02-T007, P00-S01-T004; conflict_groups: front:audit; write_set: frontend/src/pages/admin/audit/AuditLogPage.tsx; risk: medium; verify_mode: human)_

### Wave 10

- `P02-S03-T002` — Chat streaming endpoint _(depends_on: P02-S03-T001, P02-S04-T001, P02-S05-T001; conflict_groups: api:chat-stream; write_set: backend/app/chat/streaming.py, backend/tests/integration/test_chat_stream.py; risk: high; verify_mode: human)_
- `P02-S06-T002` — RAG collection endpoints _(depends_on: P02-S06-T001; conflict_groups: api:rag-collections; write_set: backend/app/rag/collections.py, backend/tests/integration/test_rag_collections.py; risk: medium; verify_mode: human)_
- `P03-S01-T001` — SignInPage _(depends_on: P01-S03-T001, P00-S01-T004, P00-S01-T005; conflict_groups: front:auth; write_set: frontend/src/pages/auth/SignInPage.tsx, frontend/src/features/auth/**; risk: medium; verify_mode: human)_
- `P03-S02-T001` — ChatHomePage _(depends_on: P02-S03-T001, P01-S02-T007, P00-S01-T004, P00-S01-T005; conflict_groups: front:chat; write_set: frontend/src/pages/chat/ChatHomePage.tsx, frontend/src/features/chat/**; risk: high; verify_mode: human)_
- `P04-S01-T003` — ModelWizardPage _(depends_on: P02-S05-T001, P04-S01-T002; conflict_groups: front:admin-ai; write_set: frontend/src/pages/admin/ai/ModelWizardPage.tsx; risk: high; verify_mode: human)_
- `P04-S02-T001` — RagDocumentsPage _(depends_on: P02-S06-T001, P00-S01-T004; conflict_groups: front:rag; write_set: frontend/src/pages/admin/rag/RagDocumentsPage.tsx; risk: high; verify_mode: human)_
- `P05-S01-T006` — J105 MCP agents e2e _(depends_on: P04-S02-T003, P04-S02-T004, P04-S02-T005; conflict_groups: journey:J105; write_set: orchestrator-state/tasks/evidence/journeys/J105/**; risk: high; verify_mode: human)_

### Wave 11

- `P03-S01-T005` — TwoFactorPage _(depends_on: P01-S02-T006, P03-S01-T001; conflict_groups: front:auth; write_set: frontend/src/pages/auth/TwoFactorPage.tsx; risk: medium; verify_mode: human)_
- `P03-S02-T002` — ConversationPage _(depends_on: P02-S03-T002, P03-S02-T001; conflict_groups: front:chat; write_set: frontend/src/pages/chat/ConversationPage.tsx, frontend/src/features/chat/stream.ts; risk: high; verify_mode: human)_
- `P03-S02-T004` — AccountPage _(depends_on: P01-S02-T004, P01-S02-T007, P03-S02-T001; conflict_groups: front:account; write_set: frontend/src/pages/chat/AccountPage.tsx, frontend/src/features/user/**; risk: medium; verify_mode: human)_
- `P04-S01-T004` — ModelTestDrawer _(depends_on: P02-S05-T002, P04-S01-T003; conflict_groups: front:admin-ai; write_set: frontend/src/pages/admin/ai/ModelTestDrawer.tsx; risk: high; verify_mode: human)_
- `P04-S02-T002` — RagCollectionsPage _(depends_on: P02-S06-T002, P04-S02-T001; conflict_groups: front:rag; write_set: frontend/src/pages/admin/rag/RagCollectionsPage.tsx; risk: medium; verify_mode: human)_

### Wave 12

- `P03-S02-T003` — HistoryPage _(depends_on: P02-S03-T001, P03-S02-T002; conflict_groups: front:history; write_set: frontend/src/pages/chat/HistoryPage.tsx; risk: medium; verify_mode: human)_
- `P05-S01-T001` — J100 auth e2e _(depends_on: P03-S01-T001, P03-S01-T005, P03-S02-T001; conflict_groups: journey:J100; write_set: orchestrator-state/tasks/evidence/journeys/J100/**; risk: high; verify_mode: human)_
- `P05-S01-T002` — J101 chat RAG e2e _(depends_on: P03-S02-T001, P03-S02-T002, P02-S04-T001; conflict_groups: journey:J101; write_set: orchestrator-state/tasks/evidence/journeys/J101/**; risk: high; verify_mode: human)_
- `P05-S01-T004` — J103 admin AI e2e _(depends_on: P04-S01-T002, P04-S01-T003, P04-S01-T004; conflict_groups: journey:J103; write_set: orchestrator-state/tasks/evidence/journeys/J103/**; risk: high; verify_mode: human)_
- `P05-S01-T005` — J104 RAG admin e2e _(depends_on: P04-S02-T001, P04-S02-T002; conflict_groups: journey:J104; write_set: orchestrator-state/tasks/evidence/journeys/J104/**; risk: high; verify_mode: human)_

### Wave 13

- `P05-S01-T003` — J102 history language e2e _(depends_on: P03-S02-T002, P03-S02-T003, P03-S02-T004; conflict_groups: journey:J102; write_set: orchestrator-state/tasks/evidence/journeys/J102/**; risk: high; verify_mode: human)_
- `P05-S02-T001` — Audit endpoint and security hardening _(depends_on: P05-S01-T004, P05-S01-T005, P05-S01-T006; conflict_groups: api:audit, security:hardening; write_set: backend/app/admin/audit.py, backend/app/core/security_headers.py, backend/tests/integration/test_audit.py; risk: high; verify_mode: human)_
- `P05-S02-T002` — Observability and performance smoke _(depends_on: P05-S01-T002, P05-S01-T004; conflict_groups: observability; write_set: backend/app/core/metrics.py, backend/tests/perf/**; risk: medium; verify_mode: human)_

### Wave 14

- `P05-S02-T003` — Visual regression and design token gate _(depends_on: P05-S01-T001, P05-S01-T002, P05-S01-T003, P05-S01-T004, P05-S01-T005, P05-S01-T006; conflict_groups: theme, visual; write_set: frontend/src/shared/styles/**, docs/visualization/hilo-people/**; risk: medium; verify_mode: human)_

### Wave 15

- `P06-S01-T001` — Production build and compose smoke _(depends_on: P05-S02-T001, P05-S02-T002, P05-S02-T003; conflict_groups: release:build; write_set: frontend/dist/**, backend/Dockerfile, docker-compose.yml; risk: high; verify_mode: human)_

### Wave 16

- `P06-S01-T002` — Runbooks and README _(depends_on: P06-S01-T001; conflict_groups: release:docs; write_set: README.md, docs/runbooks/**; risk: medium; verify_mode: human)_

### Wave 17

- `P06-S01-T003` — Final acceptance _(depends_on: P06-S01-T001, P06-S01-T002; conflict_groups: release:final; write_set: orchestrator-state/tasks/evidence/final/**; risk: high; verify_mode: human)_

## Matrix

Rows are source nodes, columns are destination nodes; `1` means row -> column.

| from \ to | P00-S01-T001 | P00-S01-T002 | P00-S01-T003 | P00-S01-T004 | P00-S01-T005 | P00-S02-T001 | P00-S02-T002 | P00-S02-T003 | P01-S01-T001 | P01-S02-T001 | P01-S02-T002 | P01-S02-T003 | P01-S02-T004 | P01-S02-T005 | P01-S02-T006 | P01-S02-T007 | P01-S03-T001 | P02-S01-T001 | P02-S02-T001 | P02-S03-T001 | P02-S03-T002 | P02-S04-T001 | P02-S04-T002 | P02-S05-T001 | P02-S05-T002 | P02-S06-T001 | P02-S06-T002 | P02-S07-T001 | P02-S08-T001 | P03-S01-T001 | P03-S01-T002 | P03-S01-T003 | P03-S01-T004 | P03-S01-T005 | P03-S02-T001 | P03-S02-T002 | P03-S02-T003 | P03-S02-T004 | P04-S01-T001 | P04-S01-T002 | P04-S01-T003 | P04-S01-T004 | P04-S02-T001 | P04-S02-T002 | P04-S02-T003 | P04-S02-T004 | P04-S02-T005 | P04-S03-T001 | P04-S03-T002 | P05-S01-T001 | P05-S01-T002 | P05-S01-T003 | P05-S01-T004 | P05-S01-T005 | P05-S01-T006 | P05-S02-T001 | P05-S02-T002 | P05-S02-T003 | P06-S01-T001 | P06-S01-T002 | P06-S01-T003 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | 0 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P00-S01-T002 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P00-S01-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P00-S01-T004 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P00-S01-T005 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P00-S02-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P00-S02-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P00-S02-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S01-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S02-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S02-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S02-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S02-T004 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S02-T005 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S02-T006 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S02-T007 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P01-S03-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S01-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S02-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S03-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S03-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S04-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S04-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S05-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S05-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S06-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S06-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S07-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P02-S08-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S01-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S01-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S01-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S01-T004 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S01-T005 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S02-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S02-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S02-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P03-S02-T004 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S01-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S01-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S01-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S01-T004 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S02-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S02-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S02-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S02-T004 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S02-T005 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S03-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P04-S03-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P05-S01-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| P05-S01-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| P05-S01-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| P05-S01-T004 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| P05-S01-T005 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 |
| P05-S01-T006 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 |
| P05-S02-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| P05-S02-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| P05-S02-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| P06-S01-T001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| P06-S01-T002 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| P06-S01-T003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
