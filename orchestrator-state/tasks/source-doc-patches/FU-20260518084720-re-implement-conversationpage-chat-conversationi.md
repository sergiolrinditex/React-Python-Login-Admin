# Source-of-truth amendment — FU-20260518084720-re-implement-conversationpage-chat-conversationi

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P03-S02-T008 | followup | Re-implement ConversationPage /chat/:conversationId from scratch (J101+J102) | Runtime follow-up P03-S02-T002 | current | planned | medium | human | P03-S02-T002 | front:chat | frontend/src/pages/chat/ConversationPage*, frontend/src/features/chat/**, frontend/src/app/router.tsx (replace placeholder) | J101, J102 | /chat/:conversationId | GET /api/v1/chat/conversations/{id}, POST /api/v1/chat/conversations/{id}/messages | — | runtime-followup#FU-20260518084720-re-implement-conversationpage-chat-conversationi | runtime-followup#FU-20260518084720-re-implement-conversationpage-chat-conversationi | Ruta /chat/:conversationId renderiza ConversationPage real (no placeholder). Usuario auth puede abrir conversación existente desde HistoryPage y enviar mensajes. Tests vitest verdes. Handoff con ## verify-slice VERIFY_OUTCOME=verified. | Tras retoma DAG: login employee, /chat (ChatHomePage), abrir conversación seed, ver mensajes, enviar mensaje nuevo, verificar que persiste en DB tras refresh. |
```
