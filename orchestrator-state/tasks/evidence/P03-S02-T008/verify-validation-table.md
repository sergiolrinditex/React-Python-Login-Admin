# Validation Table — P03-S02-T008 verify-slice

| URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa? |
|-----|-----------|-------------|-------------------|---------------------|-------|
| `http://localhost:5183/auth/sign-in` | Login con employee_primary + 2FA | Intro email+pw, 2FA TOTP | Aterriza en /chat | ✓ ChatHomePage a /chat | ✅ |
| `http://localhost:5183/chat/d45d8571-...` | Deep-link sin sesión → redirect | Navegar directo sin auth | Redirect a /sign-in?next=/chat/:id | ✓ URL preservada en ?next= | ✅ |
| `http://localhost:5183/chat/d45d8571-...` | ConversationPage renders | Login → 2FA → deep-link retorno | /chat/:id renderiza ConversationPage (NO ChatHomePage) | ✓ ConversationPage rend. | ✅ |
| `http://localhost:5183/chat/d45d8571-...` | error_network auto-stream | Última msg=user sin reply → auto-stream → LiteLLM 502 | NetworkErrorView con Retry CTA | ✓ error_network state visible | ✅ |
| `http://localhost:5183/chat/d45d8571-...` | i18n conversation.* keys | Labels del transcript y errores | "Tú", "Reintentar", "Error de conexión..." | ✗ RAW KEYS: "CONVERSATION.YOU", "conversation.errors.network.title" | ❌ |
| `http://localhost:5183/chat/00000000-...` | NotFoundView (404) | UUID inválido → GET 404 → NotFoundView | NotFoundView con CTA visible | ✓ NotFoundView renderiza (raw i18n keys) | PARTIAL |
| `http://localhost:5183/history` | Navegación a /history | Require auth | /history lista conversaciones | No probado (sesión caducó) | N/A |

## Defecto encontrado
- **i18n inline bundle vacío**: `frontend/src/i18n/index.ts` no tiene `conversation.*` keys en el namespace `chat`
- Keys en `public/locales/es/chat.json` existen y son correctas (verificado vía fetch JS)
- App usa inline static resources (sin HTTP backend), por lo que los JSON de /locales no se leen en runtime
- Scope: IN-SCOPE (i18n/index.ts pertenece al write_set de archivos compartidos que debía extenderse)

## Logs backend/frontend
- chat.stream.http_error (502 LiteLLM, expected R1) ✓
- chat.useChatStream.result.error ✓
- chat.conversation.render.start ✓
- chat.repo.getConversation.start/ok ✓

## Data Contract rows usados
- J101: employee_primary, rag_chat load (gemini absent → 502 ok per R1)
- J102: employee_primary, history load (2 conversations with user messages)

## MCP utilizado
claude-in-chrome
