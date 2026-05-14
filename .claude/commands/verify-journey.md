---
description: Gate humano end-to-end por journey (no por slice). Se lanza cuando todos los slices de un journey están cerrados y antes de arrancar la siguiente unidad bloqueada. Hard reset + datos reales/proporcionados globales del journey + reproducción del flujo completo como usuario real (multi-pantalla). Resiliente a /clear.
argument-hint: "<JOURNEY_ID>  (ej: J101). Sin argumento = lee runtime-state.pending_journey_verifications[0]"
---
### Root split obligatorio

- Lee `registry.json`, `runtime-state.json`, `PROGRESS.md`, `task-dag.*` desde `$CLAUDE_ORCHESTRATOR_ROOT/orchestrator-state/`.
- Lee/escribe handoff, evidence, report y task-pack desde la worktree activa (`./orchestrator-state/tasks/...`) cuando la slice corre en worktree.
- No registres follow-ups por errores mecánicos del orquestador (root stale, heading de handoff, checker/lint flake, cleanup omitido). Corrige, reintenta o bloquea; FU solo para trabajo de producto fuera de scope.


# /verify-journey
## Rule loading

Antes de ejecutar este comando, considera cargadas las reglas no-scoped de `.claude/rules/`. Si no ves esas reglas en contexto tras `/clear`, léelas explícitamente en este orden: `00-source-of-truth.md`, `01-non-negotiables.md`, `02-phase-execution.md`, `03-dev-loop.md`, `04-traceability.md`, `05-runtime-write-contract.md`.

Gate humano **a nivel journey**, complementario a `/verify-slice`. Mientras `/verify-slice` valida UNA slice (atómica) en su contexto técnico, `/verify-journey` valida el **flujo completo del usuario** que cruza varias slices ya cerradas (login → dashboard → upload → resultado, por ejemplo).

**Cuándo se lanza**: cuando todos los slices de un journey (definido en la Journey Coverage Matrix de `instrucciones.md`) están `done` y el usuario eligió verificarlo aparte. El `closer` emite trailer `JOURNEY_PENDING_VERIFY: JXXX` y el SubagentStop hook lo añade a `runtime-state.pending_journey_verifications[]`. En DAG-only, sólo se difieren las siguientes slices que referencian ese `JID`; ramas independientes pueden seguir.

**Resiliente a `/clear`**: igual que `/verify-slice`. Reconstruye contexto desde disco (registry.json, runtime-state.json, journey-handoffs/, TECHNICAL_GUIDE).

**Comandos hermanos**: `/verify-slice`, `/next-slice`, `/slice-maintain`. Orden recomendado al cerrar la ÚLTIMA slice de un journey: tester pass → `/verify-slice` → `closer` → `/clear` → `/verify-journey JXXX` → `/slice-maintain clean` → `/next-slice` (siguiente journey).

**Principios** (idénticos a `/verify-slice` pero a escala journey):

- **Hard reset SIEMPRE.** Stop services, drop+create DB, carga datos base reales/proporcionados, carga datos globales reales/proporcionados del journey (cuenta de usuario con sesión válida, datos previos consistentes), reinicia back+front con verbose ON.
- **Reproduce el flujo COMPLETO como humano.** No por slice individual — el journey entero, en orden, sin saltarte pasos.
- **Vigila los 3 logs en vivo durante toda la reproducción.**
- **Estados marginales obligatorios** (no solo el happy path):
  - empty state al entrar antes de tener datos
  - error states (network down, validation, payload inválido)
  - permission denied si el journey toca recursos protegidos
  - back behavior natural (volver atrás funciona, no rompe estado)
  - deep link directo a una pantalla intermedia del journey
- **Verifica el "Next action"**: después de completar el journey, ¿el sistema sugiere correctamente lo siguiente que el usuario haría?

---

## Paso 1 — Identificar el journey a verificar

Lee en paralelo:

1. `$ARGUMENTS` con `JOURNEY_ID`. Si vacío → `orchestrator-state/tasks/runtime-state.json` → `pending_journey_verifications[0]`.
2. Si no hay pending y no hay arg → aborta: *"No hay journeys pendientes de verificar. Si quieres re-verificar uno ya cerrado: `/verify-journey JXXX --post`."*
3. `orchestrator-state/tasks/registry.json` → `journeys[]` busca por ID. Lee `task_ids[]`, `milestone`, `title`, `verification_status`.
4. `orchestrator-state/memory/PROGRESS.md` (cabecera + últimas slices del milestone).
5. Journey Coverage Matrix de `instrucciones.md` (§3.5 en baseline snapshot, §3.7 en feature-app) → fila del journey: pantallas (en orden), acciones, endpoints, tablas, estado cliente, slices.
6. `*_TECHNICAL_GUIDE.md`:
   - §6.1 (rutas) para las pantallas del journey
   - §6.2 (endpoints) para los endpoints del journey
   - §10.3 (DB schema) para las tablas del journey
   - §6.4 (Navigation Contract) para empty/error/permission states
   - §3 (comandos: arranque back, front, migrate, carga de datos, health)
   - §Verification Data Contract para persona/rol, datos reales/proporcionados, datos proporcionados permitidos y reset/cleanup del journey
7. Handoffs de cada slice: `orchestrator-state/tasks/handoffs/{TASK_ID}.md` para cada `task_ids[i]` del journey — busca DATA_SETUP (o DATA_SETUP alias) y FLOWS_TESTED de cada slice individual.

Si alguna slice del journey NO está en estado `done` en registry → aborta: *"Journey JXXX no está completo (slice TASK_ID en estado X). Cierra todas sus slices con `/verify-slice` antes de verificar el journey."*

### 1.1 Detectar el modo

- **Modo `pre-next-slice`** (lo habitual): `pending_journey_verifications` contiene este JOURNEY_ID. Verify es el gate antes de arrancar la siguiente slice. Si verified → quita el journey de pending y permite continuar.
- **Modo `post`** (re-verify): journey ya verificado anteriormente, el usuario quiere re-correrlo (ej: tras un cambio en una slice posterior que toca pantallas compartidas). No mueve `pending_journey_verifications` — solo reporta outcome.

---

## Paso 2 — HARD RESET del entorno

Idéntico al §2 de `/verify-slice` pero con un cambio crítico en 2.4: **datos reales/proporcionados de TODAS las slices del journey**, no solo la última.

### 2.1 Stop servicios + 2.2 reset DB + 2.3 datos base reales/proporcionados
(idéntico a `/verify-slice §2.1-2.3`)

### 2.4 Datos reales/proporcionados consolidados del journey

Para cada slice del journey, lee la sección `## verify-slice` → `DATA_CONTRACT_ROWS`, `DATA_SETUP:` y `PERSISTED_DATA_OBSERVED` del handoff. Acumula todos los datos de verificación en orden cronológico de las slices y cruza contra el `Verification Data Contract` del TECHNICAL_GUIDE.

Reglas:

- Usa datos reales/proporcionados del contrato: personas/roles sandbox, relaciones persistidas, archivos representativos, estados coherentes.
- No cierres un journey productivo con mocks de negocio, lorem ipsum, datos demo-only o inserts hechos vía el endpoint bajo prueba.
- Los datos sintéticos solo valen para edge cases etiquetados (`empty`, `error_network`, `permission_denied`, payload inválido).
- Si algún dato de verificación entra en conflicto con otro (ej: dos slices crean la misma fila con valores distintos) → aborta y reporta: *"Conflicto de datos de verificación entre TASK_ID_A y TASK_ID_B en tabla X. Resuelve manualmente o lanza /verify-journey con --skip-data-setup-conflicts."*

Documenta en el reporte final qué filas del contrato de datos usaste, qué datos reales/proporcionados se aplicaron consolidados y qué datos persistidos observaste.

### 2.5 Arranca back+front (idéntico a `/verify-slice §2.5`)

---

## Paso 3 — Reproducción humana del journey COMPLETO

Abre el navegador en la URL del front. Reproduce el journey siguiendo EXACTAMENTE la secuencia de pantallas de la fila correspondiente de la Journey Coverage Matrix:

1. **Punto de entrada**: empieza en la pantalla `Entrada` de la matriz, con la sesión/estado descritos en la columna `Estado cliente`.
2. **Recorre las pantallas en orden**, ejecutando las `Acciones clave`:
   - En cada pantalla observa: render correcto, design system coherente, datos esperados, loading→success transitions.
   - Para cada acción: verifica logs front + logs back + queries DB en vivo.
   - Cada endpoint de la columna `Endpoints` debe dispararse en el momento esperado y solo entonces.
3. **Estados marginales** (obligatorios, uno cada uno):
   - Vuelve a la pantalla anterior con back system → estado se conserva.
   - Recarga la página intermedia → recupera estado coherente o redirige correctamente.
   - Provoca un empty state (limpia datos) → renderiza el empty correcto del §3.2 + CTA next action.
   - Provoca un error de red (corta backend o devuelve 500 con curl forzado) → error state correcto, no stack trace.
   - Si aplica permission denied: prueba con un user sin role admin → 403 page con CTA esperado.
   - Deep link: copia URL de pantalla intermedia, abre en pestaña nueva → si requiere auth, redirige a /login?next=URL; si no, abre directo.
4. **Next action**: tras completar el journey, ¿la pantalla final sugiere correctamente la siguiente acción (otro journey)? La matriz no lo dice; el §3.2 de instrucciones sí (campo "Next action recomendada").

Si tienes Chrome MCP o computer-use, automatiza + screenshots. Sin eso, describe + espera feedback humano.

---

## Paso 4 — Observación de logs (idéntico a `/verify-slice §4`)

Guarda snippets relevantes en `orchestrator-state/tasks/evidence/journeys/<JOURNEY_ID>/verify-*`.

---

## Paso 5 — Tabla final de validación del journey

Presenta al usuario:

```
# Journey <JOURNEY_ID> — <Title> (Milestone <Mn>) — Verificación

## Slices que componen el journey
| Slice | Estado | Handoff |
|-------|--------|---------|
| P03-S02-T001 | done | handoffs/P03-S02-T001.md |
| ... | ... | ... |

## Reproducción end-to-end
| # | Pantalla | Acción | Endpoint | Esperado | Observado | ✅/❌ |
|---|----------|--------|----------|----------|-----------|------|
| 1 | LoginPage | submit credenciales | POST /auth/login | redirect /, cookie httpOnly | ... | ✅ |
| 2 | Dashboard | tap Upload | (none) | navega /upload | ... | ✅ |
| 3 | {{PrimaryActionPage}} | submit file | {{primary_endpoint}} | 202 + redirect /result/:id | ... | ... |
| ... | ... | ... | ... | ... | ... | ... |

## Estados marginales
| Estado | Pantalla | Resultado | ✅/❌ |
|--------|----------|-----------|------|
| Back system | {{PrimaryActionPage}}→{{DashboardScreen}} | estado preservado | ✅ |
| Reload intermedio | /result/:id | recupera datos | ✅ |
| Empty state | Dashboard sin análisis | renderiza empty + CTA | ... |
| Error red | {{PrimaryActionPage}} con backend no disponible | banner rojo + retry | ... |
| Permission denied | (si aplica) | 403 page | ... |
| Deep link auth | /result/:id sin sesión | redirect /login?next=... | ... |

## Next action
- Esperada (de §3.2 features): "Sugerir export del análisis (J102)"
- Observada: <...>

## Data contract rows usados
- <fila/flow del Verification Data Contract>

## Fixtures consolidados aplicados
- <dato real/proporcionado 1>
- <dato real/proporcionado 2>

## Datos persistidos observados
- <tabla/id/estado observado>

## Hallazgos
<lista vacía si verified; bullets si issues>

## Recomendación
JOURNEY_VERIFY_OUTCOME: verified | issues_found
```

### 5.1 Escribir el journey-handoff (obligatorio)

Crea/sobreescribe `orchestrator-state/tasks/journey-handoffs/<JOURNEY_ID>.md`:

```markdown
# Journey <JOURNEY_ID> — Verification handoff

- TIMESTAMP: <ISO-8601>
- MODE: pre-next-slice | post
- JOURNEY_VERIFY_OUTCOME: verified | issues_found
- MILESTONE: <Mn>
- SLICES_COVERED: <lista TASK_IDs>
- DATA_CONTRACT_ROWS: <filas/flows del Verification Data Contract usadas>
- DATA_SETUP_CONSOLIDATED: <lista>
- PERSISTED_DATA_OBSERVED: <tabla/id/estado o n/a con razón>
- FLOWS_TESTED: <lista>
- MARGINAL_STATES_TESTED: back, reload, empty, error_network, permission_denied, deep_link
- NEXT_ACTION_VERIFIED: yes | no | n/a
- FINDINGS: <bullets si issues_found>
- EVIDENCE: orchestrator-state/tasks/evidence/journeys/<JOURNEY_ID>/verify-*
```

---

## Paso 6 — Mutación de estado y orquestación

### 6.1 Si `JOURNEY_VERIFY_OUTCOME: verified`

No edites `registry.json` ni `runtime-state.json` con Write/Edit. Ejecuta el helper lockeado:

```bash
./scripts/update-journey-verification.sh <JOURNEY_ID> --outcome verified
```

El helper quita `<JOURNEY_ID>` de `pending_journey_verifications[]`, marca `registry.journeys[].verification_status=verified` y mantiene el orden de locks registry → runtime-state.

Reporta al usuario:

```
✅ Journey <JOURNEY_ID> verificada.
Estado actualizado: pending_journey_verifications quitado, registry.journeys actualizado.
Puedes lanzar `/next-slice` para arrancar la siguiente slice del siguiente journey.
```

### 6.2 Si `JOURNEY_VERIFY_OUTCOME: issues_found`

NO quites el journey de pending. Pregunta al usuario:

```
❌ Journey <JOURNEY_ID> tiene issues. NO se ha desbloqueado /next-slice.
Hallazgos:
<bullets>

¿Cómo procedemos?
a) Spawn `debugger` con scope=journey (puede tocar cualquier slice del journey y debe re-correr /verify-slice de las afectadas + /verify-journey al final).
b) Mantener pending y volver luego con más contexto.
c) Waiver explícito: JOURNEY_VERIFY_WAIVED: <motivo> (NO recomendado salvo casos extremos).
```

- "a" → spawn debugger con TASK_IDS del journey + findings. Al terminar → `/verify-slice` de las slices que tocó → si pasan, relanza `/verify-journey JXXX`.
- "b" → sale del comando sin tocar estado. El planner seguirá bloqueando `/next-slice`.
- "c" → pide motivo explícito. Escribe `JOURNEY_VERIFY_WAIVED: <motivo>` en el journey-handoff y ejecuta `./scripts/update-journey-verification.sh <JOURNEY_ID> --outcome waived --reason "<motivo>"`. No edites registry/runtime a mano.

---

## Trailer final (obligatorio)

```
JOURNEY_ID: <JID>
JOURNEY_VERIFY_OUTCOME: verified | issues_found
MODE: pre-next-slice | post
NEXT_ACTION_VERIFIED: yes | no | n/a
EVIDENCE: orchestrator-state/tasks/evidence/journeys/<JID>/verify-*
HANDOFF: orchestrator-state/tasks/journey-handoffs/<JID>.md
JOURNEY_VERIFY_WAIVED: <motivo>   # SOLO si rama 6.2c — omite la línea entera en cualquier otro caso
```

El SubagentStop hook captura este trailer y muta runtime-state + registry automáticamente:

- `JOURNEY_VERIFY_OUTCOME: verified` → quita `<JID>` de `pending_journey_verifications`, marca `registry.journeys[<JID>].verification_status = verified`.
- `JOURNEY_VERIFY_WAIVED: <motivo>` (con `JOURNEY_ID` presente) → quita `<JID>` de `pending_journey_verifications`, marca `verification_status = waived`, guarda `waiver_reason`.
- `JOURNEY_VERIFY_OUTCOME: issues_found` → no muta nada (debugger debe arreglar; el journey sigue en pending).

> **Importante**: aunque el comando ya muta el estado a mano en las ramas 6.1 / 6.2c, **emite siempre el trailer**. El hook es idempotente (las funciones `remove_pending_journey_verification` y `waive_journey_verification` no fallan si el JID ya no está en pending). Belt-and-suspenders: si el LLM olvida una de las dos vías, la otra cubre. Si no estás en rama 6.1 ni 6.2c, omite la línea `JOURNEY_VERIFY_WAIVED` por completo (no escribas `JOURNEY_VERIFY_WAIVED: n/a` ni similar — el regex matchearía).
