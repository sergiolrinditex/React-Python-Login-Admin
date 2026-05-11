# Hilo People — Instrucciones (large app sin baseline)

Perfil: **large-without-base**. Producto nuevo desde cero para el departamento de People de Inditex. No se heredan rutas, tablas, endpoints, journeys ni decisiones de existing baseline.

## 1. Identidad del Proyecto

### 1.1 Nombre

`hilo-people`

Nombre público: **Hilo**. Hilo remite al hilo textil, al hilo conversacional y a la conexión entre la persona empleada y People. El tono del asistente es cercano, profesional y breve.

### 1.2 Descripción

Hilo es un asistente conversacional de IA para empleados de Inditex y sus marcas, incluyendo Zara, Pull&Bear, Massimo Dutti, Bershka, Stradivarius, Oysho, Zara Home y Lefties. Resuelve dudas de People/RRHH sobre políticas internas, nóminas, vacaciones, formación, movilidad interna, beneficios y procedimientos operativos de tienda, oficina y logística. El producto combina chat, RAG sobre documentación interna, configuración de modelos mediante LiteLLM, conexión con MCP externos y agentes gobernados por el equipo de IT/People Tech.

### 1.3 Tipo de proyecto

Aplicación web interna de producción. Frontend React + Vite + TypeScript, React Router, TanStack Query, React Hook Form, Zod e i18next. Backend Python FastAPI con JWT propio, PostgreSQL + pgvector, Redis/Celery, LiteLLM como gateway de modelos, LangChain/RAG, DeepAgents, LangGraph y MCP. La app tiene superficies móviles para empleado y escritorio para Admin AI.

## 2. Objetivo

### 2.1 Objetivo de negocio

Los equipos de People reciben preguntas repetidas sobre vacaciones, nómina, beneficios, procesos internos, movilidad y formación desde múltiples canales. Hilo reduce el tiempo de respuesta, aumenta la consistencia de las respuestas y permite citar documentación oficial cuando la respuesta usa RAG. El equipo de IT/People Tech gobierna qué modelos, colecciones RAG, MCP externos y agentes están activos. Métrica de éxito: al menos 60% de preguntas frecuentes resueltas en autoservicio, con trazabilidad de fuente y sin intervención humana.

### 2.2 Usuario objetivo

- **Empleado Inditex**: usa móvil o navegador para preguntar dudas de People a diario u on-demand. Puede consultar historial, cambiar idioma y cerrar sesión.
- **People Tech Admin**: usa desktop para configurar proveedores LiteLLM, modelos, colecciones RAG, servidores MCP, agentes, uso, costes y auditoría.
- **Auditor/Soporte People**: accede a logs, citas y trazabilidad sin poder cambiar credenciales ni activar herramientas de riesgo.
- Tenant model: un único tenant corporativo inicial con datos segmentables por marca, país, sociedad, centro y rol.

### 2.3 Definition of Done global

- [ ] Un empleado puede registrarse o entrar con email corporativo, contraseña y 2FA, y aterrizar en `/chat` con sesión JWT real.
- [ ] El chat responde por streaming SSE/fetch usando el modelo activo en LiteLLM y persiste conversación, mensajes, citas, coste y latencia.
- [ ] Una pregunta de política interna recupera documentos RAG y muestra citas inline con metadatos de documento, colección e idioma.
- [ ] Un admin puede crear proveedor LiteLLM, guardar credenciales cifradas, listar modelos, activar un modelo y probarlo en drawer.
- [ ] Un admin puede subir un documento de People, lanzar vectorización Celery y ver su colección disponible para chat.
- [ ] Un admin puede registrar un servidor MCP externo, hacer discovery de tools, aprobar tools y asignarlas a agentes.
- [ ] La interfaz está disponible en español, inglés y francés con fallback a español.
- [ ] Los logs no imprimen secretos, tokens ni contenido sensible completo.
- [ ] Todos los journeys J100-J105 pasan con datos reales/proporcionados y evidencia visual.

## 3. Alcance

### 3.1 EL MOTOR — Phase 2

#### Componente del motor: Auth y perfiles de empleado

- **Qué hace**: controla registro, login, refresh tokens, logout, reset password, 2FA TOTP, roles, permisos y perfil de empleado. Emite JWT propio de Hilo y mantiene refresh tokens en cookie HttpOnly.
- **Entities de dominio**: `User`, `EmployeeProfile`, `Role`, `Permission`, `RefreshToken`, `MfaSecret`, `PasswordResetToken`, `AuditLog`.
- **Use cases principales**: `SignUpUser`, `SignInUser`, `RotateRefreshToken`, `VerifyTwoFactorCode`, `RequestPasswordReset`, `ResetPassword`, `GetCurrentUser`, `UpdatePreferredLanguage`.
- **Componente AI**: no aplica.
- **Tablas DB nuevas**: `users`, `employee_profiles`, `roles`, `permissions`, `user_roles`, `refresh_tokens`, `mfa_totp_secrets`, `password_reset_tokens`, `audit_logs`.
- **Endpoints nuevos**: `POST /api/v1/auth/sign-up`, `POST /api/v1/auth/sign-in`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password`, `POST /api/v1/auth/2fa/verify`, `GET /api/v1/users/me`, `PATCH /api/v1/users/me/language`.
- **Reglas de negocio**: solo emails corporativos permitidos; refresh tokens se guardan hasheados y rotan; 2FA obligatorio para administradores; el idioma solo puede ser `es`, `en` o `fr`; todo login/logout/reset queda auditado.

#### Componente del motor: Chat conversacional con RAG

- **Qué hace**: gestiona conversaciones, mensajes, streaming SSE/fetch y citas a documentos internos. El chat es el home del empleado tras login.
- **Entities de dominio**: `Conversation`, `Message`, `MessageCitation`, `LlmUsageLog`, `RagCollection`, `Document`, `DocumentChunk`.
- **Use cases principales**: `CreateConversation`, `ListConversations`, `GetConversation`, `StreamMessage`, `PersistAssistantMessage`, `AttachCitations`, `LogTokenUsage`.
- **Componente AI**: chat simple con retrieval RAG y llamada a LiteLLM; no requiere DeepAgents en V1 para preguntas normales.
- **RAG config**: recuperar chunks por idioma, marca, país y colección activa; fallback a español si no hay documentos del idioma del usuario.
- **Tablas DB nuevas**: `conversations`, `messages`, `message_citations`, `llm_usage_logs`, `rag_collections`, `documents`, `document_chunks`, `document_embeddings`.
- **Endpoints nuevos**: `GET /api/v1/chat/conversations`, `POST /api/v1/chat/conversations`, `GET /api/v1/chat/conversations/{id}`, `POST /api/v1/chat/conversations/{id}/stream`.
- **Reglas de negocio**: un empleado solo ve sus conversaciones; la respuesta debe usar el idioma preferido; si usa RAG debe citar fuente; los tokens y coste se registran; no se exponen prompts internos.

#### Componente del motor: Admin AI y LiteLLM Gateway

- **Qué hace**: permite al equipo People Tech configurar proveedores, credenciales, modelos de chat, modelos de embeddings, defaults, pruebas y métricas. LiteLLM vive como gateway separado y el backend lo gobierna.
- **Entities de dominio**: `AiProvider`, `AiProviderCredential`, `AiModel`, `AiModelTest`, `LlmUsageLog`.
- **Use cases principales**: `CreateProvider`, `TestProviderConnection`, `ListAvailableModels`, `ActivateModel`, `TestModelPrompt`, `GetUsageSummary`.
- **Componente AI**: `llm_gateway/litellm_client.py` para llamadas de prueba y streaming.
- **Tablas DB nuevas**: `ai_providers`, `ai_provider_credentials`, `ai_models`, `ai_model_tests`, `llm_usage_logs`.
- **Endpoints nuevos**: `GET /api/v1/admin/ai/providers`, `POST /api/v1/admin/ai/providers`, `GET /api/v1/admin/ai/models`, `PATCH /api/v1/admin/ai/models/{id}`, `POST /api/v1/admin/ai/models/{id}/test`, `GET /api/v1/admin/usage`.
- **Reglas de negocio**: credenciales cifradas; solo admins pueden activar modelos; debe existir un modelo chat default y un modelo embeddings default; ninguna API key se devuelve al frontend.

#### Componente del motor: RAG Admin y vectorización

- **Qué hace**: ingesta documentos de People, extrae texto, chunking, embeddings, almacenamiento pgvector, colecciones por vertical y estado de vectorización. Los documentos alimentan respuestas del chat.
- **Entities de dominio**: `RagCollection`, `Document`, `DocumentVersion`, `DocumentChunk`, `DocumentEmbedding`, `VectorizationJob`.
- **Use cases principales**: `UploadDocument`, `ListDocuments`, `IndexDocument`, `ListCollections`, `UpdateCollection`, `RetrieveContext`.
- **Componente AI**: LangChain splitters/loaders, embeddings vía LiteLLM o proveedor configurado, retriever pgvector.
- **Tablas DB nuevas**: `rag_collections`, `documents`, `document_versions`, `document_chunks`, `document_embeddings`, `vectorization_jobs`.
- **Endpoints nuevos**: `POST /api/v1/admin/rag/documents`, `GET /api/v1/admin/rag/documents`, `POST /api/v1/admin/rag/documents/{id}/index`, `GET /api/v1/admin/rag/collections`, `PATCH /api/v1/admin/rag/collections/{id}`.
- **Reglas de negocio**: solo admins suben documentos; cada documento tiene idioma y vertical; no se indexan documentos sin colección; embeddings se recalculan por versión; vectorización se ejecuta en Celery.

#### Componente del motor: MCP y Agents

- **Qué hace**: registra servidores MCP externos, descubre tools/resources/prompts, aplica políticas, asigna tools a agentes y ejecuta runs auditadas con DeepAgents. MCP no vive dentro de LiteLLM ni RAG; es una capa propia de herramientas externas.
- **Entities de dominio**: `McpServer`, `McpCredential`, `McpTool`, `McpResource`, `McpPrompt`, `McpAgentBinding`, `Agent`, `AgentRun`, `McpToolInvocation`, `McpApproval`.
- **Use cases principales**: `RegisterMcpServer`, `SyncMcpTools`, `ApproveMcpTool`, `BindToolToAgent`, `StartAgentRun`, `AuditMcpInvocation`.
- **Componente AI**: DeepAgents runtime usa `rag_tool`, `mcp_tool` y `admin_tool`; LangGraph queda disponible para workflows con estado y aprobaciones humanas.
- **Tablas DB nuevas**: `mcp_servers`, `mcp_credentials`, `mcp_tools`, `mcp_resources`, `mcp_prompts`, `mcp_agent_bindings`, `agents`, `agent_runs`, `mcp_tool_invocations`, `mcp_approvals`.
- **Endpoints nuevos**: `GET /api/v1/admin/ai/mcp/servers`, `POST /api/v1/admin/ai/mcp/servers`, `POST /api/v1/admin/ai/mcp/servers/{id}/sync`, `PATCH /api/v1/admin/ai/mcp/tools/{id}`, `GET /api/v1/admin/ai/agents`, `PATCH /api/v1/admin/ai/agents/{id}/tools`, `POST /api/v1/agents/runs`.
- **Reglas de negocio**: tools MCP externas entran desactivadas; tools de escritura requieren aprobación humana; stdio no se habilita para servidores externos en producción; toda invocación queda auditada.

### 3.2 LAS FEATURES — Phase 3 y Phase 4

#### Feature: Login propio y recuperación de acceso

- **Pantallas**: `SignInPage`, `SignUpPage`, `ForgotPasswordPage`, `ResetSentPage`, `TwoFactorPage`.
- **Endpoints consumidos**: auth sign-up, sign-in, forgot, reset, 2FA, refresh.
- **Validaciones**: email corporativo, contraseña mínima, 6 dígitos 2FA, aceptación legal en sign-up.
- **Estados UI**: loading, empty no aplica por formulario, error_network, error_validation, permission_denied, success.
- **Next action**: sign-in con MFA navega a `/auth/2fa`; éxito final navega a `/chat`.

#### Feature: Chat home del empleado

- **Pantallas**: `ChatHomePage`, `ConversationPage`, `HistoryPage`, `AccountPage`.
- **Endpoints consumidos**: chat conversations, stream, users/me, users/me/language.
- **Validaciones**: pregunta no vacía, longitud máxima, idioma soportado.
- **Estados UI**: loading, empty, streaming, error_network, error_validation, permission_denied, success.
- **Next action**: abrir historial, continuar conversación o cambiar idioma.

#### Feature: Admin AI modelos y proveedores

- **Pantallas**: `AdminDashboardPage`, `AdminAiModelsPage`, `ModelWizardPage`, `ModelTestDrawer`.
- **Endpoints consumidos**: providers, models, model test, usage.
- **Validaciones**: proveedor válido, credenciales presentes, modelo seleccionado, permisos admin.
- **Estados UI**: loading, empty, error_network, error_validation, permission_denied, success.
- **Next action**: activar modelo, probar prompt o volver a tabla.

#### Feature: Admin RAG documentos y colecciones

- **Pantallas**: `RagDocumentsPage`, `RagCollectionsPage`.
- **Endpoints consumidos**: document upload/list/index, collections list/update.
- **Validaciones**: PDF/DOCX permitido, idioma requerido, colección requerida.
- **Estados UI**: loading, empty, uploading, indexing, error_network, error_validation, permission_denied, success.
- **Next action**: lanzar indexación o asignar colección a vertical.

#### Feature: Admin MCP y agentes

- **Pantallas**: `McpServersPage`, `McpWizardPage`, `AgentsPage`.
- **Endpoints consumidos**: MCP servers, MCP sync, MCP tools patch, agents list, agents tool binding, agent run.
- **Validaciones**: endpoint MCP seguro, auth configurada, tools permitidas, agente existente.
- **Estados UI**: loading, empty, syncing, error_network, error_validation, permission_denied, success.
- **Next action**: sincronizar tools, aprobar tool, asignar a agente o ejecutar smoke.

#### Feature: Auditoría y uso

- **Pantallas**: `AuditLogPage`, `UsagePage`.
- **Endpoints consumidos**: audit log, usage summary.
- **Validaciones**: filtros de fecha válidos, permisos auditor/admin.
- **Estados UI**: loading, empty, error_network, permission_denied, success; error_validation solo para filtros inválidos.
- **Next action**: exportar o abrir detalle de evento.

### 3.3 Foundation propia

- **Auth/roles**: JWT propio con access token corto y refresh token HttpOnly; roles `employee`, `people_admin`, `people_auditor`, `super_admin`.
- **Perfil/cuenta**: datos de empleado, marca, centro, sociedad, país, departamento, idioma y sesiones.
- **i18n**: español, inglés y francés; fallback español; namespaces `common`, `auth`, `chat`, `account`, `admin-ai`, `rag`, `mcp`, `errors`.
- **Design system**: editorial Inditex/Zara post-2019: blanco/negro, fondo crudo `#f5f3ee`, tinta `#0a0a0a`, serif Bodoni-like para wordmark/titulares, Helvetica Neue/sistema para texto, hairlines 1px, etiquetas uppercase tracked, cero border-radius.
- **Logging + observabilidad**: request_id, audit log, logs estructurados, métricas de latencia, tokens y coste.
- **Infraestructura**: Docker Compose local, CORS restringido, security headers, Redis, Celery, pgvector, scripts dev.
- **AI stack**: LiteLLM gateway, LangChain RAG, DeepAgents, LangGraph, MCP registry.

### 3.4 Excluido

- Nómina transaccional o descarga de recibos reales en V1; Hilo responde dudas y enlaza procedimiento.
- SSO corporativo SAML/OIDC productivo en V1; se prepara arquitectura para incorporarlo después manteniendo JWT propio.
- Ejecución automática de herramientas MCP de escritura sin aprobación humana; queda prohibida por riesgo operativo.
- Push notifications nativas y modo offline completo; la superficie inicial es web.
- OCR avanzado de imágenes escaneadas; V1 soporta texto extraíble y documentos Office/PDF nativos.

### 3.5 Scope

Tipo: MVP de producción. V1 incluye login propio, chat con RAG, Admin AI, Admin RAG, MCP registry, agentes básicos, auditoría, uso e i18n ES/EN/FR. V2 podrá añadir SSO corporativo, conectores internos certificados, approvals complejos con LangGraph, OCR, analytics avanzados y country packs específicos.

### 3.5.1 Granularidad esperada de los slices

Un slice oficial es pequeño, verificable y cerrable: una migración coherente, un endpoint verificable, una pantalla con estados completos, una pieza AI con smoke test o un journey e2e. Se evitan slices tipo “Auth completa” o “Todo admin”.

### 3.6 Recorridos del usuario de la app

#### J100 — Acceso seguro del empleado

Permite validar la foundation de auth propia y aterrizar en el chat.

`empleado → /auth/sign-in → introduce credenciales → /auth/2fa → introduce código → /chat`.

Estado final: sesión JWT activa, refresh token HttpOnly y perfil empleado cargado.

#### J101 — Pregunta de People con respuesta RAG

Es el valor principal para el empleado: preguntar y recibir respuesta citada.

`empleado → /chat → elige sugerencia o escribe pregunta → /chat/:conversationId → recibe streaming + citas`.

Estado final: conversación, mensajes, uso LLM y citas persistidas.

#### J102 — Retomar conversación y cambiar idioma

Permite demostrar historial, cuenta e i18n.

`empleado → /history → abre conversación previa → /chat/:conversationId → /account → cambia idioma`.

Estado final: idioma preferido persistido y UI traducida.

#### J103 — Gobierno de modelos por Admin AI

Permite activar el modelo que usará el chat.

`admin → /admin/ai/models → /admin/ai/models/new → configura proveedor → /admin/ai/models/:modelId/test → prueba prompt → /admin/ai/models`.

Estado final: proveedor, credenciales cifradas, modelo activo y test auditado.

#### J104 — Ingesta de base de conocimiento RAG

Permite subir documentación de People y hacerla disponible al chat.

`admin → /admin/rag/documents → sube documento → indexa → /admin/rag/collections → valida colección activa`.

Estado final: documento versionado, chunks, embeddings y job finalizado.

#### J105 — Conectar MCP externo y habilitar agente

Permite extender agentes con herramientas externas gobernadas.

`admin → /admin/ai/mcp → /admin/ai/mcp/new → registra servidor → /admin/ai/mcp → sincroniza tools → /admin/ai/agents → asigna tool`.

Estado final: servidor MCP, tools descubiertas, política y binding de agente persistidos.

### 3.7 Journey Coverage Matrix

| ID | Milestone | Pantallas (en orden) | Acciones clave | Endpoints | Tablas DB | Estado cliente/provider | Slices | Verificación |
|---|---|---|---|---|---|---|---|---|
| J100 | M1 | SignInPage /auth/sign-in → TwoFactorPage /auth/2fa → ChatHomePage /chat | submit credentials, verify MFA, land chat | POST /api/v1/auth/sign-in, POST /api/v1/auth/2fa/verify, GET /api/v1/users/me | users, employee_profiles, refresh_tokens, mfa_totp_secrets, audit_logs | authStore, currentUserQuery, i18nStore | P01-S02, P03-S01-T001, P03-S01-T005, P05-S01-T001 | /verify-journey J100 |
| J101 | M2 | ChatHomePage /chat → ConversationPage /chat/:conversationId | ask question, stream response, inspect citation | POST /api/v1/chat/conversations, POST /api/v1/chat/conversations/{id}/stream, GET /api/v1/chat/conversations/{id} | conversations, messages, message_citations, llm_usage_logs, document_chunks | chatQuery, streamController, citationStore | P02-S03, P02-S04, P03-S02-T001, P03-S02-T002, P05-S01-T002 | /verify-journey J101 |
| J102 | M2 | HistoryPage /history → ConversationPage /chat/:conversationId → AccountPage /account | open history, resume chat, change language | GET /api/v1/chat/conversations, GET /api/v1/chat/conversations/{id}, PATCH /api/v1/users/me/language | users, conversations, messages | historyQuery, currentUserQuery, i18nStore | P01-S02-T007, P02-S03-T001, P03-S02-T002..T004, P05-S01-T003 | /verify-journey J102 |
| J103 | M3 | AdminAiModelsPage /admin/ai/models → ModelWizardPage /admin/ai/models/new → ModelTestDrawer /admin/ai/models/:modelId/test | create provider, select models, test prompt, activate | GET /api/v1/admin/ai/providers, POST /api/v1/admin/ai/providers, GET /api/v1/admin/ai/models, PATCH /api/v1/admin/ai/models/{id}, POST /api/v1/admin/ai/models/{id}/test | ai_providers, ai_provider_credentials, ai_models, ai_model_tests, llm_usage_logs, audit_logs | adminAiQuery, modelWizardStore, testDrawerStore | P02-S05, P04-S01-T002..T004, P05-S01-T004 | /verify-journey J103 |
| J104 | M4 | RagDocumentsPage /admin/rag/documents → RagCollectionsPage /admin/rag/collections | upload doc, index, check collection | POST /api/v1/admin/rag/documents, GET /api/v1/admin/rag/documents, POST /api/v1/admin/rag/documents/{id}/index, GET /api/v1/admin/rag/collections, PATCH /api/v1/admin/rag/collections/{id} | rag_collections, documents, document_versions, document_chunks, document_embeddings, vectorization_jobs | ragDocumentsQuery, uploadStore, vectorizationStatus | P02-S06, P04-S02-T001..T002, P05-S01-T005 | /verify-journey J104 |
| J105 | M5 | McpServersPage /admin/ai/mcp → McpWizardPage /admin/ai/mcp/new → AgentsPage /admin/ai/agents | register server, sync tools, approve tool, bind agent | GET /api/v1/admin/ai/mcp/servers, POST /api/v1/admin/ai/mcp/servers, POST /api/v1/admin/ai/mcp/servers/{id}/sync, PATCH /api/v1/admin/ai/mcp/tools/{id}, GET /api/v1/admin/ai/agents, PATCH /api/v1/admin/ai/agents/{id}/tools | mcp_servers, mcp_credentials, mcp_tools, mcp_agent_bindings, agents, agent_runs, audit_logs | mcpQuery, mcpWizardStore, agentsQuery | P02-S07, P02-S08, P04-S02-T003..T005, P05-S01-T006 | /verify-journey J105 |

## 4. Milestones

### Milestone M1: Auth propio + llegada al chat

**Objetivo**: acceso seguro de empleado con JWT, 2FA y perfil.  
**Motor requerido**: Auth y perfiles.  
**Features requeridas**: login, 2FA, cuenta base.  
**Backend**: endpoints auth y users.  
**Verification script**: abrir `http://localhost:5000`, entrar con `data/verification/users/employee_primary.json.email`, completar 2FA con un TOTP generado en tiempo real desde `data/verification/auth/mfa_primary.json`, verificar llegada a `/chat`.  
**Tras entrega**: un empleado real de prueba accede al chat.

### Milestone M2: Chat de People con RAG e i18n

**Objetivo**: el empleado pregunta por políticas y recibe respuesta citada en su idioma.  
**Motor requerido**: Chat conversacional, RAG retrieval, LiteLLM gateway.  
**Features requeridas**: chat home, conversación, historial, cuenta.  
**Backend**: chat endpoints, RAG retrieval, usage logging.  
**Verification script**: preguntar “¿Cuántos días de vacaciones me quedan?”, ver streaming, cita de política interna y conversación en historial.  
**Tras entrega**: autoservicio de People operativo.

### Milestone M3: Admin AI modelos y proveedores

**Objetivo**: People Tech gobierna proveedores y modelos.  
**Motor requerido**: Admin AI y LiteLLM Gateway.  
**Features requeridas**: modelos, wizard, test drawer, usage.  
**Backend**: endpoints providers/models/test/usage.  
**Verification script**: crear proveedor OpenAI sandbox, listar modelos, activar modelo de chat, probar prompt.  
**Tras entrega**: el modelo activo del chat se gobierna desde Admin AI.

### Milestone M4: Admin RAG documentos y colecciones

**Objetivo**: People Tech sube e indexa documentos internos.  
**Motor requerido**: RAG Admin y vectorización.  
**Features requeridas**: documentos y colecciones.  
**Backend**: endpoints RAG, Celery, pgvector.  
**Verification script**: subir documento `politica_vacaciones_es.pdf`, lanzar indexación, comprobar colección activa.  
**Tras entrega**: documentos internos alimentan respuestas con citas.

### Milestone M5: MCP y Agents gobernados

**Objetivo**: conectar tools externas MCP sin perder control ni auditoría.  
**Motor requerido**: MCP y Agents.  
**Features requeridas**: MCP servers, wizard, agents.  
**Backend**: endpoints MCP y agents.  
**Verification script**: registrar MCP sandbox, sincronizar tools, habilitar una tool read-only para un agente y lanzar run smoke.  
**Tras entrega**: agentes pueden usar herramientas externas aprobadas.

## 5. Modo de Trabajo

Trabajo por slices verificables, DAG explícito, source-of-truth primero, tests reales, datos reales/proporcionados, DRY/KISS/YAGNI y sin hardcoding de secrets. Cada slice debe cerrar con handoff, evidencia y verify según `Verify mode`.

## 6. i18n — keys específicas de la app

Idiomas soportados: `es`, `en`, `fr`. Fallback: `es`. Namespaces: `common`, `auth`, `chat`, `account`, `admin-ai`, `rag`, `mcp`, `errors`.

| Key | ES | EN | FR |
|---|---|---|---|
| `common.productName` | Hilo | Hilo | Hilo |
| `auth.signIn.title` | Entrar | Sign in | Connexion |
| `auth.signIn.email` | Email corporativo | Corporate email | Email professionnel |
| `auth.signIn.password` | Contraseña | Password | Mot de passe |
| `auth.forgot.title` | Recuperar acceso | Reset access | Réinitialiser l’accès |
| `auth.twoFactor.title` | Verificación en dos pasos | Two-step verification | Vérification en deux étapes |
| `chat.empty.title` | ¿En qué puedo ayudarte? | How can I help? | Comment puis-je vous aider ? |
| `chat.empty.promptVacation` | ¿Cuántos días de vacaciones me quedan? | How many vacation days do I have left? | Combien de jours de congé me reste-t-il ? |
| `chat.empty.promptMobility` | Política de movilidad interna | Internal mobility policy | Politique de mobilité interne |
| `chat.citation.label` | Fuente | Source | Source |
| `account.language` | Idioma | Language | Langue |
| `adminAi.models.title` | Modelos LiteLLM | LiteLLM models | Modèles LiteLLM |
| `adminAi.mcp.title` | Integraciones MCP | MCP integrations | Intégrations MCP |
| `rag.documents.title` | Documentos de People | People documents | Documents People |
| `errors.AUTH_INVALID_CREDENTIALS` | Email o contraseña incorrectos | Incorrect email or password | Email ou mot de passe incorrect |

## 7. Theme

Hilo usa código editorial Inditex/Zara: fondo crudo `#f5f3ee`, tinta `#0a0a0a`, blanco puro para láminas, hairlines `1px`, cero sombras decorativas, cero esquinas redondeadas, CTA sólidos negros, etiquetas uppercase con tracking alto, wordmark serif solapado y cuerpo Helvetica Neue/sistema. Componentes base: `Wordmark`, `EditorialInput`, `SolidCTA`, `TrackedLabel`, `StatusDot`, `HairlineTable`, `MobileShell`, `AdminShell`.

## 8. Prioridades de ejecución

1. Foundation, tokens, i18n y health. 2. Auth y usuarios. 3. DB y motor AI/RAG/MCP. 4. Front empleado. 5. Front admin. 6. Journeys e2e. 7. Hardening/release.

## 9. Git

Workflow: `pr-flow`. Cada slice cierra con commit atómico y PR. No push directo a main. Los scripts de cierre usan `./scripts/git-workflow.sh`.

## 10. Criterios de Aceptación

- [ ] `npm run test -- --run`, `npm run build`, `pytest backend/tests`, `alembic upgrade head`, `ruff check backend`, `mypy backend/app` verdes.
- [ ] Los cinco journeys J100-J105 verificados con datos reales/proporcionados.
- [ ] No hay texto hardcodeado fuera de i18n salvo nombres de marca y IDs técnicos.
- [ ] Ninguna API key o refresh token aparece en logs o respuesta API.
- [ ] Todos los endpoints devuelven envelope `{data, meta, errors}` o 204 documentado.
- [ ] Los estados visuales loading, empty, error_network, error_validation, permission_denied y success están implementados en pantallas productivas y cada handoff frontend incluye `VISUAL_CONTRACT_CHECK`.

## 11. Restricciones técnicas

### 11.0 Library Discovery Pass

| Área funcional | Decisión | Tipo de librería buscada (sin versión) | Slices estimados ahorrados |
|---|---|---|---|
| Forms y validación React | USAR | `react-hook-form` + `zod` + resolvers | 2 |
| Data fetching/cache React | USAR | `@tanstack/react-query` | 2 |
| Routing React | USAR | `react-router-dom` | 1 |
| i18n frontend | USAR | `i18next`, `react-i18next`, language detector | 2 |
| SSE/fetch streaming | CUSTOM | fetch reader propio con parser SSE pequeño | 1 |
| Procesamiento PDF backend | USAR | parser PDF mantenido compatible con Python | 1 |
| Procesamiento Office backend | USAR | extractor DOCX mantenido compatible con Python | 1 |
| Jobs/queues | USAR | Celery con Redis | 2 |
| Email custom | USAR | proveedor Resend y SMTP fallback | 1 |
| Observabilidad backend | USAR | structlog + prometheus client | 1 |
| Storage no-Supabase | USAR | S3/MinIO compatible | 1 |
| BBDD pgvector | USAR | extensión pgvector + soporte SQLAlchemy | 2 |
| BBDD pgcrypto | USAR | extensión pgcrypto para UUID/cifrado auxiliar | 1 |
| AI LiteLLM | USAR | LiteLLM proxy/client | 2 |
| AI LangChain RAG | USAR | LangChain splitters/retrievers | 2 |
| AI LangGraph workflows | USAR | LangGraph | 2 |
| AI DeepAgents | USAR | DeepAgents | 2 |
| MCP client | USAR | SDK/protocolo MCP mantenido | 2 |
| Token counting | USAR | tokenizer compatible con modelos OpenAI/Anthropic | 1 |
| Maps/pagos/push | NO APLICA | No hay geolocalización, pagos ni push en V1 | 0 |

### 11.1 Paquetes adicionales — resumen

- **Forms y validación React**: `react-hook-form`, `zod`, `@hookform/resolvers`.
- **Data fetching/cache React**: `@tanstack/react-query`.
- **Routing React**: `react-router-dom`.
- **i18n frontend**: `i18next`, `react-i18next`, `i18next-browser-languagedetector`.
- **PDF backend**: `pypdf`.
- **Office backend**: `python-docx`.
- **Jobs/queues**: `celery`, `redis`.
- **Email custom**: `resend`, SMTP stdlib fallback.
- **Observabilidad backend**: `structlog`, `prometheus-client`.
- **Storage compatible S3/MinIO**: `boto3`.
- **Postgres/pgvector**: `pgvector` y SQLAlchemy.
- **AI gateway y RAG/agents**: `litellm`, `langchain`, `langgraph`, `deepagents`.
- **MCP**: SDK MCP Python candidato a confirmar.
- **Token counting**: `tiktoken`.

### 11.2 Paquetes prohibidos

Prohibido usar auth externa como Clerk/Auth0/Supabase Auth para el core; tokens en localStorage; CORS `*` en producción; llaves en texto plano; librerías abandonadas; SDKs con licencias incompatibles sin ADR.

## 12. Plataforma

Web responsive. Mobile web 402×874 para login y chat de empleado. Desktop 1440×920 para Admin AI. Sin funcionalidad que varíe por plataforma nativa en V1.

## 13. Riesgos

- **Riesgo**: respuestas de IA incorrectas sobre políticas internas. **Mitigación**: RAG con citas, system prompt conservador, disclaimers internos y feedback de usuario.
- **Riesgo**: costes de LLM por streaming y pruebas admin. **Mitigación**: usage logs, límites por rol, latencia/coste en admin y modelos default controlados.
- **Riesgo**: exposición de credenciales LiteLLM/MCP. **Mitigación**: cifrado en DB, secrets manager, no retorno al frontend, auditoría.
- **Riesgo**: MCP externo malicioso o demasiado amplio. **Mitigación**: allowlist, tools desactivadas por defecto, approvals humanas, timeouts y rate limits.
- **Riesgo**: documentos multidioma incompletos. **Mitigación**: metadata de idioma, fallback explícito y señalización de fuente.

## 14. Logging y Observabilidad

Métricas custom: `hilo_chat_stream_duration_seconds`, `hilo_llm_tokens_total`, `hilo_llm_cost_total`, `hilo_rag_retrieval_duration_seconds`, `hilo_vectorization_jobs_total`, `hilo_mcp_tool_invocations_total`, `hilo_auth_login_attempts_total`. Audit actions: `auth_sign_in`, `auth_2fa_verified`, `model_activated`, `model_tested`, `document_uploaded`, `document_indexed`, `mcp_server_registered`, `mcp_tool_enabled`, `agent_run_started`, `chat_message_streamed`.

## 15. Verification Data

Carga idempotente de datos de verificación `python -m app.verification_data.bootstrap --source data/verification` carga exclusivamente datos reales/proporcionados entregados por People Tech: usuarios, employee profiles, documentos People ES/EN/FR, colecciones RAG, proveedores LiteLLM de verificación, MCPs sandbox autorizados y agentes de prueba. Si `data/verification/` no existe o le faltan campos obligatorios, el comando falla y bloquea la verificación. Reset con `scripts/dev-restart.sh --reset`.

## 16. Protocolo de Entrega

Cada slice requiere plan, implementación, validator, tester, evidencia, `/verify-slice` o `/verify-journey`, closer y PR. Phase gate obligatorio antes de pasar de fase.

## 17. Visualización

Mockups y HTML estático se guardan en `docs/visualization/hilo-people/` y `dist/hilo-people-preview.html`. Son referencia visual/evidencia, no source-of-truth canónico. El source-of-truth visual es `UX_CONTRACT.md` + tokens reales + componentes reales. La verificación visual se hace en navegador con `design_tokens_v1` y cada slice frontend debe documentar `VISUAL_CONTRACT_CHECK` en su handoff.

## 18. Relación con baseline

Sin existing baseline. No se arrastra nada de `docs/product-baseline`. Todo stack, rutas, tablas, endpoints, journeys, diseño y dependencias se declaran aquí y en los documentos canónicos.

## 19. Verificación de cableado pre-entrega

Revisión documental ejecutada dos veces antes de entregar: producto y scheduler. Se verificó que cada journey tiene pantallas, endpoints, tablas y slices; que las rutas del Technical Guide tienen slice; que los endpoints del Technical Guide aparecen en Coverage Registry; que las tablas están en DB schema y migration slices; y que no queda ningún marcador de plantilla.
