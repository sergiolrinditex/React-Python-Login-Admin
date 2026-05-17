# Validation Table — P04-S02-T004 McpWizardPage

MCP used: claude-in-chrome (tab 777662329)
Date: 2026-05-17T23:05:00Z
Admin: admin.peopletech@inditex-sandbox.com
Data contract rows: J105 mcp-agents (sandbox_readonly seed + sandbox_writeonly created by verify)

| URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa? |
|-----|-----------|-------------|--------------------|---------------------|-------|
| `http://localhost:5173/admin/ai/mcp/new` | W01 form render | 4 campos visibles: NOMBRE, TRANSPORTE (HTTP/SSE), ENDPOINT, TIPO DE AUTENTICACIÓN | 4 campos, sin stdio, editorial design tokens | 4 campos visibles, TRANSPORTE=HTTP/SSE (sin stdio), diseño editorial correcto (cream bg, hairlines, uppercase labels, black CTA) | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W05 error_validation (name empty) | Submit sin nombre → error inline | "Nombre obligatorio" debajo del campo | "Nombre obligatorio" visible inline bajo NOMBRE | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W05 error_validation (endpoint invalid) | Submit con endpoint="not-a-url" | "Debe empezar por http:// o https:// o sse://" | "Debe empezar por http:// o https:// o sse://" visible inline bajo ENDPOINT | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W07 secret rendering (api_key) | auth_type=api_key → campo SECRETO visible | Campo SECRETO aparece | Campo SECRETO aparece bajo TIPO DE AUTENTICACIÓN | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W09 oauth2 fields | auth_type=oauth2 → SECRETO + REFRESH TOKEN visibles | Ambos campos aparecen | SECRETO + REFRESH TOKEN visibles con oauth2 | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W09 none → fields disappear | auth_type=none → sin secret/refreshToken | Campos ocultos | accessibility tree: no wizard-secret, no wizard-refresh-token con auth=none | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W10 secret never persisted | Secreto type=password, no en storage ni DOM | type=password, autocomplete=off, spellcheck=false | Confirmado vía JS: type=password, autocomplete=off, spellcheck=false; localStorage=[i18nextLng]; sessionStorage=[adobeCleanFontAdded] | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W03 success (auth=none) | Submit name=sandbox_writeonly, transport=http, endpoint=http://localhost:8080/mcp, auth=none → 201 → navigate | 201 POST, auto-navigate a /admin/ai/mcp, nueva fila visible | POST 201, navegación automática a /admin/ai/mcp, sandbox_writeonly aparece en lista con status BORRADOR | ✅ |
| `http://localhost:5173/admin/ai/mcp` | W03 query invalidation | Lista actualizada sin reload manual | sandbox_writeonly en lista tras 201 | sandbox_writeonly visible inmediatamente en /admin/ai/mcp (GET /servers 200) | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W04 error_network (500→error) | Submit con api_key y ENCRYPTION_KEY ausente → 500 → form-level error | "Error de red. Vuelve a intentarlo." | "Error de red. Vuelve a intentarlo." visible, form preserved con valores, sin navegación | ✅ |
| `http://localhost:5173/admin/ai/mcp/new` | W06 permission_denied (route guard) | employee user intenta acceder | RequireRole redirige a /auth/sign-in | Redirect a /auth/sign-in?next=/admin/ai/mcp/new (RequireRole funciona) | ✅ |
| DB | mcp_servers persisted | sandbox_writeonly en DB con status=draft | id, name, transport_type=http, endpoint_url=http://localhost:8080/mcp, status=draft | Confirmado: id=31f26fd7-..., name=sandbox_writeonly, transport_type=http, status=draft | ✅ |
| DB | mcp_credentials ausentes para auth=none | COUNT=0 para auth=none servers | 0 filas en mcp_credentials | 0 filas para sandbox_writeonly y verify-T004-loading-test | ✅ |

## NEXT_ACTION_VERIFIED

After successful create, the user is on /admin/ai/mcp list page. The new server row (sandbox_writeonly) shows:
- Status: BORRADOR
- Transport: HTTP  
- Action button: SINCRONIZAR

This SINCRONIZAR button is the next action for J105 journey (sync → discover tools → assign to agent). 
NEXT_ACTION_VERIFIED: yes
