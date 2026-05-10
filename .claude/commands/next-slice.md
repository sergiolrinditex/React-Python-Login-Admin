---
description: Arranca la siguiente slice. Lee PROGRESS.md + registry, levanta entorno con dev-restart --soft (sin reiniciar lo sano), propone plan para TU aprobación ANTES de tocar nada, y ejecuta el pipeline de 20 spawns máximo con paralelismo (validator ‖ tester). Verifica FRONT → BACK → DB.
argument-hint: "[hint opcional: 'continuar con P02-S02-1.3', 'siguiente slice'; sin argumento = la siguiente según registry/PROGRESS]"
---

# /next-slice
## Rule loading

Antes de ejecutar este comando, considera cargadas las reglas no-scoped de `.claude/rules/`. Si no ves esas reglas en contexto tras `/clear`, léelas explícitamente en este orden: `00-source-of-truth.md`, `01-non-negotiables.md`, `02-phase-execution.md`, `03-dev-loop.md`, `04-traceability.md`, `05-runtime-write-contract.md`.

Eres el **main-orchestrator**. Este comando arranca la siguiente slice del Step activo del checklist.

## Production DAG mode — recordatorio obligatorio

Antes de elegir task, reclamarla, spawnear agentes o presentar plan, repite internamente este invariante y hazlo visible en el plan del Paso 4:

```text
MODO DAG ACTIVO: production = explicit_dag.
Unidad ejecutable = TASK_ID canónico del registry.
No existe modo secuencial improvisado.
No inventes slices efímeras.
No uses active_task singleton para bloquear workers paralelos si existe CLAUDE_ACTIVE_TASK_ID.
Cada subagente recibe TASK_ID + CLAUDE_TASK_PACK + allowed_paths/write_set.
```

Si en cualquier momento dudas si estás en DAG o legacy, para y ejecuta/consulta `./scripts/check-task-dag.sh --strict`. En producción `legacy_linear` es error operativo, no fallback.

**Comandos hermanos**: `/verify-slice` (gate humano + orquesta `closer`), `/revise-slice <TASK_ID>` (corrección) y `/slice-maintain clean|compact` (limpieza + compactación). Orden recomendado al cerrar una slice: `/next-slice` pausa en tester pass → (opcional `/clear`) → `/verify-slice` (spawnea `closer` si verificado) → `/slice-maintain clean` → `/clear` → `/next-slice`.

**Gate adicional — DAG-only producción**: antes de reclamar una task, valida que `registry.json -> task_dag.mode` sea `explicit_dag`. Si sale `legacy_linear`, PARA: faltan `Depends on` reales en el Coverage Registry o el bootstrap no derivó DAG. No continúes en modo secuencial improvisado; corrige source-of-truth y reejecuta `python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh`.

**Gate adicional — follow-ups productivos**: antes de reclamar una task, revisa `runtime-state.open_followups`. Si hay propuestas `high|critical|blocker` en estado `proposed`, no sigas: primero comprueba que no sean defectos in-scope que deberían ir por `debugger/retest`; después usa `/promote-followup <ID>` para convertirlas en task DAG real o `/register-followup waive <ID>` con decisión humana. No permitas que un hallazgo de validator/tester quede solo en handoff, pero tampoco conviertas bugs reparables de la slice en FU. Las FU reales deben traer `--scope-classification` y `--why-not-debugger`.

**Gate adicional — journey verification**: si al cerrar esta slice todos los demás slices de un journey ya están `done`, **`/verify-slice` integrará el gate de journey** en su §5.bis: ofrecerá al usuario verificar el journey inline (mismo entorno, mismos datos cargados, un solo gate humano) o dejarlo "aparte" para `/verify-journey <JID>` después. La detección se hace con `list_journey_closures.py`, no con `task_ids[-1]`, para soportar DAGs y matrices desordenadas. Si elige aparte, el closer emitirá `JOURNEY_PENDING_VERIFY` y el próximo `/next-slice` quedará bloqueado por el planner hasta que se resuelva.

**Este comando NO invoca `closer`.** El pipeline de `/next-slice` termina en `tester pass`. El cierre (closer) es responsabilidad de `/verify-slice`, que actúa como gate humano previo al commit.

**REGLA DE ORO**: NO toques código, NO lances workers, NO mutes registry hasta que el usuario apruebe el plan en el **Paso 4**. Solo permitido antes: leer ficheros, listar estado del entorno, levantar dev-restart en modo `--soft`, y presentar el plan.

---

## Paso 0 — Contexto limpio

Cada slice se arranca con contexto limpio (lo obliga CLAUDE.md). Un pipeline de slice consume 50–80k tokens; dos slices sin `/clear` revientan el prompt cache.

- Si acabas de cerrar otra slice en esta sesión (has visto pasar `closer` hace poco) → PARA. Dile al usuario: *"He detectado que ya cerramos una slice. Ejecuta `/clear` y relanza `/next-slice`. PROGRESS.md tiene el estado."*
- Si vienes de `/clear` o la sesión empieza en limpio → continúa al Paso 1.

---

## Paso 1 — Reconstruir contexto (barato)

Lee en paralelo (máximo 10 ficheros — si necesitas más, replantea):

1. `orchestrator-state/memory/PROGRESS.md` (cabecera + últimas 3 slices).
2. `orchestrator-state/tasks/registry.json` (solo `active_task`, `active_phase`, últimas 3 `done`, primeras 5 `ready`/`pending`).
3. `orchestrator-state/tasks/runtime-state.json` (último worker, último evento — para detectar pipeline a medio).
4. `.claude/CLAUDE.md` + `.claude/rules/01-non-negotiables.md` (relee los non-negotiables).
5. Títulos de los documentos source-of-truth fuente (primeras 60 líneas de `instrucciones.md`, TOC del guide, la sección de la fase activa del checklist).
6. Último handoff `orchestrator-state/tasks/handoffs/{TASK_ID_ACTIVE_OR_LAST}.md` si existe.
7. Si hay `CLAUDE_ACTIVE_TASK_ID`, evalúa SOLO ese `TASK_ID`: el singleton `active_task` puede pertenecer a otra terminal DAG. Si NO hay override DAG y existe un `active_task` no `done`, hay pipeline a medio secuencial: termina esa antes de arrancar otra. Si hay varias tasks activas en explicit DAG, no bloquees por el singleton; sugiere `/next-wave` y continúa solo con el `TASK_ID` de este terminal.

Prohibido:

- Releer los documentos source-of-truth fuente completos (solo cuando `planner` los extrae por secciones).
- Lanzar subagentes.
- Escribir/mutar ficheros.

---

## Paso 2 — Entorno dev SIN reiniciar

Ejecuta una sola vez `scripts/dev-restart.sh --soft`.

> **Nota**: el framework provee un dispatcher genérico `scripts/dev-restart.sh` con el contrato `--soft` (levanta solo lo caído), `--check` (reporta estado, no toca nada) y `--reset` (drop DB + migrate + carga datos reales/proporcionados + reinicia todo). El dispatcher es agnóstico del stack: delega los comandos concretos (start back, start front, db reset, carga de datos reales/proporcionados, health probes) en `scripts/dev-restart.profile.sh`. La versión que viene en el template implementa Flutter + FastAPI + Supabase y lee puertos de `.env` con fallbacks (BACKEND_PORT=8000, FRONTEND_PORT=5000). Cuando un feature-app necesita otro stack, **sustituye solo el profile** — el dispatcher y el contrato `--soft|--check|--reset` se mantienen intactos. Si el profile falta, el dispatcher aborta con error claro.

- Si todo está sano → el script sale en 1s (auto-soft exit).
- Si algo está caído → levanta SOLO lo que falta.

**Nunca uses `--reset`** salvo que el usuario lo pida explícitamente.

Verifica después (puertos en TECHNICAL_GUIDE):

- `curl -sf http://localhost:<BACKEND_PORT>/health` → 200.
- `curl -sf http://localhost:<AUX_RUNTIME_PORT>/health` → 200 (si existe runtime auxiliar tipo AI/worker).
- `curl -sI http://localhost:<FRONTEND_PORT>/` → 200 o 304.

Si algo sigue DOWN tras el soft → muestra la tabla de estado, añádelo como riesgo al plan del Paso 4 y **no avances** a ejecutar slice con entorno roto.

Si el soft levantó algo, lee últimas 30 líneas de los logs relevantes (back, front, runtimes auxiliares). Sin spam de logs si no fue necesario.

---

## Paso 3 — Identificar la siguiente slice

Prioridad (aplicar en orden, parar en la primera match):

1. `$ARGUMENTS` con ID concreto o referencia textual → respétalo.
2. `active_task` no terminada → continuar esa.
3. Sin `active_task` → invoca `planner` para elegir una cola `ready` con dependencias satisfechas y preparar `task-packs/<TASK_ID>.md`. `planner` no debe editar `registry.json` ni `runtime-state.json` con Write/Edit; el claim y los cambios de estado los hacen `claim_task.py` y los hooks bajo lock. **Pero no debe arrancar otros workers desde aquí** — su rol es solo "seleccionar + preparar pack". Contrasta con PROGRESS.md: si hay discrepancia registry ↔ PROGRESS, **PROGRESS + código real ganan para diagnosticar**, y cualquier reparación de registry debe ser explícita/lockeada.
4. Si la slice huele grande (≥3 endpoints, ≥4 ficheros de front, ≥2 features, o ≥10 criterios de aceptación) → **NO la dividas en vivo**. Para. Reporta que el `Coverage Registry` está demasiado grueso y propone al usuario actualizar el source-of-truth pack para crear `Slice ID` canónicos más pequeños. El orquestador no inventa slices efímeros porque romperían registry, handoffs, memory y journey matrix.

Regla KISS:

- La unidad ejecutable es siempre el `TASK_ID` generado por bootstrap desde el Coverage Registry.
- Si una unidad no cabe en el pipeline de 20 spawns, el bug está en la granularidad documental, no en el runtime.
- Ejemplo correcto: `POST /auth/register`, `POST /auth/login`, `LoginPage`, `0005_profiles.py`.
- Ejemplo incorrecto: `Auth completa`, `Todo el motor`, `Todas las pantallas`.

---

## Paso 4 — PROPUESTA — gate de aprobación OBLIGATORIO

Presenta al usuario:

```
# Plan para la siguiente slice

## Estado actual (PROGRESS.md + registry)
- Fase activa: <ID> (<nombre>)
- Última slice cerrada: <ID> — <una línea>
- Active task en registry: <ID o "none"> (estado: <status>)
- Entorno: back=<UP/DOWN> · aux=<UP/DOWN si aplica> · front=<UP/DOWN> · contenedores=<UP/DOWN>

## Siguiente slice propuesta
- ID: <TASK_ID>
- Título: <texto del checklist>
- Objetivo en 1 línea (qué ve el usuario al final): <...>
- Checklist origen: §<sección>

## Granularidad
- Esta es una slice canónica del Coverage Registry. No se crearán slices temporales.
- Si parece demasiado grande, se detendrá el flujo y se pedirá corregir los docs source-of-truth.

## Invariante DAG de esta ejecución
- MODO DAG ACTIVO: `registry.json -> task_dag.mode` debe ser `explicit_dag`.
- TASK_ID canónico: `<TASK_ID>`; no se crearán slices temporales ni se seguirá un orden secuencial improvisado.
- Cada Agent spawn debe recibir `TASK_ID`, `CLAUDE_TASK_PACK`, `allowed_paths`/`Write set` y el aviso `production DAG mode`.

## Pipeline por slice (/next-slice pausa en tester pass — closer NO se invoca aquí)
1. planner (pack + extracto 5 docs + PROGRESS + impact analysis)
2. developer ‖ official-docs-researcher  [UN MENSAJE CON 2 Agent calls — paralelismo crítico]
                              developer: DB → back → front; logs BEFORE/AFTER; PROGRESS.md; handoff
                              official-docs-researcher: SIEMPRE (shallow/deep según MEMORY cache);
                              red de seguridad para cazar patrones o cambios recientes del ecosistema
3. validator ‖ tester          [UN MENSAJE CON 2 Agent calls — paralelismo crítico]
4. debugger                    [solo si tester falla → volver a paso 3; máx 3 ciclos]
   ── /next-slice termina aquí y pide al usuario que lance /verify-slice ──
5. /verify-slice (gate humano) — tú o el usuario lo arrancáis. Spawnea closer si VERIFIED.
6. closer (evidence report + commit atómico y workflow Git configurado + `configured Git workflow (`./scripts/git-workflow.sh`)` + limpieza segura de worktrees) — lo orquesta /verify-slice, no este comando.

## Ficheros/áreas (predicción)
- Back: <módulos/rutas>
- Front: <features/pantallas>
- DB: <migraciones/tablas>
- Tests: <unit/componente/integration/e2e>

## Riesgos y decisiones abiertas
- <riesgo 1>: <mitigación>
- <decisión pendiente>: <opciones>

## Verificación FRONT → BACK → DB (al final de cada slice)
- FRONT: lint + tests + ruta visual: <ruta>
- BACK: endpoint curl-able: <método path> + logs del back
- DB: fila/row inspeccionable + migración aplicada + logs de query

## ¿Procedo?
Responde **sí / adelante / go** para arrancar esta slice.
Si quieres cambiar alcance, dímelo ahora.
```

**NO avances al Paso 5 sin "sí" / "adelante" / "go" / "ok" / "proceed" / "dale" explícito.**

Si dice "no" o pide cambios → re-haz Paso 4 con sus ajustes.

---

## Paso 5 — Ejecutar el pipeline de la slice

Ejecuta exactamente el `TASK_ID` aprobado en el Paso 4. No crees slices temporales.

> **RECORDATORIO DAG PARA ESTA EJECUCIÓN**: seguimos en `explicit_dag`. El `TASK_ID` aprobado es el único nodo ejecutable de este terminal. No infieras trabajo desde un orden secuencial, no uses otro `active_task` y no spawnees agentes sin repetirles `MODO DAG ACTIVO` + `TASK_ID` + `CLAUDE_TASK_PACK`.

### 5.1 — Pre-check

### DAG worker claim

Si `$ARGUMENTS` contiene un `TASK_ID` concreto o el entorno tiene `CLAUDE_ACTIVE_TASK_ID`, esta ejecución es un worker DAG para ese nodo. Después de la aprobación del Paso 4 y antes de spawnear agentes:

```bash
export CLAUDE_ACTIVE_TASK_ID=<TASK_ID>
python3 -B -S .claude/bin/claim_task.py <TASK_ID>
export CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md
```

Si `claim_task.py` devuelve `CLAIM_DENIED`, no ejecutes la slice: informa la causa (deps incompletas, ya claimed o conflicto activo por `Conflict group`/`Write set`) y vuelve al planner. `/next-wave` solo imprime el `export` y el `/next-slice`; el claim atómico ocurre aquí, una sola vez, después de la aprobación humana. En modo secuencial sin `TASK_ID` explícito, no hace falta claim manual. El claim crea un pack mínimo por task; el `planner` debe enriquecer `CLAUDE_TASK_PACK` con los extractos de los documentos source-of-truth antes de arrancar `developer`.

- Relee PROGRESS.md (cabecera + últimas 3 slices).
- Confirma entorno sano (`--check` del script de dev-restart).

### 5.2 — Invoca los agentes con paralelismo explícito

Cada `Agent` call debe incluir `TASK_ID`, `TASK_PACK`, handoff previo si existe, y esperar el trailer machine-readable (`TASK_ID` / `OUTCOME` / `NEXT_STATUS` / `HANDOFF`). En modo DAG, `TASK_PACK` **no** es el singleton `orchestrator-state/memory/active-task.md`: usa siempre `orchestrator-state/tasks/task-packs/<TASK_ID>.md` para que dos terminales no se pisen.

**Cadena (este comando pausa en tester pass; closer NO se invoca desde aquí):**

1. **`planner`** [BLOQUEANTE]. Espera `CONTEXT_READY: yes` con 5 fuentes extraídas + `IMPACT_READY: yes` + `TASK_PACK: orchestrator-state/tasks/task-packs/<TASK_ID>.md` en DAG. Si `no` → para y resuelve.
2. **`developer` ‖ `official-docs-researcher`** [OBLIGATORIOS, PARALELO]. **Un solo mensaje con dos Agent calls** e incluye literalmente `TASK_ID=<TASK_ID>` y `TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md` en ambos prompts:
   - `developer`: DB → back → front. Logs BEFORE/AFTER. Actualiza PROGRESS.md. Escribe handoff. FRONT → BACK → DB: revisa los ficheros de log declarados en TECHNICAL_GUIDE.
   - `official-docs-researcher`: SIEMPRE, aunque `planner` no marque `NEEDS_OFFICIAL_DOCS: yes`. Con su cache agresivo el shallow pass cuesta ≤5s. Si detecta discrepancia con docs internos → PARA al developer (aunque ya haya avanzado), anota en `orchestrator-state/memory/official-doc-notes/`, reconcilia los documentos source-of-truth fuente, y reinicia el paso 2.
3. **`validator` ‖ `tester`** [OBLIGATORIO, PARALELO]. Un solo mensaje con dos Agent calls e incluye el mismo `TASK_ID` + `TASK_PACK` para ambos:
   - `validator`: arquitectura, scope, DRY/KISS/YAGNI, file size, docstrings, logs, tests realness (sin ejecutar), PROGRESS.md, security checklist (si diff toca auth/secrets/CORS/SQL/permisos/headers/rate-limit/infra).
   - `tester`: tests reales con back+DB up, curl a endpoints nuevos, logs en ambos modos de `ENABLE_VERBOSE_LOGGING`, evidencia en `orchestrator-state/tasks/evidence/<TASK_ID>/`.
4. **`debugger`** [SOLO si tester falla — máximo 3 ciclos]. Corrige con fix real (no mocks). Volver al paso 3. **Si el tester falla tras 3 intentos → PARA, reporta al usuario, marca la tarea `blocked` en registry.**

── Fin del pipeline automático de `/next-slice`. A partir de aquí: gate humano. ──

5. **Menú de cierre — pregunta OBLIGATORIA al usuario** (presenta la checklist de validación de la plantilla de abajo y luego este menú):

```
Tests verdes en <TASK_ID>. ¿Cómo cerramos?

haz clear   — RECOMENDADO. Haces /clear para liberar el contexto del pipeline
              (~100-200k tokens), y luego /verify-slice. Verify recupera todo
              desde disco (handoff, PROGRESS, TECHNICAL_GUIDE), hace hard reset
              del entorno, reproduce como usuario, y si sale verified orquesta
              closer automáticamente.

haz closer  — Closer directo SIN verify-slice. Requiere waiver explícito
              (`VERIFY_WAIVED: <motivo>`) en el handoff. Úsalo solo para slices
              sin UI o cuando ya has verificado manualmente. Commit atómico,
              push a origin/main.

espera      — No cierro nada. Dejo la slice en pausa. Para retomar: /verify-slice
              o dime "cierra <TASK_ID>" directamente.
```

Interpreta la respuesta:

- **"haz clear"** / "clear" / "verify" / "a" → informa al usuario del flujo recomendado: *"Haz `/clear` y después `/verify-slice`. Verify-slice leerá de disco todo lo necesario (handoff, PROGRESS, runtime-state, TECHNICAL_GUIDE) y orquestará el closer si queda verificada."* Sal del comando. **NO invoques verify-slice tú mismo** — es el usuario quien lo lanza como slash command tras el `/clear`.
- **"haz closer"** / "closer" / "cierra" / "b" → pide confirmación explícita del waiver: *"¿Qué motivo pongo en `VERIFY_WAIVED`? (ej: 'slice backend sin UI', 'verificado manualmente fuera de la herramienta')"*. Escribe el motivo + timestamp + sección `## verify-slice` con `VERIFY_WAIVED: <motivo>` en el handoff. Spawnea `closer` (un solo Agent call). Espera `OUTCOME: committed`.
- **"espera"** / "wait" / "c" → informa al usuario: *"Slice en pausa. Para retomar: `/verify-slice` o dime `cierra <TASK_ID>`."* Sal del comando sin escribir nada extra al state.

**Este comando NO invoca closer salvo por la rama "haz closer" con waiver explícito.** La ruta normal es siempre "haz clear" → `/verify-slice`.

### 5.3 — Después de la slice

- Verifica que PROGRESS.md quedó actualizado por el developer; si no, completa tú.
- Sugiere `/slice-maintain clean` si hay backlog de slices cerradas.
- Si el contexto conversacional ya superó ~50k tokens → sugiere `/clear` antes de seguir (PROGRESS.md reconstruirá estado).
- Para continuar con la siguiente unidad canónica, el usuario lanzará `/next-slice` otra vez.

Si el usuario eligió (c) en el menú del Paso 5 → no hay "después"; sal del comando y deja la slice en pausa.

---

## Plantilla — Checklist de validación de usuario (paso de verificación visual)

Al acabar cada slice:

```
# ✅ Slice <ID> lista — valida por favor

## Cómo verificar (según TECHNICAL_GUIDE)
<Método: URL en navegador · emulador · simulador · dispositivo — según lo definido en TECHNICAL_GUIDE>
Referencia: <ruta / pantalla / deep link / equivalente>

## Flujo paso a paso
1. <click / input / navegación>
2. <qué debería verse>
3. <qué dato/estado debería cambiar>

## Verificaciones FRONT
- [ ] Se ve profesional (colores, spacing, tipografía del design system)
- [ ] Loading states presentes
- [ ] Errores elegantes

## Verificaciones BACK
- [ ] Endpoint: <método path> responde 200 con payload esperado
- [ ] Logs back muestran BEFORE/AFTER de la operación
- [ ] Sin PII en logs

## Verificaciones DB
- [ ] Fila/row creada o actualizada (query: <ejemplo>)
- [ ] Migración aplicada si aplica

## Reglas de negocio a verificar
- <regla 1 de instrucciones.md>
- <regla 2>

## Casos de error
- <caso 1: submit vacío → validación>
- <caso 2: payload inválido → 400>

Cuando termines de mirar, te presento el menú de cierre (a /verify-slice, b cierra con waiver, c espera).
```
