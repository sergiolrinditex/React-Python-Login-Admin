# UX_CONTRACT — Hilo People

## 1. UX purpose

Hilo ofrece una experiencia editorial, mínima y corporativa para que empleados de Inditex resuelvan dudas de People/RRHH mediante conversación. El chat es el home tras login. Admin AI es una superficie desktop separada para People Tech, centrada en gobierno de modelos, RAG, MCP, agentes, uso y auditoría. La identidad visual sigue código editorial Inditex/Zara: fondo crudo, tinta negra, serif de alto contraste, hairlines, etiquetas uppercase tracked, cero esquinas redondeadas y CTAs sólidos negros.

## 2. Personas

| Persona | Goal | Critical journeys | Data required |
|---|---|---|---|
| Empleado Inditex | Preguntar dudas de People en móvil y recibir respuesta breve con fuentes | J100, J101, J102 | user profile, employee profile, conversations, documents indexed |
| People Tech Admin | Configurar proveedores/modelos, RAG, MCP y agentes con auditoría | J103, J104, J105 | ai providers, encrypted credentials, rag docs, mcp servers, agents |
| Auditor People | Revisar eventos, coste y trazabilidad sin cambiar configuración | J103, J104, J105 | audit logs, usage logs, read-only access |

## 3. Screen inventory

| Route | Screen/Page | Primary journey refs | Required UI states | Real data contract |
|---|---|---|---|---|
| /auth/sign-in | SignInPage | J100 | loading, error_network, error_validation, permission_denied, success | employee de verificación real/proporcionado with MFA challenge |
| /auth/sign-up | SignUpPage | J100 | loading, error_network, error_validation, permission_denied, success | email corporativo real/proporcionado |
| /auth/forgot-password | ForgotPasswordPage | J100 | loading, error_network, error_validation, success | reset token de verificación emitido por email provider sandbox autorizado |
| /auth/reset-sent | ResetSentPage | J100 | loading, empty, error_network, success | masked email from previous step |
| /auth/2fa | TwoFactorPage | J100 | loading, error_network, error_validation, permission_denied, success | MFA TOTP generated from `data/verification/auth/mfa_primary.json` |
| /chat | ChatHomePage | J100, J101 | loading, empty, error_network, permission_denied, success | current user and empty conversation state |
| /chat/:conversationId | ConversationPage | J101, J102 | loading, empty, streaming, error_network, error_validation, permission_denied, success | persisted conversation, messages, citations |
| /history | HistoryPage | J102 | loading, empty, error_network, permission_denied, success | at least two conversaciones persistidas reales/proporcionadas |
| /account | AccountPage | J102 | loading, error_network, error_validation, permission_denied, success | employee profile and language preference |
| /admin | AdminDashboardPage | J103 | loading, empty, error_network, permission_denied, success | usage summary |
| /admin/ai/models | AdminAiModelsPage | J103 | loading, empty, error_network, permission_denied, success | providers and models |
| /admin/ai/models/new | ModelWizardPage | J103 | loading, empty, error_network, error_validation, permission_denied, success | credencial de proveedor real/proporcionada para entorno sandbox autorizado |
| /admin/ai/models/:modelId/test | ModelTestDrawer | J103 | loading, error_network, error_validation, permission_denied, success | modelo y prompt reales/proporcionados |
| /admin/rag/documents | RagDocumentsPage | J104 | loading, empty, uploading, indexing, error_network, error_validation, permission_denied, success | PDF/DOCX real/proporcionado del data/verification proporcionado and collection |
| /admin/rag/collections | RagCollectionsPage | J104 | loading, empty, error_network, error_validation, permission_denied, success | rag collections |
| /admin/ai/mcp | McpServersPage | J105 | loading, empty, syncing, error_network, permission_denied, success | MCP sandbox server |
| /admin/ai/mcp/new | McpWizardPage | J105 | loading, error_network, error_validation, permission_denied, success | endpoint/auth real/proporcionado para MCP sandbox autorizado |
| /admin/ai/agents | AgentsPage | J105 | loading, empty, error_network, error_validation, permission_denied, success | agents and approved tools |
| /admin/audit | AuditLogPage | J103, J104, J105 | loading, empty, error_network, permission_denied, success | audit log rows |
| /admin/usage | UsagePage | J103 | loading, empty, error_network, permission_denied, success | llm usage rows |

## 4. Interaction model

- Login: form fields are full-width, hairline only, no rounded card containers. Success moves to 2FA or directly to chat. Errors are inline and translated.
- Chat: empty state shows Hilo wordmark and three prompt suggestions. Conversation uses no bubble styling; assistant copy uses serif, user copy uses sans. Citations are inline links with source label.
- History: grouped by relative date with hairline separators. Empty state invites starting a new chat.
- Account: shows employee data, language selector ES/EN/FR and logout as underlined action.
- Admin AI: desktop shell with left nav, model table, status dot, active state and model test drawer. No colored badges beyond monochrome dots.
- RAG Admin: upload strip + document table + indexing progress. Collection status uses dot + tracked label.
- MCP/Admin Agents: server list, tool approval states, risk labels, binding controls and audit trail.

## 5. Verification rules

J100-J105 require real/proporcionado persisted data created by `python -m app.verification_data.bootstrap --source data/verification`. Empty states, network errors, permission denied and invalid payload validation are verified with real/provided baseline data plus controlled technical simulations of the error condition, never with decorative invented business data. No journey is considered verified using non-persisted frontend data or invented decorative data.

## 6. Accessibility and responsive minimum

All forms have labels, visible focus, keyboard navigation and error text linked by aria-describedby. Mobile target width is 402 px; admin target is 1440 px. Contrast uses black on crude/white backgrounds. Text never relies on color alone; statuses combine dot and uppercase tracked label. Reduced motion users must not see mandatory animation.
