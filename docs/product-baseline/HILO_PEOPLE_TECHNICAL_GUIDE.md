# Hilo People — Technical Guide (large app sin baseline)

Perfil: **large-without-base**. Contrato técnico completo para una app nueva React + FastAPI + PostgreSQL/pgvector.

## 1. Overview específico

```text
Empleado People
  │
  ▼
React Mobile Web: Login / Chat / History / Account
  │  Authorization Bearer access token + refresh HttpOnly
  ▼
FastAPI app/api/router.py
  ├─ auth/       JWT propio, refresh rotation, 2FA, reset password
  ├─ users/      perfil empleado, idioma, marca, centro, sociedad
  ├─ chat/       conversaciones, mensajes, streaming SSE/fetch
  │    ├─ rag/          retrieval pgvector + citas
  │    └─ llm_gateway/  LiteLLM proxy/client
  ├─ admin/      gobierno de proveedores, modelos, credenciales, audit, usage
  ├─ rag/        documentos, chunking, embeddings, colecciones, Celery
  ├─ mcp/        servidores MCP externos, discovery, policies, approvals
  ├─ agents/     DeepAgents runtime + tools RAG/MCP/Admin
  └─ graphs/     LangGraph workflows y checkpointer opcional
       │
       ▼
PostgreSQL 18 + pgvector + pgcrypto, Redis, Celery, LiteLLM proxy
```

El empleado entra y aterriza en `/chat`. Admin AI es una superficie independiente para People Tech: modelos LiteLLM, RAG, MCP, agentes, uso y auditoría.

## 2. Stack — contrato completo

- Frontend: React + Vite + TypeScript, React Router, TanStack Query, React Hook Form, Zod, i18next.
- Backend: Python + FastAPI, SQLAlchemy async, Alembic, Pydantic, JWT propio, SSE/fetch streaming.
- DB: PostgreSQL + pgvector + pgcrypto.
- AI: LiteLLM gateway, LangChain RAG, LangGraph, DeepAgents, MCP client.
- Async: Redis + Celery para vectorización y sync MCP.
- Tests: pytest backend, npm test/build frontend, journeys humanos en navegador.

### 2.0 Library Discovery Pass

| Área (ref §11.0) | Paquete propuesto | URL oficial | Frontend / Backend | Justificación + slice ahorrado | Alternativa descartada | Versión | Introducida en slice |
|---|---|---|---|---|---|---|---|
| Forms y validación React | `react-hook-form`, `zod`, `@hookform/resolvers` | npm official docs | Frontend | Formularios auth/admin con validación tipada; ahorra componentes custom | Validación manual por pantalla | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T002 |
| Data fetching/cache React | `@tanstack/react-query` | tanstack.com/query | Frontend | Cache de user, chat history, modelos, RAG y MCP | Fetch manual + estados duplicados | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T002 |
| Routing React | `react-router-dom` | reactrouter.com | Frontend | Rutas protegidas auth/admin y deep links web | Router propio | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T002 |
| i18n frontend | `i18next`, `react-i18next`, `i18next-browser-languagedetector` | i18next.com, react.i18next.com | Frontend | ES/EN/FR con namespaces y fallback | Diccionarios custom ad hoc | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T002 |
| PDF backend | `pypdf` | pypdf.readthedocs.io | Backend | Extracción texto PDF nativo para RAG | OCR desde V1 | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| Office backend | `python-docx` | python-docx.readthedocs.io | Backend | Extracción DOCX de políticas People | Parser XML propio | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| Jobs/queues | `celery`, `redis` | docs.celeryq.dev | Backend | Vectorización async y sync MCP | BackgroundTasks de FastAPI | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| Email custom | `resend` + SMTP fallback | resend.com/docs | Backend | Reset password y avisos con plantillas por idioma | SMTP único sin proveedor | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| Observabilidad backend | `structlog`, `prometheus-client` | structlog.org, prometheus client docs | Backend | request_id, métricas coste/latencia, logs sin PII | logging stdlib plano | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| Storage S3/MinIO | `boto3` | boto3.amazonaws.com | Backend | Guardar documentos originales de RAG | Filesystem local en producción | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| Postgres/pgvector | `pgvector` | github.com/pgvector/pgvector-python | Backend/DB | embeddings en PostgreSQL | Vector DB separada en V1 | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| AI Gateway | `litellm` | docs.litellm.ai | Backend | proxy unificado modelos/proveedores | Clientes OpenAI/Anthropic separados | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| RAG | `langchain` | python.langchain.com | Backend | loaders, splitters y retriever | Splitters propios extensos | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| LangGraph | `langgraph` | langchain-ai.github.io/langgraph | Backend | workflows con estado y approvals | FSM propia | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| DeepAgents | `deepagents` | github/docs oficiales del paquete | Backend | agentes con tools RAG/MCP/Admin | Agent loop propio | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |
| MCP client | `mcp==1.27.1` (not adopted in P02-S07-T001, see resolved official-doc note) | modelcontextprotocol.io | Backend | conectar servidores MCP externos | JSON-RPC artesanal | reservado — adopción decidida en slice MCP integration posterior | P00-S01-T003 |
| Token counting | `tiktoken` | github.com/openai/tiktoken | Backend | estimación coste y límites | conteo aproximado manual | pendiente — official-docs-researcher confirmará al implementar | P00-S01-T003 |

### 2.1 Stack — paquetes auxiliares

| Componente | Paquete | URL oficial | Por qué |
|---|---|---|---|
| Lint frontend | `eslint`, `typescript-eslint` | eslint.org | calidad TS/React |
| Test frontend | `vitest`, `@testing-library/react` | vitest.dev | tests de componentes y stores |
| Lint backend | `ruff`, `mypy` | docs.astral.sh/ruff, mypy.readthedocs.io | lint/type-check Python |
| DB test | `pytest-asyncio`, `httpx` | docs pytest/httpx | tests async FastAPI |

## 3. Comandos — adiciones

```bash
./scripts/setup-from-scratch.sh --check
./scripts/dev-restart.sh --soft
./scripts/dev-restart.sh --reset
npm --prefix frontend install
npm --prefix frontend run dev -- --host 0.0.0.0
npm --prefix frontend run test -- --run
npm --prefix frontend run build
pytest backend/tests
ruff check backend
mypy backend/app
alembic upgrade head
python -m app.verification_data.bootstrap --source data/verification
python -m app.scripts.ingest_people_docs --source data/verification/people_docs
bash scripts/check-design-tokens.sh
```

## 4. Estructura del proyecto — adiciones

```text
frontend/
  src/
    app/App.tsx
    app/router.tsx
    app/providers.tsx
    i18n/index.ts
    i18n/languages.ts
    layouts/AuthLayout.tsx
    layouts/UserMobileLayout.tsx
    layouts/AdminDesktopLayout.tsx
    pages/auth/SignInPage.tsx
    pages/auth/SignUpPage.tsx
    pages/auth/ForgotPasswordPage.tsx
    pages/auth/ResetSentPage.tsx
    pages/auth/TwoFactorPage.tsx
    pages/chat/ChatHomePage.tsx
    pages/chat/ConversationPage.tsx
    pages/chat/HistoryPage.tsx
    pages/chat/AccountPage.tsx
    pages/admin/AdminDashboardPage.tsx
    pages/admin/ai/AdminAiModelsPage.tsx
    pages/admin/ai/ModelWizardPage.tsx
    pages/admin/ai/ModelTestDrawer.tsx
    pages/admin/rag/RagDocumentsPage.tsx
    pages/admin/rag/RagCollectionsPage.tsx
    pages/admin/mcp/McpServersPage.tsx
    pages/admin/mcp/McpWizardPage.tsx
    pages/admin/agents/AgentsPage.tsx
    pages/admin/audit/AuditLogPage.tsx
    pages/admin/usage/UsagePage.tsx
    features/auth/
    features/user/
    features/chat/
    features/admin-ai/
    features/rag/
    features/mcp/
    shared/api/http.ts
    shared/design-system/
    shared/styles/tokens.css
    shared/styles/reset.css
  public/locales/es/*.json
  public/locales/en/*.json
  public/locales/fr/*.json

docs/
  visualization/hilo-people/
    README.md
    reference-preview-notes.md

backend/
  app/
    main.py
    core/config.py
    api/router.py
    auth/
    users/
    admin/
    chat/
    llm_gateway/
    rag/
    mcp/
    agents/
    graphs/
    db/models/
    db/repositories/
    storage/
    mail/
    security/
    workers/
    i18n/
    verification_data/bootstrap.py
  tests/
  alembic/
```

## 5. Arquitectura

### 5.1 Componentes nuevos

| Módulo | Responsabilidad | Depende de |
|---|---|---|
| `auth` | JWT, passwords Argon2, 2FA, refresh, reset | `db`, `security`, `mail`, `audit` |
| `users` | perfil empleado, idioma y preferencias | `auth`, `db` |
| `chat` | conversaciones, mensajes, SSE/fetch | `llm_gateway`, `rag`, `db`, `users` |
| `llm_gateway` | cliente LiteLLM, registry modelos, pricing | `admin`, `security` |
| `rag` | documentos, chunking, embeddings, pgvector | `storage`, `workers`, `llm_gateway` |
| `mcp` | registry MCP, auth, transports, tools, policies | `security`, `workers`, `audit` |
| `agents` | DeepAgents runtime y tool adapters | `mcp`, `rag`, `llm_gateway`, `graphs` |
| `graphs` | LangGraph workflows y checkpointer | `db`, `agents` |
| `admin` | gobierno proveedores/modelos/RAG/MCP/audit/usage | `auth`, `security`, `llm_gateway`, `rag`, `mcp` |

### 5.2 Flujo de datos específico

```text
Pregunta empleado → ChatHomePage
  → POST /api/v1/chat/conversations
  → POST /api/v1/chat/conversations/{id}/stream
    → get_current_user + preferred_language
    → rag.retriever.retrieve(query, language, brand, country)
    → llm_gateway.stream_chat(model_default, context, prompt)
    → SSE chunks al frontend
    → persist messages + citations + usage
```

```text
Admin sube documento → RagDocumentsPage
  → POST /api/v1/admin/rag/documents
    → storage.save(original)
    → documents row + document_versions row
  → POST /api/v1/admin/rag/documents/{id}/index
    → Celery task_extract_chunk_embed
    → document_chunks + document_embeddings
```

### 5.3 Decisiones de diseño

| Decisión | Alternativas | Elegida | Razón |
|---|---|---|---|
| Auth | Clerk/Auth0/Supabase Auth | JWT propio + refresh HttpOnly | control total, roles y auditoría corporativa |
| Chat streaming | EventSource nativo | fetch stream parser SSE | permite header Authorization y control de errores |
| LiteLLM | SDKs directos por proveedor | proxy/gateway LiteLLM | unifica proveedores, routing y coste |
| RAG | vector DB externa | PostgreSQL + pgvector | simplicidad operativa y joins con permisos |
| MCP | dentro de agents | módulo `mcp/` independiente | gobierno y auditoría antes de exponer tools a agentes |
| LangGraph | obligatorio en chat | disponible para workflows/approvals | chat simple no necesita complejidad de graph en V1 |

## 6. Interfaces — adiciones

### 6.1 Rutas/pantallas frontend

| Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/provider | Estados UI obligatorios | Next action | Slice ID | Descripción |
|---|---|---|---|---|---|---|---|---|---|
| /auth/sign-in | SignInPage | No | J100 | POST /api/v1/auth/sign-in | authStore, loginForm | loading, error_network, error_validation, permission_denied, success | /auth/2fa o /chat | P03-S01-T001 | Login email/password editorial móvil |
| /auth/sign-up | SignUpPage | No | J100 | POST /api/v1/auth/sign-up | signUpForm | loading, error_network, error_validation, permission_denied, success | /auth/2fa | P03-S01-T002 | Registro con email corporativo y legal |
| /auth/forgot-password | ForgotPasswordPage | No | J100 | POST /api/v1/auth/forgot-password | forgotForm | loading, error_network, error_validation, success | /auth/reset-sent | P03-S01-T003 | Solicitud enlace reset |
| /auth/reset-sent | ResetSentPage | No | J100 | (none) | authUiState | loading, empty, error_network, success | /auth/sign-in | P03-S01-T004 | Confirmación email enviado |
| /auth/2fa | TwoFactorPage | No | J100 | POST /api/v1/auth/2fa/verify | twoFactorForm | loading, error_network, error_validation, permission_denied, success | /chat | P03-S01-T005 | Inputs 6 dígitos |
| /chat | ChatHomePage | Sí employee | J100, J101 | GET /api/v1/users/me, POST /api/v1/chat/conversations | currentUserQuery, chatHomeState | loading, empty, error_network, permission_denied, success | /chat/:conversationId | P03-S02-T001 | Home del empleado con prompts sugeridos |
| /chat/:conversationId | ConversationPage | Sí employee | J101, J102 | GET /api/v1/chat/conversations/{id}, POST /api/v1/chat/conversations/{id}/stream | conversationQuery, streamController | loading, empty, streaming, error_network, error_validation, permission_denied, success | /history o seguir preguntando | P03-S02-T002 | Conversación con citas inline |
| /history | HistoryPage | Sí employee | J102 | GET /api/v1/chat/conversations | historyQuery | loading, empty, error_network, permission_denied, success | /chat/:conversationId | P03-S02-T003 | Historial agrupado por fecha |
| /account | AccountPage | Sí employee | J102 | GET /api/v1/users/me, PATCH /api/v1/users/me/language, POST /api/v1/auth/logout | currentUserQuery, languageStore | loading, error_network, error_validation, permission_denied, success | /chat o /auth/sign-in | P03-S02-T004 | Cuenta, idioma y logout |
| /admin | AdminDashboardPage | Sí admin | J103 | GET /api/v1/admin/usage | adminDashboardQuery | loading, empty, error_network, permission_denied, success | /admin/ai/models | P04-S01-T001 | Vista resumen Admin AI |
| /admin/ai/models | AdminAiModelsPage | Sí admin | J103 | GET /api/v1/admin/ai/providers, GET /api/v1/admin/ai/models | adminAiQuery | loading, empty, error_network, permission_denied, success | /admin/ai/models/new | P04-S01-T002 | Tabla modelos LiteLLM |
| /admin/ai/models/new | ModelWizardPage | Sí admin | J103 | POST /api/v1/admin/ai/providers, GET /api/v1/admin/ai/models | modelWizardStore | loading, empty, error_network, error_validation, permission_denied, success | /admin/ai/models/:modelId/test | P04-S01-T003 | Wizard proveedor/modelos |
| /admin/ai/models/:modelId/test | ModelTestDrawer | Sí admin | J103 | POST /api/v1/admin/ai/models/{id}/test, PATCH /api/v1/admin/ai/models/{id} | testDrawerStore | loading, error_network, error_validation, permission_denied, success | /admin/ai/models | P04-S01-T004 | Playground lateral |
| /admin/rag/documents | RagDocumentsPage | Sí admin | J104 | POST /api/v1/admin/rag/documents, GET /api/v1/admin/rag/documents, POST /api/v1/admin/rag/documents/{id}/index | ragDocumentsQuery, uploadStore | loading, empty, uploading, error_network, error_validation, permission_denied, success | /admin/rag/collections | P04-S02-T001 | Subir e indexar documentos |
| /admin/rag/collections | RagCollectionsPage | Sí admin | J104 | GET /api/v1/admin/rag/collections, PATCH /api/v1/admin/rag/collections/{id} | ragCollectionsQuery | loading, empty, error_network, error_validation, permission_denied, success | /admin/rag/documents | P04-S02-T002 | Colecciones y verticales |
| /admin/ai/mcp | McpServersPage | Sí admin | J105 | GET /api/v1/admin/ai/mcp/servers, POST /api/v1/admin/ai/mcp/servers/{id}/sync | mcpServersQuery | loading, empty, syncing, error_network, permission_denied, success | /admin/ai/mcp/new | P04-S02-T003 | Lista servidores MCP |
| /admin/ai/mcp/new | McpWizardPage | Sí admin | J105 | POST /api/v1/admin/ai/mcp/servers | mcpWizardStore | loading, error_network, error_validation, permission_denied, success | /admin/ai/mcp | P04-S02-T004 | Wizard conectar MCP |
| /admin/ai/agents | AgentsPage | Sí admin | J105 | GET /api/v1/admin/ai/agents, PATCH /api/v1/admin/ai/agents/{id}/tools, POST /api/v1/agents/runs | agentsQuery | loading, empty, error_network, error_validation, permission_denied, success | /admin/ai/mcp | P04-S02-T005 | Asignación tools a agentes |
| /admin/audit | AuditLogPage | Sí auditor | J103, J104, J105 | GET /api/v1/admin/audit | auditQuery | loading, empty, error_network, permission_denied, success | abrir detalle evento | P04-S03-T001 | Auditoría |
| /admin/usage | UsagePage | Sí admin | J103 | GET /api/v1/admin/usage | usageQuery | loading, empty, error_network, permission_denied, success | /admin/ai/models | P04-S03-T002 | Coste y latencias |

### 6.2 Endpoints API nuevos

Envelope general: `{data, meta, errors}`. Errores: `{code, message, field, details}`.

| Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
|---|---|---|---|---|---|---|---|---|
| GET | /health | — | `{data:{status}}` | No | 500 | health checks | no DB | P00-S02-T002 |
| GET | /live | — | `{data:{status}}` | No | 500 | health checks | no DB | P00-S02-T002 |
| GET | /ready | — | `{data:{db,redis,litellm}}` | No | 503 | health checks | DB/Redis ping | P00-S02-T002 |
| POST | /api/v1/auth/sign-up | `{email,password,full_name,legal_acceptance}` | `{data:{mfa_required,user_id}}` | No | 400,409,422 | SignUpPage / J100 | users, employee_profiles, audit_logs | P01-S02-T001 |
| POST | /api/v1/auth/sign-in | `{email,password}` | `{data:{mfa_required,access_token?}}` | No | 400,401,423 | SignInPage / J100 | refresh_tokens, audit_logs | P01-S02-T002 |
| POST | /api/v1/auth/refresh | cookie refresh | `{data:{access_token}}` | Refresh cookie | 401 | authStore | refresh_tokens | P01-S02-T003 |
| POST | /api/v1/auth/logout | — | 204 | Sí | 401 | AccountPage | refresh_tokens revoke, audit_logs | P01-S02-T004 |
| POST | /api/v1/auth/forgot-password | `{email}` | `{data:{sent:true}}` | No | 400,429 | ForgotPasswordPage | password_reset_tokens, mail | P01-S02-T005 |
| POST | /api/v1/auth/reset-password | `{token,password}` | `{data:{reset:true}}` | No | 400,410 | Reset password flow | users, password_reset_tokens | P01-S02-T005 |
| POST | /api/v1/auth/2fa/verify | `{challenge_id,code}` | `{data:{access_token,user}}` | No | 400,401,410 | TwoFactorPage / J100 | mfa_totp_secrets, refresh_tokens, audit_logs | P01-S02-T006 |
| GET | /api/v1/users/me | — | `{data:UserProfile}` | Sí | 401 | ChatHomePage, AccountPage / J100,J102 | users, employee_profiles read | P01-S02-T007 |
| PATCH | /api/v1/users/me/language | `{language}` | `{data:UserProfile}` | Sí | 400,401,422 | AccountPage / J102 | users.preferred_language | P01-S02-T007 |
| GET | /api/v1/chat/conversations | `cursor,limit` | `{data:[Conversation],meta:{pagination}}` | Sí employee | 401 | HistoryPage / J102 | conversations read | P02-S03-T001 |
| POST | /api/v1/chat/conversations | `{initial_message?,language?}` | `{data:{conversation_id}}` | Sí employee | 400,401 | ChatHomePage / J101 | conversations, messages | P02-S03-T001 |
| GET | /api/v1/chat/conversations/{id} | — | `{data:ConversationDetail}` | Sí employee | 401,403,404 | ConversationPage / J101,J102 | conversations, messages, message_citations read | P02-S03-T001 |
| POST | /api/v1/chat/conversations/{id}/stream | `{message}` | `text/event-stream` | Sí employee | 400,401,403,404,502 | ConversationPage / J101 | messages, message_citations, llm_usage_logs | P02-S03-T002 |
| GET | /api/v1/admin/ai/providers | — | `{data:[AiProvider]}` | Sí admin | 401,403 | AdminAiModelsPage / J103 | ai_providers read | P02-S05-T001 |
| POST | /api/v1/admin/ai/providers | `{provider_type,name,credentials}` | `{data:AiProvider}` | Sí admin | 400,401,403,422 | ModelWizardPage / J103 | ai_providers, ai_provider_credentials, audit_logs | P02-S05-T001 |
| GET | /api/v1/admin/ai/models | `provider_id?` | `{data:[AiModel]}` | Sí admin | 401,403 | AdminAiModelsPage, ModelWizardPage / J103 | ai_models read | P02-S05-T001 |
| PATCH | /api/v1/admin/ai/models/{id} | `{enabled?,is_default?}` | `{data:AiModel}` | Sí admin | 400,401,403,404 | ModelTestDrawer / J103 | ai_models, audit_logs | P02-S05-T001 |
| POST | /api/v1/admin/ai/models/{id}/test | `{prompt}` | `{data:{output,latency_ms,cost}}` | Sí admin | 400,401,403,404,502 | ModelTestDrawer / J103 | ai_model_tests, llm_usage_logs | P02-S05-T002 |
| GET | /api/v1/admin/usage | `from,to,group_by` | `{data:UsageSummary}` | Sí admin | 401,403,422 | AdminDashboardPage, UsagePage / J103 | llm_usage_logs read | P02-S05-T002 |
| POST | /api/v1/admin/rag/documents | multipart + metadata | `{data:Document}` | Sí admin | 400,401,403,413,422 | RagDocumentsPage / J104 | documents, document_versions, storage | P02-S06-T001 |
| GET | /api/v1/admin/rag/documents | `collection_id?,status?` | `{data:[Document]}` | Sí admin | 401,403 | RagDocumentsPage / J104 | documents read | P02-S06-T001 |
| POST | /api/v1/admin/rag/documents/{id}/index | — | `{data:{job_id,status}}` | Sí admin | 401,403,404,409 | RagDocumentsPage / J104 | vectorization_jobs enqueue | P02-S06-T001 |
| GET | /api/v1/admin/rag/collections | — | `{data:[RagCollection]}` | Sí admin | 401,403 | RagCollectionsPage / J104 | rag_collections read | P02-S06-T002 |
| PATCH | /api/v1/admin/rag/collections/{id} | `{name?,vertical?,enabled?}` | `{data:RagCollection}` | Sí admin | 400,401,403,404 | RagCollectionsPage / J104 | rag_collections, audit_logs | P02-S06-T002 |
| GET | /api/v1/admin/ai/mcp/servers | — | `{data:[McpServer]}` | Sí admin | 401,403 | McpServersPage / J105 | mcp_servers read | P02-S07-T001 |
| POST | /api/v1/admin/ai/mcp/servers | `{name,transport,endpoint,auth}` | `{data:McpServer}` | Sí admin | 400,401,403,422 | McpWizardPage / J105 | mcp_servers, mcp_credentials, audit_logs | P02-S07-T001 |
| POST | /api/v1/admin/ai/mcp/servers/{id}/sync | — | `{data:{tools_count,status}}` | Sí admin | 401,403,404,502 | McpServersPage / J105 | mcp_tools, mcp_resources, mcp_prompts | P02-S07-T001 |
| PATCH | /api/v1/admin/ai/mcp/tools/{id} | `{enabled,requires_approval,risk_level}` | `{data:McpTool}` | Sí admin | 400,401,403,404 | McpServersPage / J105 | mcp_tools, audit_logs | P02-S07-T001 |
| GET | /api/v1/admin/ai/agents | — | `{data:[Agent]}` | Sí admin | 401,403 | AgentsPage / J105 | agents, mcp_agent_bindings read | P02-S08-T001 |
| PATCH | /api/v1/admin/ai/agents/{id}/tools | `{tool_ids}` | `{data:Agent}` | Sí admin | 400,401,403,404 | AgentsPage / J105 | mcp_agent_bindings, audit_logs | P02-S08-T001 |
| POST | /api/v1/agents/runs | `{agent_id,input}` | `{data:{run_id,status}}` | Sí admin | 400,401,403,404,502 | AgentsPage / J105 | agent_runs, mcp_tool_invocations | P02-S08-T001 |
| GET | /api/v1/admin/audit | `from,to,actor,action` | `{data:[AuditLog]}` | Sí auditor | 401,403 | AuditLogPage | audit_logs read | P05-S02-T001 |

### 6.3 Modelos de datos nuevos

**User**
```python
class User(BaseModel):
    id: UUID
    email: EmailStr
    password_hash: str
    full_name: str
    status: Literal['active','disabled','pending']
    preferred_language: Literal['es','en','fr']
    created_at: datetime
```

**EmployeeProfile**
```python
class EmployeeProfile(BaseModel):
    user_id: UUID
    employee_id: str
    brand: str
    society: str
    center: str
    country: str
    department: str
```

**Conversation, Message, MessageCitation**
```python
class Conversation(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    language: Literal['es','en','fr']
    created_at: datetime
    updated_at: datetime

class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal['user','assistant','system']
    content: str
    token_count: int | None
    created_at: datetime

class MessageCitation(BaseModel):
    id: UUID
    message_id: UUID
    document_id: UUID
    chunk_id: UUID
    label: str
    score: float
```

**AiProvider, AiModel, RagCollection, Document, DocumentChunk, McpServer, Agent** se representan como Pydantic schemas en sus módulos y TypeScript DTOs en `frontend/src/features/*/*.types.ts`.

### 6.4 Formato de errores específico

Códigos principales: `AUTH_INVALID_CREDENTIALS`, `AUTH_MFA_REQUIRED`, `AUTH_SESSION_EXPIRED`, `AUTH_FORBIDDEN`, `CHAT_STREAM_FAILED`, `RAG_DOCUMENT_INVALID`, `RAG_INDEX_IN_PROGRESS`, `AI_PROVIDER_TEST_FAILED`, `MCP_SERVER_UNREACHABLE`, `MCP_TOOL_REQUIRES_APPROVAL`, `AGENT_RUN_FAILED`.

### 6.4 Navigation Contract

Rutas públicas: `/auth/sign-in`, `/auth/sign-up`, `/auth/forgot-password`, `/auth/reset-sent`, `/auth/2fa`. Rutas empleado: `/chat`, `/chat/:conversationId`, `/history`, `/account`. Rutas admin: `/admin`, `/admin/ai/models`, `/admin/ai/models/new`, `/admin/ai/models/:modelId/test`, `/admin/rag/documents`, `/admin/rag/collections`, `/admin/ai/mcp`, `/admin/ai/mcp/new`, `/admin/ai/agents`, `/admin/audit`, `/admin/usage`. Deep links web respetan auth guard; si no hay sesión, redirigen a sign-in y vuelven al destino tras login.

### 6.5 Verification Data Contract

| Flow/Journey | Persona/Rol | Datos reales/proporcionados requeridos | Carga de datos reales/proporcionados | Reset/Cleanup | Slices/Journeys |
|---|---|---|---|---|---|
| J100 auth-login | `data/verification/users/employee_primary.json.email` employee | usuario confirmado, MFA secret reales/proporcionados desde `data/verification`, refresh cookie | `python -m app.verification_data.bootstrap --source data/verification --only auth` | `scripts/dev-restart.sh --reset` | J100, P01-S02, P03-S01 |
| J101 chat-rag | empleado + colección activa | documento política vacaciones ES indexado, modelo chat de verificación `gemini-2.5-flash` activo (Google AI Studio enrutado vía LiteLLM proxy; requiere `GEMINI_API_KEY` en env) | `python -m app.verification_data.bootstrap --source data/verification --only rag_chat` | truncate conversations/messages/citations | J101, P02-S03, P02-S04, P03-S02 |
| J102 history-language | empleado con conversación previa | 2 conversaciones persistidas, idioma inicial `es` | `python -m app.verification_data.bootstrap --source data/verification --only history` | reset user language to es | J102, P03-S02-T003, P03-S02-T004 |
| J103 admin-ai | `data/verification/users/admin_peopletech.json.email` admin | proveedor de verificación, credencial reales/proporcionados cifrable desde `data/verification`, modelos desde `data/verification` | `python -m app.verification_data.bootstrap --source data/verification --only admin_ai` | delete ai_provider test rows | J103, P02-S05, P04-S01 |
| J104 rag-admin | admin | `politica_vacaciones_es.pdf`, colección `politicas_tienda` | `python -m app.verification_data.bootstrap --source data/verification --only rag_docs` | delete documents/chunks/embeddings/jobs | J104, P02-S06, P04-S02 |
| J105 mcp-agents | admin | MCP sandbox autorizado HTTP read-only, agente `people_helper` | `python -m app.verification_data.bootstrap --source data/verification --only mcp_agents` | delete mcp_servers/tools/bindings/runs | J105, P02-S07, P02-S08, P04-S02 |

## 7. Theme & Design System

Tokens: `--color-bg #f5f3ee`, `--color-ink #0a0a0a`, `--color-paper #ffffff`, `--font-display Bodoni Moda/Didot/serif`, `--font-sans Helvetica Neue/Arial/system`, `--hairline 1px solid rgba(10,10,10,.22)`, `--tracking-label .18em`, `--radius 0`. Componentes: `Wordmark`, `TrackedLabel`, `EditorialInput`, `SolidCTA`, `HairlineTable`, `StatusDot`, `MobileFrame`, `AdminShell`, `CitationInline`.

### 7.1 Visual Implementation Contract

El diseño se implementa en código real, no copiando HTML estático. El source-of-truth visual es `UX_CONTRACT.md` + `frontend/src/shared/styles/tokens.css` + `frontend/src/shared/design-system/`. `dist/hilo-people-preview.html` y `docs/visualization/hilo-people/` son referencias/evidencias para comparar dirección visual, pero no sustituyen componentes React ni estados reales.

Toda pantalla frontend debe:

- importar tokens desde `frontend/src/shared/styles/tokens.css`;
- usar componentes base del design system cuando apliquen;
- cubrir los estados UI declarados en `UX_CONTRACT.md`;
- usar backend real o datos reales/proporcionados persistidos;
- registrar evidencia visual en el handoff;
- evitar estilos fuera de contrato: radius, shadows, badges de color decorativo, datos hardcoded o textos fuera de i18n.

El handoff de cada slice frontend debe incluir:

```text
VISUAL_CONTRACT_CHECK:
- route: <route>
- tokens_used: yes|no
- base_components_used: yes|no
- required_states_covered: <states>
- real_data_or_backend_used: yes|no
- i18n_checked: yes|no
- evidence: orchestrator-state/tasks/evidence/<TASK_ID>/<file>
- deviations: none|<explicación y follow-up si aplica>
```

La gate visual final `P05-S02-T003` consolida capturas permanentes en `docs/visualization/hilo-people/` y comprueba que login mobile, chat mobile, history/account mobile, Admin AI, Admin RAG y MCP/Agents respetan tokens, componentes y estados.

## 8. Logging y Observabilidad

Usar `structlog` con `request_id`, `user_id_hash`, `role`, `route`, `latency_ms`, `status_code`. Prometheus: chat stream duration, LLM tokens/cost, RAG retrieval duration, vectorization jobs, MCP invocations, auth attempts. Audit log persistente para acciones críticas.

## 9. Testing

### 9.1 Convenciones específicas

- Tests backend en `backend/tests/integration` usan DB Postgres de test, no SQLite para RAG/pgvector.
- Documentos reales/proporcionados de verificación en `backend/tests/data/verification/people_docs/`.
- Tests frontend usan Vitest/Testing Library con API client test doubles solo para unit tests; journeys usan backend real.
- Edge cases sintéticos permitidos: `empty`, `error_network`, `permission_denied`, payload inválido.

## 10. Backend / API — adiciones

### 10.1 Módulos del backend

Ver §5.1. Cada módulo tiene `router.py`, `service.py`, `schemas.py`; módulos con persistencia usan `db/repositories` y modelos SQLAlchemy en `db/models`.

### 10.2 Auth strategy

JWT propio. Access token Bearer de vida corta. Refresh token en cookie `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth`, guardado hasheado y rotado. Password hashing con Argon2. Claims: `sub`, `email`, `roles`, `preferred_language`, `employee_profile_id`, `iat`, `exp`, `jti`. Guards: `require_user`, `require_admin`, `require_auditor`, `require_role`.

**Refresh cookie Path contract (P01-S02-T011)**: el atributo `Path` de la cookie de refresh es `/api/v1/auth` — no `/auth` (sub-prefix sin el prefix real), no `/` (demasiado amplio). Justificación RFC 6265 §5.4: el navegador solo envía la cookie a URLs cuyo path comience por el valor del atributo Path. Los endpoints reales viven en `/api/v1/auth/{sign-in,refresh,logout,2fa/verify}`, por lo que `Path=/api/v1/auth` es el mínimo viable que satisface el principio de menor exposición (la cookie no viaja a `/api/v1/users/*`, `/api/v1/chat/*` ni ningún otro módulo). Atributos byte-idénticos en setter (`_set_refresh_cookie`, Max-Age=TTL) y clearer (`_clear_refresh_cookie`, Max-Age=0) — implementado en `backend/app/auth/routers/_helpers.py::_REFRESH_COOKIE_PATH`.

### 10.3 DB Schema — tablas nuevas

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  preferred_language TEXT NOT NULL DEFAULT 'es',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT users_language_chk CHECK (preferred_language IN ('es','en','fr'))
);

CREATE TABLE employee_profiles (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  employee_id TEXT NOT NULL UNIQUE,
  brand TEXT NOT NULL,
  society TEXT NOT NULL,
  center TEXT NOT NULL,
  country TEXT NOT NULL,
  department TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE roles (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT UNIQUE NOT NULL);
CREATE TABLE permissions (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), key TEXT UNIQUE NOT NULL);
CREATE TABLE user_roles (user_id UUID REFERENCES users(id) ON DELETE CASCADE, role_id UUID REFERENCES roles(id) ON DELETE CASCADE, PRIMARY KEY(user_id, role_id));
CREATE TABLE refresh_tokens (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ);
CREATE TABLE mfa_totp_secrets (user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, secret_encrypted TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT false);
CREATE TABLE password_reset_tokens (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, used_at TIMESTAMPTZ);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL, entity_type TEXT, entity_id UUID, metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conversations (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'es', created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX conversations_user_updated_idx ON conversations(user_id, updated_at DESC);
CREATE TABLE messages (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, token_count INT, created_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX messages_conversation_created_idx ON messages(conversation_id, created_at);
CREATE TABLE message_citations (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), message_id UUID REFERENCES messages(id) ON DELETE CASCADE, document_id UUID, chunk_id UUID, label TEXT NOT NULL, score DOUBLE PRECISION NOT NULL);

CREATE TABLE ai_providers (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, provider_type TEXT NOT NULL, base_url TEXT, status TEXT NOT NULL DEFAULT 'draft', created_by UUID REFERENCES users(id));
CREATE TABLE ai_provider_credentials (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), provider_id UUID REFERENCES ai_providers(id) ON DELETE CASCADE, auth_type TEXT NOT NULL, encrypted_secret TEXT NOT NULL, expires_at TIMESTAMPTZ);
CREATE TABLE ai_models (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), provider_id UUID REFERENCES ai_providers(id) ON DELETE CASCADE, model_id TEXT NOT NULL, model_type TEXT NOT NULL, capabilities JSONB NOT NULL DEFAULT '[]'::jsonb, enabled BOOLEAN NOT NULL DEFAULT false, is_default BOOLEAN NOT NULL DEFAULT false, pricing JSONB NOT NULL DEFAULT '{}'::jsonb, latency_ms_avg INT);
CREATE TABLE ai_model_tests (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), model_id UUID REFERENCES ai_models(id) ON DELETE CASCADE, prompt TEXT NOT NULL, output TEXT, latency_ms INT, estimated_cost NUMERIC, status TEXT NOT NULL, created_by UUID REFERENCES users(id), created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE llm_usage_logs (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id) ON DELETE SET NULL, model_id UUID REFERENCES ai_models(id) ON DELETE SET NULL, conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL, tokens_in INT NOT NULL DEFAULT 0, tokens_out INT NOT NULL DEFAULT 0, estimated_cost NUMERIC NOT NULL DEFAULT 0, latency_ms INT, created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE rag_collections (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, vertical TEXT NOT NULL, language TEXT, enabled BOOLEAN NOT NULL DEFAULT true, metadata JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE documents (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), collection_id UUID REFERENCES rag_collections(id) ON DELETE SET NULL, title TEXT NOT NULL, language TEXT NOT NULL, source_uri TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'uploaded', uploaded_by UUID REFERENCES users(id), created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE document_versions (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), document_id UUID REFERENCES documents(id) ON DELETE CASCADE, version INT NOT NULL, storage_key TEXT NOT NULL, checksum TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE document_chunks (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), document_id UUID REFERENCES documents(id) ON DELETE CASCADE, version_id UUID REFERENCES document_versions(id) ON DELETE CASCADE, chunk_index INT NOT NULL, content TEXT NOT NULL, metadata JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE document_embeddings (chunk_id UUID PRIMARY KEY REFERENCES document_chunks(id) ON DELETE CASCADE, embedding vector(1536), model_id UUID REFERENCES ai_models(id) ON DELETE SET NULL, created_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX document_embeddings_vector_idx ON document_embeddings USING ivfflat (embedding vector_cosine_ops);
CREATE TABLE vectorization_jobs (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), document_id UUID REFERENCES documents(id) ON DELETE CASCADE, status TEXT NOT NULL, progress INT NOT NULL DEFAULT 0, error TEXT, created_at TIMESTAMPTZ DEFAULT now(), finished_at TIMESTAMPTZ);

CREATE TABLE mcp_servers (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, transport_type TEXT NOT NULL, endpoint_url TEXT, command TEXT, status TEXT NOT NULL DEFAULT 'draft', last_sync_at TIMESTAMPTZ, created_by UUID REFERENCES users(id));
CREATE TABLE mcp_credentials (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), server_id UUID REFERENCES mcp_servers(id) ON DELETE CASCADE, auth_type TEXT NOT NULL, encrypted_secret TEXT, encrypted_refresh_token TEXT, expires_at TIMESTAMPTZ);
CREATE TABLE mcp_tools (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), server_id UUID REFERENCES mcp_servers(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT, input_schema JSONB NOT NULL DEFAULT '{}'::jsonb, output_schema JSONB NOT NULL DEFAULT '{}'::jsonb, enabled BOOLEAN NOT NULL DEFAULT false, requires_approval BOOLEAN NOT NULL DEFAULT true, risk_level TEXT NOT NULL DEFAULT 'medium');
CREATE TABLE mcp_resources (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), server_id UUID REFERENCES mcp_servers(id) ON DELETE CASCADE, uri TEXT NOT NULL, name TEXT, mime_type TEXT, description TEXT);
CREATE TABLE mcp_prompts (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), server_id UUID REFERENCES mcp_servers(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT, arguments_schema JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE agents (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, description TEXT, enabled BOOLEAN NOT NULL DEFAULT false, config JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE mcp_agent_bindings (agent_id UUID REFERENCES agents(id) ON DELETE CASCADE, tool_id UUID REFERENCES mcp_tools(id) ON DELETE CASCADE, enabled BOOLEAN NOT NULL DEFAULT true, PRIMARY KEY(agent_id, tool_id));
CREATE TABLE agent_runs (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), agent_id UUID REFERENCES agents(id) ON DELETE SET NULL, user_id UUID REFERENCES users(id) ON DELETE SET NULL, input TEXT NOT NULL, status TEXT NOT NULL, output TEXT, created_at TIMESTAMPTZ DEFAULT now(), finished_at TIMESTAMPTZ);
CREATE TABLE mcp_tool_invocations (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tool_id UUID REFERENCES mcp_tools(id) ON DELETE SET NULL, agent_run_id UUID REFERENCES agent_runs(id) ON DELETE CASCADE, arguments_json JSONB NOT NULL DEFAULT '{}'::jsonb, result_json JSONB, status TEXT NOT NULL, latency_ms INT, error TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE mcp_approvals (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), invocation_id UUID REFERENCES mcp_tool_invocations(id) ON DELETE CASCADE, requested_by UUID REFERENCES users(id), approved_by UUID REFERENCES users(id), status TEXT NOT NULL, reason TEXT, created_at TIMESTAMPTZ DEFAULT now());
```

### 10.4 AI stack — motor específico

#### LLM Gateway
- `llm_gateway/litellm_client.py`: cliente async para chat, embeddings, model test y streaming. Usado por chat, Admin AI y RAG embeddings.
- Smoke: llamada a modelo sandbox oficial/reales/proporcionados con prompt corto y log de latencia.

#### RAG
- `rag/ingestion.py`: extrae texto PDF/DOCX, calcula checksum y crea `document_versions`.
- `rag/chunking.py`: splitter LangChain con chunk size configurable por vertical.
- `rag/embeddings.py`: embeddings vía modelo default de embeddings en LiteLLM.
- `rag/retriever.py`: búsqueda cosine pgvector filtrada por idioma, colección, marca y país.
- Prompts: `backend/app/prompts/system/chat_people_assistant.md` con versión y fecha.

#### Deep Agents
- `agents/deepagents_runtime.py`: crea agentes People usando tools aprobadas.
- Tools: `agents/tools/rag_tool.py`, `agents/tools/mcp_tool.py`, `agents/tools/admin_tool.py`.

#### LangGraph
- `graphs/workflows.py`: workflows opcionales para approvals MCP y runs largas.
- `graphs/checkpointer.py`: checkpointer Postgres.

#### MCP
- `mcp/client.py`: JSON-RPC client para Streamable HTTP y stdio controlado.
- `mcp/policies.py`: evalúa allowlist, approvals, risk_level y rate limits.
- `mcp/tools.py`: discovery `tools/list` y llamada `tools/call` auditada.

### 10.5 Backend logging

Logs BEFORE/AFTER/ERROR por use case con redacción de `password`, `token`, `secret`, `api_key`, `encrypted_secret`, `prompt` completo y `document.content`.

## 11. Deploy

Docker Compose local con servicios `frontend`, `backend`, `postgres`, `redis`, `worker`, `litellm`, `minio`. Backend multi-stage Python. Frontend build estático servible por Nginx. CI ejecuta lint/test/build y migraciones sobre Postgres efímero.

### 11.1 Variables de entorno adicionales

| Variable | Dev | Staging | Prod | Descripción |
|---|---|---|---|---|
| `DATABASE_URL` | local | secret | secret | PostgreSQL async |
| `REDIS_URL` | local | secret | secret | Celery broker |
| `JWT_PRIVATE_KEY` | dev key | secret | secret | firma JWT |
| `JWT_PUBLIC_KEY` | dev key | secret | secret | verify JWT |
| `ENCRYPTION_KEY` | dev key | secret | secret | cifrado credenciales |
| `LITELLM_BASE_URL` | http://litellm:4000 | staging | prod | gateway modelos |
| `LITELLM_MASTER_KEY` | dev key | secret | secret | bearer que el backend envía al proxy LiteLLM; debe coincidir con `credential_plain` del fixture activo en `data/verification/admin_ai/credentials/*.json` |
| `S3_BUCKET_DOCUMENTS` | hilo-docs-dev | staging | prod | originales RAG |
| `DEFAULT_LANGUAGE` | es | es | es | fallback i18n |
| `MAX_UPLOAD_MB` | 25 | 25 | 25 | límite documentos |
| `MCP_ALLOWLIST_DOMAINS` | localhost | staging domains | approved domains | seguridad MCP |

### 11.2 Build targets

Frontend: `npm --prefix frontend run build`. Backend: `docker build -f backend/Dockerfile .`. Worker comparte imagen backend con comando Celery.

### 11.3 Rollback strategy

Migraciones reversibles. Activación de modelo y MCP son toggles auditados, rollback por `enabled=false` o restaurar default anterior. Documentos RAG no se borran físicamente en rollback, se desactivan por versión/colección.


### 11.4 Cross-origin / reverse-proxy topology

En dev y prod el navegador habla a UN solo origin (mismo host, mismo puerto):

- **Dev**: `vite` (puerto 5173) sirve el SPA y proxy-pasa `/api/**` a `uvicorn` (:8000). Configurado en `frontend/vite.config.ts` → `server.proxy["/api"]` (ADR-002, P01-S03-T002).
- **Prod**: `nginx` (puerto 80/443) sirve el SPA estático compilado y proxy-pasa `/api/**` al contenedor `backend`.

No se usa `CORSMiddleware` en el backend porque el navegador nunca emite una request cross-origin contra el API. Razonamiento completo y alternativas descartadas en ADR-002.

`frontend/.env.example` pin: `VITE_API_BASE_URL=""` — el cliente usa paths relativos para que el contrato de URL sea idéntico en dev y prod. **No** establecer `VITE_API_BASE_URL=http://localhost:8000` en dev: re-introduce cross-origin XHR y obliga a registrar `CORSMiddleware` (preflight independiente del atributo `SameSite=Lax` de la cookie de refresh — ver ADR-002 §Contexto).

## 12. Constraints & Invariants

- RAG no depende de Agents ni Graphs.
- Agents puede usar RAG y MCP solo mediante tools aprobadas.
- llm_gateway no conoce RAG, MCP ni Agents.
- Todo documento tiene idioma; todo chat tiene idioma.
- Credenciales de proveedores/MCP cifradas y nunca devueltas al frontend.
- Refresh tokens se guardan hasheados y rotan.
- Tools MCP externas se crean desactivadas y requieren aprobación para escritura.
- `preferred_language` solo puede ser `es`, `en`, `fr`.
- Un usuario employee no accede a `/admin/*` ni endpoints admin.
- Every streaming message is persisted after completion or marked failed with audit trail.

## 12.1 Slice Traceability Contract

Cada endpoint de §6.2 mapea a un `Slice ID` en Coverage Registry. Cada ruta de §6.1 mapea a un slice frontend o journey. Cada tabla de §10.3 nace en una migración de Phase 1/2. Cada pieza AI de §10.4 tiene smoke test. Los IDs canónicos se encuentran en `HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`.

## 13. Milestones técnicos

| Milestone | Features | Pantallas frontend | Rutas nuevas | Endpoints nuevos | Tablas nuevas | AI nuevo |
|---|---|---|---|---|---|---|
| M1 Auth propio + llegada al chat | Login, 2FA, profile | SignInPage, TwoFactorPage, ChatHomePage | /auth/sign-in, /auth/2fa, /chat | POST /api/v1/auth/sign-in, POST /api/v1/auth/2fa/verify, GET /api/v1/users/me | users, employee_profiles, refresh_tokens, mfa_totp_secrets, audit_logs | — |
| M2 Chat de People con RAG e i18n | Chat, History, Account | ChatHomePage, ConversationPage, HistoryPage, AccountPage | /chat, /chat/:conversationId, /history, /account | POST /api/v1/chat/conversations, POST /api/v1/chat/conversations/{id}/stream, PATCH /api/v1/users/me/language | conversations, messages, message_citations, document_chunks, llm_usage_logs | RAG retriever + LiteLLM stream |
| M3 Admin AI modelos y proveedores | Modelos, wizard, drawer test | AdminAiModelsPage, ModelWizardPage, ModelTestDrawer | /admin/ai/models, /admin/ai/models/new, /admin/ai/models/:modelId/test | GET/POST providers, GET/PATCH models, POST model test | ai_providers, ai_provider_credentials, ai_models, ai_model_tests | LiteLLM client smoke |
| M4 Admin RAG documentos y colecciones | Upload docs, index, collections | RagDocumentsPage, RagCollectionsPage | /admin/rag/documents, /admin/rag/collections | POST/GET documents, POST index, GET/PATCH collections | rag_collections, documents, document_versions, document_chunks, document_embeddings, vectorization_jobs | ingestion + embeddings |
| M5 MCP y Agents gobernados | MCP registry, tools, agents | McpServersPage, McpWizardPage, AgentsPage | /admin/ai/mcp, /admin/ai/mcp/new, /admin/ai/agents | GET/POST MCP, sync, patch tools, agents endpoints | mcp_servers, mcp_tools, agents, agent_runs | DeepAgents + LangGraph smoke |

## 14. Visualización

La visualización estática se genera en `dist/hilo-people-preview.html` como preview/reference, no como contrato canónico. Capturas esperadas: login mobile, chat mobile, history/account mobile, admin models desktop, admin RAG desktop, admin MCP/agents desktop. La evidencia temporal de cada slice vive en `orchestrator-state/tasks/evidence/<TASK_ID>/`; la gate `P05-S02-T003` consolida capturas aprobadas en `docs/visualization/hilo-people/`.

## 15. Architectural Decision Records

### ADR-001 — Refresh cookie Path attribute

**Fecha**: 2026-05-12

**Contexto**: La cookie de refresh token se estaba emitiendo con `Path=/auth`. Los endpoints reales de auth viven en `/api/v1/auth/*`. Por RFC 6265 §5.4, un navegador real NO envía la cookie a un path si el path del request no comienza por el atributo Path de la cookie. Esto hacía que refresh y logout fallaran en un navegador real aunque los tests con TestClient (que ignora Path) pasaran.

**Decisión**: Fijar `Path=/api/v1/auth` en `_REFRESH_COOKIE_PATH` (constante única en `_helpers.py`) usada por `_set_refresh_cookie` y `_clear_refresh_cookie`. Añadir test de cookie-jar real con `httpx.AsyncClient+ASGITransport` que valida el roundtrip sin inyectar manualmente la Cookie header.

**Alternativas descartadas**:
- `Path=/` — expone la cookie a toda la API; viola principio de menor exposición; rechazado.
- `Path=/api/v1` — innecesariamente amplio; no hay razón para enviar el refresh token a users/chat/etc.; rechazado.
- `Path=/auth` (status quo) — bug activo; el path no coincide con los endpoints reales; rechazado.

**Consecuencias**: La cookie solo viaja a `/api/v1/auth/*`. Cambios futuros al routing prefix requieren actualizar `_REFRESH_COOKIE_PATH` y la sección §10.2. Tests T01/T13 de sign-in, T01 de refresh y el nuevo T15 de logout actúan como muro de contención.


### ADR-002 — Cross-origin strategy: same-origin reverse proxy in dev (vite) and prod (Nginx)

**Fecha**: 2026-05-13

**Contexto**: El frontend dev sirve en :5173 (vite) y el backend dev en :8000 (uvicorn). `localhost:5173` y `localhost:8000` son **same-site** — la determinación de same-site usa scheme + eTLD+1 y **el puerto se ignora** (MDN Glossary/Site; web.dev "same-site-same-origin"; RFC 6265bis §5.2). Por tanto `SameSite=Lax` permite la cookie de refresh entre ambos puertos: SameSite gobierna same-site vs cross-site, no same-origin vs cross-origin, y nunca fue el bloqueo. El bloqueo real observado en `/verify-slice P01-S03-T001` F3–F5 fue el **preflight CORS** (mecanismo independiente de SameSite): `OPTIONS /api/v1/auth/refresh → 405 Method Not Allowed` porque no había `CORSMiddleware` registrado y FastAPI/Starlette no genera un handler implícito de OPTIONS. Strategy A colapsa el navegador a un único origin (`:5173` vía vite proxy) y elimina el preflight; la cookie sigue viajando porque el request sigue siendo same-site (lo era ya) y ahora además same-origin.

**Decisión**: Adoptar reverse proxy same-origin en dev y prod:
- Dev: `vite.config.ts` declara `server.proxy["/api"] = { target: "http://localhost:8000", changeOrigin: false }`. El navegador habla a :5173 para TODO (HTML, assets, /api/**) y vite reenvía /api → :8000.
- Prod: Nginx delante del SPA estático también proxy-pasa `/api/**` al servicio backend. El navegador habla a UN solo origin (el de la app) en ambos entornos.

`VITE_API_BASE_URL=""` en `frontend/.env.example` es el pin de contrato: el cliente usa paths relativos.

**Alternativas descartadas**:
- `CORSMiddleware` con `allow_origins=["http://localhost:5173"]; allow_credentials=true` — funciona pero deja prod y dev en topologías distintas (en prod hay Nginx delante; en dev hay CORS), introduce middleware adicional permanente solo por dev, requiere allowlist de orígenes mantenida a mano. Rechazado por divergencia dev/prod.
- `CORSMiddleware` con `allow_origins=["*"]` — incompatible con `allow_credentials=true` por spec CORS; además inseguro. Rechazado.
- `VITE_API_BASE_URL=http://localhost:8000` (status quo implícito) — re-introduce cross-origin XHR y require CORS. Rechazado.

**Consecuencias**:
- El frontend code path es idéntico en dev y prod; cero ramas `if (DEV)` alrededor de URLs.
- La cookie refresh no necesita razonar sobre cross-origin: `SameSite=Lax` simplemente funciona.
- El backend no necesita conocer la lista de orígenes UI; un servicio detrás de Nginx no necesita CORS.
- SSE / streaming (P02-S04 `POST /api/v1/chat/conversations/{id}/stream`) debe verificarse explícitamente a través del proxy cuando aterrice; vite preserva chunked transfer por defecto.
- Si en el futuro Hilo gana un consumer externo (app móvil nativa, integración B2B), se reabrirá esta decisión con un ADR que SUPERSEDE a ADR-002.

## 16. Verificación de cableado pre-entrega

Revisión técnica ejecutada dos veces: todos los endpoints de §6.2 tienen slice, todas las rutas de §6.1 tienen slice, todas las tablas de §10.3 aparecen en el schema y en Coverage Registry, todos los journeys J100-J105 cruzan pantallas/endpoints/tablas/slices existentes y no quedan placeholders.
