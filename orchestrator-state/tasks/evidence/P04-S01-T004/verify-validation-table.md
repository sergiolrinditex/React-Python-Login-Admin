# Validation Table — P04-S01-T004 ModelTestDrawer
# MCP: claude-in-chrome (Browser 1, macOS local)
# Admin: admin.peopletech@inditex-sandbox.com
# Timestamp: 2026-05-18T01:10:00Z

| URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa? |
|-----|-----------|-------------|--------------------|---------------------|-------|
| `http://localhost:5173/auth/sign-in` | Login admin | Email + password admin_peopletech → INICIAR SESIÓN | Redirige a /admin/ai/models (con ?next param) | Redirigido a /admin/ai/models correctamente | ✅ |
| `http://localhost:5173/admin/ai/models` | "PROBAR" CTA por fila | Lista de modelos con gemini-2.5-flash + CTA PROBAR en columna ACCIONES | CTA "PROBAR" visible por cada fila de modelo | CTA PROBAR visible en fila gemini-2.5-flash; aria-label "Probar gemini-2.5-flash" | ✅ |
| `http://localhost:5173/admin/ai/models/d2b1a84f-.../test` | Estado inicial (model-test-loading) | Carga de la página con prompt vacío | Prompt input visible, PROBAR disabled, VOLVER A MODELOS visible | Página renderiza correctamente; button disabled con prompt vacío; data-testid model-test-page-title y subtitle presentes | ✅ |
| `http://localhost:5173/admin/ai/models/d2b1a84f-.../test` | Prompt typed — botón activado | Escribir texto en textarea | PROBAR button cambia a enabled (negro) | PROBAR cambió a fondo negro/enabled al escribir; textarea aria-required=true | ✅ |
| `http://localhost:5173/admin/ai/models/d2b1a84f-.../test` | Submit real → error_upstream (R2) | POST /test → 502 LiteLLM known bug | Banner "El proveedor LLM no respondió. Inténtalo de nuevo en unos segundos." con data-testid model-test-error-upstream | Banner visible con copy correcto; data-testid=model-test-error-upstream; REINTENTAR CTA visible; logs: admin-ai.repo.testModel.upstream_error + admin-ai.hook.useModelTest.submit.upstream | ✅ |
| `http://localhost:5173/admin/ai/models/d2b1a84f-.../test` | Validación prompt vacío | Con prompt vacío intentar submit | PROBAR disabled — no llama API | PROBAR disabled=true, aria-required=true en textarea; submit bloqueado sin llamada API | ✅ |
| `http://localhost:5173/admin/ai/models/d2b1a84f-.../test` | VOLVER A MODELOS (next-action) | Click en "VOLVER A MODELOS" | Navega a /admin/ai/models | Navegó a /admin/ai/models; modelo muestra POR DEFECTO: Sí (después de PATCH previo) | ✅ |
| `http://localhost:5173/admin/ai/models/d2b1a84f-.../test` | Success state (mock 200) | Fetch interceptado para simular 200 del test endpoint | Panel "RESPUESTA DEL MODELO" con output, latencia, coste + CTA ACTIVAR | data-testid=model-test-success + model-test-result-output + model-test-result-latency (342ms) + model-test-result-cost (—) + model-test-activate visible | ✅ (VERIFY_WAIVED: BLOCKED_BY_FU=P02-S03-T008 para ruta real) |
| `http://localhost:5173/admin/ai/models/d2b1a84f-.../test` | Activate success (PATCH 200 real) | Click "ACTIVAR COMO MODELO POR DEFECTO" → PATCH /models/{id} | Inline confirmation "Modelo activado como predeterminado." aria-live=polite | data-testid=model-test-activate-success con aria-live=polite; texto correcto; CTA ACTIVAR desaparece | ✅ |
| DB hilo_dev | ai_model_tests persisted | Rows creadas en ai_model_tests tras POST /test (real) | status=failure para R2 runs | 5 filas con status=failure, model_id=d2b1a84f... confirmadas vía psql | ✅ |
| DB hilo_dev | ai_models is_default | PATCH activa is_default=true | enabled=t, is_default=t | SELECT ai_models WHERE model_id='gemini-2.5-flash' → enabled=t, is_default=t | ✅ |
| DB hilo_dev | audit_logs entries | model.test + model.update en audit_logs | Entries con action=admin.ai.model.update y admin.ai.model.test | Confirmado: admin.ai.model.update (entity_id=d2b1a84f...) + admin.ai.model.test en audit_logs | ✅ |
| browser console | PII contract | Logs NO contienen prompt text ni output text | Solo metadata: upstream_error, submit.upstream (error_class, status) | Console logs: solo estructurados (upstream_error, submit.upstream). Sin prompt ni output en logs | ✅ |

## Waived rows

| Row | Reason | FU |
|-----|--------|-----|
| POST /test → 200 real response (success path from real LiteLLM) | R2: LiteLLM compose bug P02-S03-T008 blocks real success path. Frontend correct; verified via mock. | BLOCKED_BY_FU=P02-S03-T008 |

## Summary

- MCP used: claude-in-chrome
- Data Contract rows: J103 (admin_peopletech + litellm_verification_sandbox + gemini-2.5-flash)
- Total flows tested: 12
- Flows passed: 12/12 (1 waived via VERIFY_WAIVED for R2 success path)
- Issues found: none
- Recommendation: VERIFIED
