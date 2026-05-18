# P03-S02-T008 Verification Re-run Validation Table
## Timestamp: 2026-05-18T19:15:00Z
## MCP: claude-in-chrome (Browser 1 — macOS local)
## Chrome DevTools MCP: blocked (SingletonLock PID=38510, scripts/chrome-mcp-doctor.sh output)

| URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa? |
|-----|-----------|-------------|--------------------|---------------------|-------|
| `http://localhost:5183/auth/sign-in` | Login employee_primary + password | Email+pass form → submit | 2FA screen con "Verificación en dos pasos" | 2FA screen mostrada en ES (pass) | ✅ |
| `http://localhost:5183/auth/2fa` | 2FA TOTP entry | Introduce código 6 dígitos → "VERIFICAR Y ENTRAR" | Redirect a /chat (ChatHomePage) | ChatHomePage con "¿En qué puedo ayudarte?" en ES | ✅ |
| `http://localhost:5183/chat/d45d8571-2167-4f86-9a1f-ade71ddda36b` | Deep-link sin sesión activa | Navegar a URL protegida → debe redirigir a sign-in preservando next param | URL auth/sign-in?next=%2Fchat%2Fd45d8571... | Redirigido correctamente con next param preservado | ✅ |
| `http://localhost:5183/chat/d45d8571-2167-4f86-9a1f-ade71ddda36b` | ConversationPage — user role label i18n | Label "TÚ" sobre el mensaje del usuario (ES) | "TÚ" en español (NO raw key CONVERSATION.YOU) | "TÚ" renderizado correctamente (FIX CONFIRMADO) | ✅ |
| `http://localhost:5183/chat/d45d8571-2167-4f86-9a1f-ade71ddda36b` | ConversationPage — error_network i18n | 502 LiteLLM → error_network view | "Error de conexión. Por favor, inténtalo de nuevo." + "REINTENTAR" (NO raw keys) | "Error de conexión. Por favor, inténtalo de nuevo." y "REINTENTAR" visibles (FIX CONFIRMADO) | ✅ |
| `http://localhost:5183/chat/d45d8571-2167-4f86-9a1f-ade71ddda36b` | ConversationPage — auto-stream trigger | Página con último mensaje de rol user → auto-start stream | POST /stream llamado automáticamente | POST /api/v1/chat/.../stream → 502 visible en network tab (auto-stream disparado correctamente) | ✅ |
| `http://localhost:5183/chat/00000000-0000-0000-0000-000000000000` | NotFoundView i18n | Fake UUID → 404 → NotFoundView | "CONVERSACIÓN NO ENCONTRADA." + "NUEVO CHAT" (NO raw keys) | "CONVERSACIÓN NO ENCONTRADA." y "NUEVO CHAT" visibles (FIX CONFIRMADO) | ✅ |
| Backend API | GET conversation → 200 | GET /api/v1/chat/conversations/d45d8571... | 200 con ConversationDetail shape | HTTP 200 observado en network (request 1) | ✅ |
| Backend API | GET conversation → 404 | GET /api/v1/chat/conversations/00000000... | 404 CHAT_CONVERSATION_NOT_FOUND | HTTP 404 + chat.repo.getConversation.not_found log | ✅ |
| Backend API | POST stream → 502 | POST /api/v1/chat/conversations/d45d8571.../stream | 502 LiteLLM absent (R1 risk, expected) | HTTP 502 + chat.stream.http_error log | ✅ (expected R1) |

## i18n parity table (code-verified)

| Clave | ES (L210) | EN (L845) | FR (L1480) | Antes del fix |
|-------|-----------|-----------|------------|---------------|
| conversation.you | "Tú" | "You" | "Vous" | AUSENTE (raw key) |
| conversation.assistant | "Asistente" | "Assistant" | "Assistant" | AUSENTE (raw key) |
| conversation.errors.notFound.title | "Conversación no encontrada." | "Conversation not found." | "Conversation introuvable." | AUSENTE (raw key) |
| conversation.errors.notFound.cta | "Nuevo chat" | "New chat" | "Nouveau chat" | AUSENTE (raw key) |
| conversation.errors.network.title | "Error de conexión. Por favor, inténtalo de nuevo." | "Connection error. Please try again." | "Erreur de connexion. Veuillez réessayer." | AUSENTE (raw key) |
| conversation.errors.network.retry | "Reintentar" | "Try again" | "Réessayer" | AUSENTE (raw key) |
| conversation.errors.permission.title | "No tienes acceso a esta conversación." | "You do not have access to this conversation." | "Vous n'avez pas accès à cette conversation." | AUSENTE (raw key) |
| conversation.errors.permission.cta | "Volver al chat" | "Back to chat" | "Retour au chat" | AUSENTE (raw key) |

**Todos los keys ausentes confirmados presentes post-debugger fix en i18n/index.ts.**
**ES verificado en browser. EN y FR verificados por inspección de código (inline bundle L845, L1480).**

## Logs verbosos confirmados
- chat.repo.getConversation.not_found ✅
- chat.hook.useConversation.fetch.error ✅
- chat.conversation.render.not_found ✅
- chat.stream.http_error ✅
- chat.useChatStream.result.error ✅
- Sin raw keys en consola ✅
- Sin warnings i18next missing-key ✅

## Recomendación: VERIFIED
