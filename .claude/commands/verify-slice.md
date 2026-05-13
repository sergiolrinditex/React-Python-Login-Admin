---
description: Verificación humana-real post-slice. Hard reset del entorno (back + front + bbdd con carga de datos reales/proporcionados del slice), reproduce como usuario en el navegador, vigila logs front+back+bbdd en vivo, devuelve tabla de validación con URL, qué probar, descripción y resultado esperado. Agnóstico del stack.
argument-hint: "<TASK_ID>|--task <TASK_ID>  (o terminal con CLAUDE_ACTIVE_TASK_ID exportado)"
---

# /verify-slice
## Rule loading

Antes de ejecutar este comando, considera cargadas las reglas no-scoped de `.claude/rules/`. Si no ves esas reglas en contexto tras `/clear`, léelas explícitamente en este orden: `00-source-of-truth.md`, `01-non-negotiables.md`, `02-phase-execution.md`, `03-dev-loop.md`, `04-traceability.md`, `05-runtime-write-contract.md`.


## Production DAG mode — recordatorio obligatorio

Antes de verificar, confirma el checkout correcto: ejecuta `./scripts/ensure-task-worktree.sh --check-current <TASK_ID>`. En `pr-flow`, `/verify-slice` debe correr desde el worktree/rama del TASK_ID; en `push-to-main`, desde `main`. Si estás en otro checkout, PARA: no verifiques una rama distinta a la que implementó el developer.


Antes de reconstruir contexto, verificar, decidir `pre-closer`/`post-closer`, spawnear `debugger` o spawnear `closer`, repite internamente este invariante y respétalo durante todo el comando:

```text
MODO DAG ACTIVO: production = explicit_dag.
Unidad verificable = TASK_ID canónico del registry.
No existe modo DAG-disabled improvisado.
No dependas de ningún singleton global para decidir qué verificar; en DAG-only se exige TASK_ID explícito.
Usa siempre orchestrator-state/tasks/task-packs/<TASK_ID>.md como task pack en DAG.
Todo Agent spawn desde verify-slice debe recibir TASK_ID, CLAUDE_TASK_PACK y el aviso production DAG mode. Esto incluye `screen-journey-reviewer`, `debugger` y `closer`.
```

Si dudas si estás en DAG, para y consulta `./scripts/check-task-dag.sh --strict`. En producción la ausencia de `Depends on` es error operativo, no fallback. `/verify-slice` es el gate humano de un `TASK_ID` DAG concreto; no verifica una flujo no habilitado para DAG ni cierra slices implícitas.

Te lanzas **después de que `tester` pasa limpio, antes de que `closer` haga commit** (modo pre-closer, el habitual). También puede lanzarse **tras `closer`** para re-verificar un slice ya commiteado (modo post-closer). Tu trabajo es convencerte a ti mismo (y al usuario) de que lo shipeado funciona de verdad, reproduciéndolo como un usuario humano en el navegador, con entorno fresco, datos reales/proporcionados cargados y logs en vivo. En modo pre-closer, si la slice queda verificada orquestas tú mismo al `closer` para commit atómico + workflow Git configurado; si encuentra issues, orquestas al `debugger`.

**Tras `/clear`**: este comando es 100% resiliente al `/clear`. No depende del contexto conversacional previo — reconstruye todo desde disco (PROGRESS.md, runtime-state.json, registry.json, handoff). Puedes y debes hacer `/clear` antes de `/verify-slice` para liberar los ~100-200k tokens del pipeline previo.

**Comandos hermanos**: `/next-slice`, `/verify-journey <JID>` (gate end-to-end por journey, distinto de éste que es por slice), `/revise-slice <TASK_ID>` (corrección) y `/slice-maintain clean|compact`. Orden recomendado al cerrar una slice: tester pass → (opcional `/clear`) → `/verify-slice` (orquesta `closer` si verificado) → `/slice-maintain clean` → `/clear` → `/next-slice`.

**Principios (no negociables)**:

- **Hard reset SIEMPRE.** Parar servicios, resetear bbdd, reinyectar datos base reales/proporcionados, inyectar datos específicos para lo que shipeó el slice, reiniciar back y front. No confíes en el estado anterior.
- **Reproduce como humano.** Abre la app, navega, rellena formularios, pulsa botones, lee respuestas. Tantas interacciones como flujos tenga el slice.
- **Vigila los 3 logs a la vez.** Front, back y bbdd en paralelo.
- **Solo lectura de código.** No modificas producción, no añades tests, no cambias carga de datos existente.
- **Agnóstico del stack.** Todo lo específico (stack, comandos, puertos, health, carga de datos, migraciones) se lee del TECHNICAL_GUIDE en runtime.
- **Tú eliges las herramientas.** Cada paso describe la acción, no la tool.

---

## Paso 1 — Identificar qué reproducir

En paralelo:

1. `orchestrator-state/tasks/runtime-state.json` → `last_worker`, `last_event`, `pending_journey_verifications`; la identidad del verify viene sólo de `<TASK_ID>` o `CLAUDE_ACTIVE_TASK_ID`.
2. `orchestrator-state/memory/PROGRESS.md` (bloque NOW + primer PREVIOUSLY).
3. Usa `TASK_ID` sólo desde `--task <ID>`, argumento directo o `CLAUDE_ACTIVE_TASK_ID`. Si falta, PARA y pide un `TASK_ID` explícito.
4. Evidence report del task si ya existe: `orchestrator-state/tasks/reports/<TASK_ID>.md` (solo existirá si `closer` ya corrió).
5. Handoff: `orchestrator-state/tasks/handoffs/<TASK_ID>.md` (tiene las secciones developer/validator/tester — tiene que existir sí o sí).
6. `orchestrator-state/tasks/task-packs/<TASK_ID>.md`. No dependas de implicit selector; está eliminado del modo DAG en DAG. Si el pack no existe o no menciona ese `TASK_ID`, aborta antes de verificar.
6. `docs/source-of-truth/*_TECHNICAL_GUIDE.md` — extrae: comando de arranque back (+ puerto), frontend (+ puerto/plataforma), comando migrate, comando de carga de datos, endpoint de health, flag de verbose logging.
7. `docs/source-of-truth/*_TECHNICAL_GUIDE.md` §`Verification Data Contract` — identifica las filas que aplican por `TASK_ID`, `Journey refs`, pantalla o endpoint. Estas filas son obligatorias para decidir datos reales/proporcionados, datos proporcionados permitidos solo si cargan datos proporcionados y reset/cleanup.
8. `instrucciones.md` → reglas de negocio relevantes al slice (las usarás en la tabla final).

**Del handoff (+ evidence si existe) identifica**:

- Back: endpoints nuevos (verbo + ruta), servicios, reglas de negocio.
- Front: pantallas, rutas, componentes, flujos de usuario.
- BBDD: tablas, columnas, índices, datos esperados.
- Datos reales/proporcionados necesarios para ejercer lo shipeado (más allá de los datos base reales/proporcionados).
- Forward-carries de seguridad si los hay.

Si NO hay handoff → aborta: *"La tarea no tiene handoff. Completa el pipeline hasta tester pass antes de verificar."*

### 1.1 — Detecta el modo de verify

- **Modo `pre-closer`** (lo habitual, y lo correcto semánticamente): handoff con developer + validator + tester, PERO **sin** evidence report en `orchestrator-state/tasks/reports/<TASK_ID>.md`, y la tarea en `registry.json` NO está `done`. Verify es el gate humano previo al `closer`. Si verificada, orquestas al closer en el Paso 6. Si hay issues, orquestas al debugger.
- **Modo `post-closer`** (re-verify): evidence report ya existe y/o la tarea está `done` en registry. Verify solo reporta outcome — NO orquesta closer ni debugger. Si encuentra issues, el usuario decide si abre slice nueva o revert.

En modo `pre-closer`, chequea en el handoff:

- `validator` OUTCOME == `approved`.
- `tester` OUTCOME == `pass` (o waive explícito con razón).

Si falta algo → aborta: *"Pipeline no cerró limpio (validator/tester no pasaron). Pasa por debugger antes de verify."*

---

## Paso 2 — HARD RESET del entorno

Objetivo: partir de cero con datos base reales/proporcionados + datos específicos del slice, back + front arriba con logging verbose.

### 2.1 Parar servicios

- Localiza procesos en puertos back + front. Ofrece al usuario pararlos mostrando PID y comando de kill. **No mates procesos sin preguntar.**
- Si usa contenedores, lista estado actual.

### 2.2 Reset bbdd

- Procedimiento del TECHNICAL_GUIDE (drop+create, volumen docker, truncate).
- Migraciones hasta **head** con el comando oficial (Alembic, Prisma, Knex, Flyway, migrate...).
- Si no está documentado → para y reporta: *"No encuentro comando de reset en TECHNICAL_GUIDE. Indícamelo."*

### 2.3 Datos base reales/proporcionados

- Comando de carga de datos del TECHNICAL_GUIDE, si existe, sólo para datos reales/proporcionados.
- Verifica con SELECT COUNT por tabla principal que los números coinciden con el contrato/evidence de datos reales/proporcionados.

### 2.4 Datos específicos reales/proporcionados del slice (paso clave — NO saltes)

A partir de lo identificado en Paso 1, carga solo datos reales/proporcionados necesarios para ejercer todos los flujos del slice. La fuente autoritativa es el `Verification Data Contract` del TECHNICAL_GUIDE:

- Usa datos reales/proporcionados por el usuario o el equipo: usuarios sandbox autorizados, catálogos reales de prueba, documentos representativos proporcionados, importes/fechas/estados coherentes y relaciones completas.
- No uses `lorem ipsum`, IDs inventados sin persistencia, mocks de negocio, datos decorativos ni datos no proporcionados para cerrar una slice productiva.
- Los datos sintéticos no deben usarse para cerrar una slice productiva. Para casos marginales (`empty`, `error_network`, permisos, payload inválido), usa datos proporcionados o bloquea/registra follow-up si faltan.
- Si el slice añade "listar pedidos de un usuario" → usa pedidos reales/proporcionados persistidos con distinto estado y usuario real/sandbox autorizado; si faltan, bloquea o registra follow-up de datos.
- Si añade "filtro por rango de precios" → asegura que el carga de datos cubre el rango; si no, inserta lo que falta.
- Si añade "notificación al superar umbral" → inserta el registro que fuerza el umbral.

Usa SQL directo (transacción parametrizada) o el script de carga de datos del proyecto si existe. **NO hagas inserts vía la propia API del slice** — eso contamina la verificación.

Documenta en el reporte final qué filas del `Verification Data Contract` usaste, qué datos reales/proporcionados cargaste y qué filas persistidas observaste.

### 2.5 Arrancar back + front con verbose on

- `ENABLE_VERBOSE_LOGGING=true` (o la flag del TECHNICAL_GUIDE).
- Arranca back; verifica health → 200.
- Arranca front; verifica que sirve.

---

## Paso 3 — Reproducción humana

Abre el navegador en la URL del front. Reproduce TODOS los flujos identificados en Paso 1:

- Navegar a la pantalla nueva.
- Rellenar formularios con datos reales.
- Pulsar botones, submits, navegación.
- Casos felices + casos de error (submit vacío, payload inválido, sin permisos).
- Cada interacción: observa UI + logs front + logs back + DB rows.

Usa `ToolSearch` para descubrir qué MCPs tienes disponibles en esta sesión y elige el más adecuado para cada verificación. A día de hoy hay Chrome DevTools MCP, claude-in-chrome, MCP específico del framework declarado y computer-use — pero puede haber más, búscalos antes de asumir que no existen. Si uno falla o se desconecta, prueba con otro. Si ninguno sirve, describe los pasos al usuario y espera su feedback, o verifica los flujos directamente contra la API con `curl`/`httpx`.

---

## Paso 4 — Observación de logs en vivo

Durante la reproducción, mira en 3 paneles:

- **Logs front**: consola browser + stdout del dev server. Busca errores, warnings, network failures, render issues.
- **Logs back**: stdout del backend. Cada request debe dejar BEFORE/AFTER. Sin tokens/PII.
- **Logs bbdd**: queries ejecutadas (ver flag del ORM, ej Alembic echo, Prisma log). Verifica que las queries coinciden con lo esperado y que los índices se usan.

Guarda snippets relevantes en `orchestrator-state/tasks/evidence/<TASK_ID>/verify-*`.

---

## Paso 5 — Tabla final de validación

Presenta al usuario una tabla con:

| URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa? |
|-----|-----------|-------------|--------------------|---------------------|-------|
| `http://localhost:<FRONT_PORT>/<ruta>` | Submit formulario X | Rellena Y, pulsa Z | Aparece pantalla W con dato K | <...> | ✅/❌ |
| ... | ... | ... | ... | ... | ... |

Incluye también:

- Filas del `Verification Data Contract` usadas.
- Datos reales/proporcionados cargados (lista).
- Datos persistidos observados, con tabla/ID/estado cuando aplique.
- Queries observadas en bbdd (las relevantes al slice).
- Hallazgos: cualquier cosa que no cuadre con lo esperado.
- Reglas de negocio verificadas vs pendientes.
- Recomendación: `VERIFIED` / `ISSUES FOUND (volver a debugger)`.

### 5.1 — Appendea sección al handoff (obligatorio)

Añade al final de `orchestrator-state/tasks/handoffs/<TASK_ID>.md` una sección nueva (nunca sobreescribas). Esta sección es el contrato que lee `closer`; no basta con mencionarlo en el chat final. Usa campos `KEY: value` claros para evitar ambigüedad tras `/clear`:

```markdown
## verify-slice

- TASK_ID: <TASK_ID>
- TIMESTAMP: <ISO-8601>
- MODE: pre-closer|post-closer
- VERIFY_OUTCOME: verified|issues_found
- DATA_CONTRACT_ROWS: <filas/IDs del Verification Data Contract usadas; required>
- DATA_SETUP: <lista 1 línea por dato real/proporcionado cargado; o n/a con razón>
- PERSISTED_DATA_OBSERVED: <tabla/id/estado o n/a con razón>
- FLOWS_TESTED: <lista corta>
- FINDINGS: <bullets si issues_found; none si verified>
- EVIDENCE: orchestrator-state/tasks/evidence/<TASK_ID>/verify-*
```

El `closer` leerá esta sección en su pre-check. Sin ella, sin `TASK_ID` coincidente o sin `VERIFY_OUTCOME: verified`, el closer rechaza el cierre.

Después de apendizarla, valida mecánicamente el handoff antes de invocar `closer`:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice
```

Si falla, no invoques `closer`; corrige el handoff o relanza el agente que escribió mal su sección.

---

## Paso 5.2 — Screen/Journey review condicional antes de closer

Este paso protege la nueva realidad del orquestador: pantallas y journeys se cierran por experiencia completa, no por capas aisladas ni por HTML estático.

Ejecuta este paso **solo si** la task cumple alguno de estos criterios, leyendo `registry.json`, task pack y handoff:

- `kind`/`Tipo` es `frontend`, `ui`, `ux`, `journey`, `gate` o visual.
- Tiene `Pantalla/Ruta`, `route`, `Journey refs` o `journey_refs`.
- Acceptance, handoff o evidencia mencionan `VISUAL_CONTRACT_CHECK`.
- La verificación humana reprodujo una pantalla, navegación, estado UX o evidencia visual.

Si no aplica, escribe en tu tabla final `screen_journey_review: not_applicable` y sigue a §5.bis.

Si aplica y `VERIFY_OUTCOME: verified`, spawnea **un único** subagente `screen-journey-reviewer` antes de `closer`, con este contexto literal:

```text
TASK_ID: <TASK_ID>
CLAUDE_TASK_PACK: orchestrator-state/tasks/task-packs/<TASK_ID>.md
MODO DAG ACTIVO: production = explicit_dag.
No uses global state; exige `TASK_ID` explícito.
Revisa UX_CONTRACT.md, Technical Guide, Implementation Checklist, handoff, verify-slice y evidencia.
HTML preview/docs visuales son referencia/evidencia, no source-of-truth.
Si el problema cabe en TASK_ID/Write set: OUTCOME: changes_requested; needs_debugger=yes; NO FU.
Si falta trabajo/datos/contrato fuera de scope: OUTCOME: blocked; followup_candidate=yes; why_not_debugger obligatorio.
Apendiza `## Screen/Journey review` al handoff.
```

Después del subagente, ejecuta:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice --require-screen-journey-review
```

Decisión:

- `OUTCOME: approved` en `## Screen/Journey review` → continúa a §5.bis / closer.
- `OUTCOME: changes_requested` → trata los hallazgos como `issues_found` aunque tu reproducción inicial pareciera bien: salta a §6.2, invoca `debugger`, repite `validator ‖ tester` y relanza `/verify-slice`. No crees FU para defectos reparables dentro del `TASK_ID`.
- `OUTCOME: blocked` → no invoques `closer`. Si `followup_candidate=yes`, registra FU formal con `--scope-classification` y `--why-not-debugger`; si falta información, pide decisión humana.

Si el reviewer no escribe `## Screen/Journey review`, no cierres. Corrige/repite el reviewer o bloquea.

---

## Paso 5.bis — Journey-closing inline (solo si VERIFY_OUTCOME: verified)

**Solo se ejecuta si**: la verificación de slice salió `verified` Y la slice cierra al menos un journey de la Journey Coverage Matrix. Si `issues_found` → salta este paso y ve directo al Paso 6.

### 5.bis.1 — Detectar journey-closing

Lee `orchestrator-state/tasks/registry.json:journeys[]`. Para cada journey J:

- Ejecuta `python3 -B -S .claude/bin/list_journey_closures.py <TASK_ID> --json`.
- Usa `closing_journeys[]` del script como fuente autoritativa. El script simula este TASK_ID como `done` y solo marca cierre cuando todos los demás slices del journey ya están `done`.
- No uses `task_ids[-1]`: en DAG la columna `Slices` puede venir de rangos, step refs o listas humanas desordenadas.

Si `closing_journeys` está vacía → salta al Paso 6 directamente. No hay journey que verificar.

### 5.bis.2 — Pregunta al usuario (gate humano único)

```
✅ Slice <TASK_ID> verificada. Esta slice cierra el/los journey(s):
   <lista: J5 — login flow, J7 — password change, ...>

El entorno ya está hard-reset y los datos reales/proporcionados cargados. Tienes dos opciones:

  a) ahora     — verifico el journey end-to-end inline (multi-pantalla, estados
                 marginales, deep links, next action). Aprovecho el entorno y
                 cierro slice + journey en un solo gate humano. RECOMENDADO.

  b) aparte    — solo verifico la slice. Dejo el journey en pending y el
                 usuario lanzará `/verify-journey <JID>` después en una
                 sesión limpia. Útil si tienes prisa o quieres tomarte el
                 journey con más calma.

¿Cómo procedemos? (ahora / aparte)
```

Interpreta la respuesta:

- **`ahora` | `inline` | `sí` | `go`** → ejecuta §5.bis.3 inline.
- **`aparte` | `luego` | `después` | `no`** → salta §5.bis.3, ve al Paso 6 con la rama "luego" (el closer emitirá `JOURNEY_PENDING_VERIFY` para cada journey).

### 5.bis.3 — Verificación journey inline

Mismo procedimiento que `/verify-journey` pero aprovechando el entorno actual:

1. **Datos reales/proporcionados consolidados**: añade encima de los datos actuales los necesarios para reproducir el journey COMPLETO (no solo esta última slice). Lista mínima: estados intermedios entre pantallas, datos para deep links, datos que dispararían rama de error.
2. **Reproducción end-to-end**: navega el journey en orden de pantallas. Para cada paso: rellena, pulsa, observa logs (front + back + bbdd) y UI.
3. **Estados marginales obligatorios** (mínimo, según la sección **Recorridos del usuario** y la **Journey Coverage Matrix** de `instrucciones.md`):
   - `loading` (durante transiciones de pantalla)
   - `empty` (datos no presentes)
   - `error_network` (offline / 500)
   - `permission_denied` (si aplica al journey)
   - `back_navigation` (botón atrás del SO/navegador)
   - `deep_link` (entrada por URL directa al medio del journey)
   - `next_action` (lo que sugiere la pantalla final como siguiente paso)
4. **Evidencia**: snippets en `orchestrator-state/tasks/evidence/<TASK_ID>/verify-journey-*`.

Apendiza al handoff (después de `## verify-slice`) con `TASK_ID` coincidente:

```markdown
## verify-journey

- TASK_ID: <TASK_ID>
- TIMESTAMP: <ISO-8601>
- MODE: inline
- JOURNEYS: <lista de JIDs verificados juntos en este bloque>
- JOURNEY_VERIFY_OUTCOME: verified|issues_found
- FLOWS_TESTED: <pantallas en orden>
- MARGINAL_STATES_TESTED: loading, empty, error_network, permission_denied, back_navigation, deep_link, next_action
- NEXT_ACTION_VERIFIED: yes|no|n/a
- FINDINGS: <bullets si issues_found>
- EVIDENCE: orchestrator-state/tasks/evidence/<TASK_ID>/verify-journey-*
```

Si `issues_found` → cancela el cierre, salta al Paso 6 con rama issues (debugger). El journey NO queda verificado; el usuario tendrá que arreglar y volver a verificar.

---

## Paso 6 — Orquestación de cierre (solo en modo `pre-closer`)

En modo `post-closer` este paso se salta — el commit ya existe; solo entrégale al usuario la tabla del Paso 5.

### 6.1 — Si `VERIFY_OUTCOME: verified`

Recapitula al usuario el estado real (con la información de §5.bis si aplica):

```
✅ Slice <TASK_ID> verificada.
<si hubo journey inline:>
   ✅ Journey(s) <lista JIDs> verificada(s) inline en el mismo gate.
<si quedó "aparte":>
   ⏸ Journey(s) <lista JIDs> queda(n) pendiente(s) — el closer emitirá
     JOURNEY_PENDING_VERIFY. En modo frontier solo se diferirán tasks que
     referencien esos JIDs. No existe otro modo de journey gate.
<si la slice no cierra journey:>
   (esta slice no cierra ningún journey — flujo normal)

¿Invoco a `closer` para escribir evidence report + commit atómico + workflow Git configurado (`./scripts/git-workflow.sh`) + cleanup de worktrees? (sí/no)
```

- Si "sí" / "adelante" / "ok" / "dale" / "go" → primero ejecuta `./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice`. Solo si pasa —y, cuando aplique pantalla/journey, también pasa con `--require-screen-journey-review`— spawnea `closer` (un solo Agent call) con el `TASK_ID`, `CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md` y el recordatorio literal `MODO DAG ACTIVO: production = explicit_dag; cierra sólo el TASK_ID explícito y su CLAUDE_TASK_PACK`. Espera el trailer `OUTCOME: committed` + `NEXT_STATUS: done` + `PUSH_READY: yes`. Si vuelve `blocked`, reporta qué le falta al usuario.
- Si "no" → informa al usuario:
  > *"Slice verificada pero sin commit. La sección `## verify-slice` con `VERIFY_OUTCOME: verified` ya está en el handoff (más `## verify-journey` si fue inline) — cuando quieras cerrar, relanza `/verify-slice` o dime `cierra <TASK_ID>` directamente."*

  Si el usuario responde inmediatamente "cierra" / "close" / "commit" → spawnea closer como en la rama "sí" sin volver a preguntar, manteniendo el mismo `TASK_ID` y `CLAUDE_TASK_PACK` DAG.

### 6.1.bis — Housekeeping post-closer (automático, silencioso)

Tras `closer` cierre con `OUTCOME: committed` y `PUSH_READY: yes`:

```bash
bash scripts/slice-clean.sh --apply 2>&1 | tail -20
bash scripts/cleanup-worktrees.sh --apply --task <TASK_ID> 2>&1 | tail -40
```

Operación segura: `slice-clean` rota ledger y borra caches regenerables; `cleanup-worktrees` elimina solo worktrees limpios asociados al TASK_ID y jamás toca `main`. Si falla → log y sigue; si dejó worktrees dirty, repórtalos como follow-up.

Reporta una línea al usuario: `🧹 Housekeeping: <resumen del script>`.

Si el SessionStart hook detectó presión de tamaño (sugerencia 💡 sobre PROGRESS.md grande, MEMORY.md de algún agente >200 líneas, etc.), repítela ahora junto al recordatorio: `/clear` + `/next-slice` (o `/slice-maintain compact` antes si la sugerencia lo aconseja).

### 6.2 — Si `VERIFY_OUTCOME: issues_found`

**NO invoques closer.** El código NO se committea sin verificar — ésta es la razón de existir de este paso. Presenta al usuario:

```
❌ Verify encontró problemas en <TASK_ID>. NO se ha commiteado nada (por diseño).
Hallazgos:
<bullets de findings, incluidos `Screen/Journey review` si fue el reviewer quien bloqueó>

¿Invoco a `debugger` para que los arregle? (sí/no)
Si dices "sí", al volver re-lanzaré `validator ‖ tester` y si pasan, relanzaré `/verify-slice`.
```

- Clasifica cada hallazgo antes de actuar:
  - **Menor y dentro del TASK_ID/Write set**: bug reparable sin cambiar contratos source-of-truth, sin añadir endpoint/ruta/tabla nueva, sin ampliar journey ni tocar conflicto compartido no declarado. Debes spawnear `debugger`, luego `validator ‖ tester`, y si ambos pasan relanzar este mismo `/verify-slice <TASK_ID>` hasta que el resultado sea `verified` o quede bloqueado con razón explícita.
  - **Mayor o fuera de scope**: falta ruta/endpoint/tabla/journey, cambia contrato front→back→DB, requiere datos reales/proporcionados nuevos, amplía `Write set`/`Conflict group` o afecta otro TASK_ID. No lo arregles como parche invisible: crea propuesta formal con `./scripts/register-followup-task.sh propose --origin-task <TASK_ID> --severity high|medium|low --kind bug|ux|wiring|data|test --scope-classification out_of_scope|missing_coverage|missing_real_data|scope_expansion --why-not-debugger "<por qué debugger/retest no basta>" --title "..." --description "..." --acceptance "..." --verify "..."`.
- Si "sí" y todos los hallazgos son menores → spawnea `debugger` con TASK_ID + findings + `CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md` + recordatorio `MODO DAG ACTIVO: production = explicit_dag`. Al volver → `validator ‖ tester` en paralelo. Si pasan → relanza este mismo comando con hard reset completo. No invoques `closer` hasta un verify posterior `verified`.
- Si hay al menos un hallazgo mayor/fuera de scope → registra follow-up formal con `--scope-classification` y `--why-not-debugger` antes de continuar. Si es `high|critical|blocker`, el closer y la siguiente wave quedarán bloqueados hasta promoverlo o hacer waiver humano. Si el hallazgo cabe en debugger/retest, no crees FU.
- Si "no" → informa y espera instrucciones (puede querer parchear a mano, revertir, marcar blocked, etc), pero no dejes la slice como cerrada.

---

## Trailer final (obligatorio)

```
CLAUDE_TRAILER:
TASK_ID: <ID>
VERIFY_OUTCOME: verified|issues_found
MODE: pre-closer|post-closer
CLOSER_INVOKED: yes|no|n/a
DATA_CONTRACT_ROWS: <filas/flows usados o "n/a">
PERSISTED_DATA_OBSERVED: <tabla/id/estado o "n/a">
JOURNEY_INLINE_VERIFIED: <lista JIDs o "none">
JOURNEY_PENDING: <lista JIDs o "none">
EVIDENCE: orchestrator-state/tasks/evidence/<TASK_ID>/verify-*
```

> `JOURNEY_INLINE_VERIFIED` y `JOURNEY_PENDING` aquí son informativos para el comando. El `closer` debe traducirlo a líneas `JOURNEY_VERIFIED_INLINE: <JID>`; el SubagentStop hook las consume y marca el journey `verified` bajo lock.

