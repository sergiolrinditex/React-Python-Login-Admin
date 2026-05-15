---
description: Verificación humana-real post-slice en modo DAG. Hard reset, navegador MCP, datos reales/proporcionados, logs front/back/DB, tabla de validación, y cierre automático vía closer si queda verified.
argument-hint: "<TASK_ID>|--task <TASK_ID>  (o terminal con CLAUDE_ACTIVE_TASK_ID exportado)"
---

# /verify-slice

## Rule loading

Antes de ejecutar este comando, considera cargadas las reglas no-scoped de `.claude/rules/`. Si no ves esas reglas en contexto tras `/clear`, léelas explícitamente en este orden: `00-source-of-truth.md`, `01-non-negotiables.md`, `02-phase-execution.md`, `03-dev-loop.md`, `04-traceability.md`, `05-runtime-write-contract.md`.

## Production DAG mode — recordatorio obligatorio

MODO DAG ACTIVO: production = explicit_dag.

Unidad verificable = TASK_ID canónico del registry. No existe modo DAG-disabled improvisado. La ausencia de `Depends on` es error operativo, no fallback. Usa TASK_ID explícito por argumento o `CLAUDE_ACTIVE_TASK_ID`; si falta, para.

Todo Agent spawn desde verify-slice debe recibir TASK_ID, CLAUDE_TASK_PACK y el aviso production DAG mode. Usa exactamente `CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md`. Esto incluye `slice-verifier`, `screen-journey-reviewer`, `debugger`, `validator`, `tester` y `closer`.

Antes de verificar, confirma el checkout correcto:

```bash
./scripts/ensure-task-worktree.sh --check-current <TASK_ID>
```

En `pr-flow`, `/verify-slice` debe correr desde el worktree/rama del TASK_ID; en `push-to-main`, desde `main`. Si estás en otro checkout, PARA: no verifiques una rama distinta a la que implementó el developer.

## Root split obligatorio

- Lee `registry.json`, `runtime-state.json`, `PROGRESS.md`, `task-dag.*` desde `$CLAUDE_ORCHESTRATOR_ROOT/orchestrator-state/`.
- Lee/escribe handoff, evidence, report y task-pack desde la worktree activa (`./orchestrator-state/tasks/...`) cuando la slice corre en worktree.
- No registres follow-ups por errores mecánicos del orquestador: root stale, heading de handoff, checker/lint flake, cleanup omitido, PR abierta/queued o CI pendiente. Corrige, reintenta o bloquea; FU solo para trabajo real de producto fuera de scope.

## Flujo mecánico

```text
tester pass / validator approved
→ verify-slice-state router
→ slice-verifier                 # hard reset + reproducción humana + ## verify-slice + trailer
→ screen-journey-reviewer        # sólo si aplica UI/journey/visual contract
→ closer                         # report + commit + workflow Git configurado + cleanup
→ done sólo si closer prueba commit/push/merge/cleanup
```

El estado intermedio correcto después del verify es `verified_pending_close`, no `done`. Sólo `closer` puede mover la task a `done`.

## Paso 1 — Reconstrucción de contexto

1. Resuelve `<TASK_ID>` desde argumento o `CLAUDE_ACTIVE_TASK_ID`.
2. Lee task pack `orchestrator-state/tasks/task-packs/<TASK_ID>.md`.
3. Lee handoff `orchestrator-state/tasks/handoffs/<TASK_ID>.md`.
4. Lee registry/runtime/PROGRESS desde root canónico, no desde snapshot viejo de worktree.
5. Si el pack no existe o no menciona el TASK_ID, bloquea antes de spawnear nada.

## Paso 2.5 — Router mecánico de estado

Ejecuta siempre antes de spawnear nada, y repítelo después de `slice-verifier`, `debugger`/retest o un `closer` blocked:

```bash
./scripts/verify-slice-state.sh <TASK_ID> --json
```

Acciones:

- `invoke_slice_verifier` → sigue al Paso 4.
- `invoke_closer` → salta al Paso 6. Cubre el rescue donde `closer` corrió antes de verify y quedó `blocked`; no reinicies debugger si validator/tester/verify están verdes.
- `invoke_debugger_or_register_followup` → sigue al Paso 5.
- `invoke_debugger` → spawnea `debugger`, luego `validator` y `tester` en paralelo, y relanza `/verify-slice <TASK_ID>`.
- `wait_validator_tester` → no hagas verify todavía.
- `post_closer_done` → no relances closer/debugger; resume estado.
- `blocked` → corrige el blocker mecánico; no crees FU de producto por ruido.

Regla dura: `closer` sólo se invoca cuando este helper devuelve `invoke_closer`; entonces spawnea `closer`. `slice-verifier` sólo se invoca cuando devuelve `invoke_slice_verifier`.


## Verificación humana-real obligatoria

`/verify-slice` no es sólo un router de estados. El router decide CUÁNDO lanzar `slice-verifier`, pero `slice-verifier` debe ejecutar el contrato humano-real antiguo:

- Hard reset del entorno: parar servicios propios, reset DB, migraciones, datos base reales/proporcionados y datos específicos del slice desde `Verification Data Contract`.
- Navegación real como usuario en navegador mediante Chrome DevTools MCP aislado como opción primaria; fallback 2: Claude-in-Chrome MCP; fallback 3: Agent360 Browser MCP (`browser-mcp`).
- Observación de logs front + back + DB en vivo.
- Evidencia en `orchestrator-state/tasks/evidence/<TASK_ID>/verify-*`.
- Tabla visible para el usuario con URL, qué probar, descripción, resultado esperado, observado y pasa/no pasa.
- Bloque `## verify-slice` en handoff con `VERIFY_OUTCOME: verified|issues_found|blocked`.

MCP de navegador es obligatorio para el gate humano. Debe ser **usable**, no sólo aparecer listado. MCPs aceptados: `chrome-devtools`, `claude-in-chrome` y `agent360-browser-mcp`/`browser-mcp`. Política de elección: intenta siempre primero Chrome DevTools aislado (`--isolated` o `scripts/chrome-devtools-isolated-session.sh --task <TASK_ID>` + `--browser-url`), también para login/MFA si puede abrir una sesión visible por `TASK_ID`; si Chrome DevTools no está usable o no puede completar la sesión humana requerida, prueba `claude-in-chrome`; si tampoco responde, prueba Agent360 Browser MCP (`browser-mcp`). Si Chrome DevTools MCP falla por lock del profile, diagnostica con `bash scripts/chrome-mcp-doctor.sh || true`, imprime instrucciones de aislamiento con `bash scripts/chrome-devtools-isolated-session.sh --task <TASK_ID>`, cambia a claude-in-chrome y después a Agent360 sólo si están realmente usables, o bloquea con `BLOCKER_REASON: browser_mcp_unavailable` + `MCP_DIAGNOSTIC`. Si los MCP están listados pero sus llamadas fallan, no hagas fallback a `curl` como cierre humano: dile al usuario que conecte/reinicie uno de esos MCP y relance `/verify-slice <TASK_ID>`. Si uno de los MCP ya completó la reproducción humana, no repitas con otro sólo porque otro esté roto.

`slice-verifier` tiene `maxTurns: 130` para absorber navegación real con Chrome DevTools MCP. No amplíes el budget de spawns ni el `spawn_budget` global para esto: el límite de 20 subagentes por slice sigue igual. El agente debe hacer preflight corto, usar el MCP usable elegido y reservar margen para evidencia + tabla + handoff + trailer. Si el MCP está roto o el scope visual excede la slice, debe bloquear limpio con `VERIFY_OUTCOME: blocked` y `BLOCKER_REASON: mcp_budget_exhausted_or_scope_too_large` o el diagnóstico MCP correspondiente; no quedar `partial` ni relanzarse en bucle.

Antes de spawnear `slice-verifier`, escribe skeleton persistente para evitar estados parciales por interrupción:

```bash
./scripts/init-verify-slice-handoff.sh <TASK_ID>
```

Ese skeleton debe quedar sobrescrito lógicamente por un bloque final append-only del subagente. Si el subagente se interrumpe y no hay bloque final ni trailer, vuelve a lanzar `slice-verifier` con prompt focalizado `write-first skeleton already exists; finish MCP browser verification or write blocked`.

## Paso 4 — Spawn de `slice-verifier`

`slice-verifier` tiene un budget de tool-uses algo mayor (`maxTurns: 130`) porque Chrome DevTools MCP consume más llamadas en una verificación humana real. No amplíes el budget de spawns ni lances varios verificadores para compensar MCP roto: el agente debe escribir primero el skeleton, hacer preflight corto de Chrome DevTools y sólo después probar fallbacks acotados (`claude-in-chrome`, luego `browser-mcp`/Agent360).

Sólo si `verify-slice-state` devuelve `invoke_slice_verifier`, primero ejecuta `./scripts/init-verify-slice-handoff.sh <TASK_ID>` y luego spawnea **un único** subagente `slice-verifier` con este contexto literal:

```text
TASK_ID: <TASK_ID>
CLAUDE_TASK_PACK: orchestrator-state/tasks/task-packs/<TASK_ID>.md
MODO DAG ACTIVO: production = explicit_dag.
Unidad verificable = TASK_ID canónico del registry.
Hard reset obligatorio con datos reales/proporcionados del Verification Data Contract.
Primero confirma que un MCP aceptado está usable con una llamada mínima. Orden obligatorio de preferencia: 1) Chrome DevTools MCP aislado, 2) Claude-in-Chrome MCP, 3) Agent360 Browser MCP (`browser-mcp`). Usa Chrome DevTools también para MFA/2FA/CAPTCHA/sesión real si puede abrir una sesión visible por `TASK_ID`; si no puede completar esa sesión humana, pasa a claude-in-chrome y después a Agent360. Si Chrome DevTools MCP falla por profile lock, ejecuta `bash scripts/chrome-mcp-doctor.sh || true`, imprime aislamiento con `bash scripts/chrome-devtools-isolated-session.sh --task <TASK_ID>` y prueba los fallbacks en ese orden sólo si están realmente conectados. Si ninguno está usable, escribe ## verify-slice con VERIFY_OUTCOME: blocked, BLOCKER_REASON: browser_mcp_unavailable, MCP_DIAGNOSTIC y USER_ACTION_REQUIRED.
Presupuesto: `slice-verifier` tiene `maxTurns: 130` para acomodar Chrome DevTools MCP. Úsalo para hard reset + navegación real + logs/evidence, no para reintentos infinitos. Máximo 2 intentos cortos por MCP candidato; si el MCP sigue roto, el scope visual excede la slice o se agota el margen, escribe `VERIFY_OUTCOME: blocked` con `BLOCKER_REASON: mcp_budget_exhausted_or_scope_too_large` y acción requerida en vez de quedar partial.
Reproduce como usuario con navegador MCP, vigila logs front/back/DB, guarda evidencia verify-* y devuelve una tabla: URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa?.
Escribe ## verify-slice final en el handoff.
No invoques closer; no hagas commit; no marques done.
```

Debe emitir:

```text
CLAUDE_TRAILER:
TASK_ID: <TASK_ID>
OUTCOME: verified|issues_found|blocked
NEXT_STATUS: verified_pending_close|needs_debug|blocked
HANDOFF: orchestrator-state/tasks/handoffs/<TASK_ID>.md
EVIDENCE: orchestrator-state/tasks/evidence/<TASK_ID>/
VERIFY_OUTCOME: verified|issues_found|blocked
```

Mapeo obligatorio:

- `verified` → `verified_pending_close`.
- `issues_found` → `needs_debug`.
- `blocked` → `blocked`.

Cuando vuelva, ejecuta otra vez `./scripts/verify-slice-state.sh <TASK_ID> --json`. Si devuelve `invoke_closer`, sigue al Paso 6. Si devuelve `invoke_debugger_or_register_followup`, sigue al Paso 5. Si devuelve `blocked` con `VERIFY_OUTCOME: blocked` por MCP/entorno, PARA y muestra al usuario el `USER_ACTION_REQUIRED`; no spawnees closer ni debugger. Si el trailer se pierde, revisa el handoff: el agente debe haber escrito al menos el skeleton `## verify-slice` con `VERIFY_OUTCOME: pending`. Si hay sección final verified y el checker pasa, puedes continuar por el helper; si sólo hay skeleton pending o no hay evidencia, relanza `slice-verifier` una sola vez con prompt enfocado en `write-first skeleton already exists; finish MCP browser verification or write blocked`. Si vuelve a no escribir handoff, bloquea como fallo mecánico.

## Paso 5 — Si `slice-verifier` reporta issues

No preguntes al usuario para decidir el siguiente paso:

- Defecto dentro del `TASK_ID`/Write set → spawnea `debugger` con findings exactos, `TASK_ID`, `CLAUDE_TASK_PACK` y root split. Después lanza `validator` y `tester` en paralelo. Si pasan, relanza `/verify-slice <TASK_ID>` desde hard reset.
- Trabajo real fuera de scope pero aceptación actual verificada → registra FU formal `proposed` con `origin_task_id=<TASK_ID>`, `triage.scope_classification` y `triage.why_not_debugger`; después relanza `slice-verifier` o corrige el handoff para que `VERIFY_OUTCOME: verified` refleje que la aceptación actual sí pasa.
  Usa `/register-followup propose ... --scope-classification <out_of_scope|missing_coverage|...> --why-not-debugger <razón>`; sin esos campos no cierres la PR con deuda ambigua.
- Problema mecánico del orquestador/ambiente → corrige/reintenta o bloquea. No crees follow-up de producto.

Nunca uses el reset completo `debugger → validator+tester → verify-slice` cuando el diagnóstico dice “sólo falta closer” y validator/tester/verify ya están correctos. En ese caso ve al Paso 6.

## Paso 5.2 — Screen/Journey review condicional antes de closer

HTML preview/docs visuales son referencia/evidencia, no source-of-truth.

Si la task toca UI, UX, journey, rutas, pantallas, VISUAL_CONTRACT_CHECK/visual contract, auth visible, navegación o `journey_refs`, spawnea **un único** `screen-journey-reviewer` después de `slice-verifier` y antes de `closer`.

Contexto obligatorio:

```text
TASK_ID: <TASK_ID>
CLAUDE_TASK_PACK: orchestrator-state/tasks/task-packs/<TASK_ID>.md
MODO DAG ACTIVO: production = explicit_dag.
Revisa UX_CONTRACT, Technical Guide, Checklist, handoff, verify-slice y evidencia.
Si el problema cabe en TASK_ID/Write set: OUTCOME=changes_requested; needs_debugger=yes; NO FU.
Si falta trabajo/datos/contrato fuera de scope: OUTCOME=blocked; followup_candidate=yes; why_not_debugger obligatorio.
```

Luego valida:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice --require-screen-journey-review
```

Si `OUTCOME: changes_requested`, va a debugger/retest. Si `blocked` por FU real fuera de scope y la aceptación actual sigue verificada, registra FU `proposed` y continúa; si no puedes decidir, bloquea.

## Paso 5.bis — Journey-closing

Si esta slice cierra journeys, usa `python3 -B -S .claude/bin/list_journey_closures.py <TASK_ID> --json` antes de closer para que el cierre sepa qué journeys debe clasificar.

- Si el journey se verificó inline y el handoff contiene `## verify-journey` con `JOURNEY_VERIFY_OUTCOME: verified`, el closer debe emitir `JOURNEY_VERIFIED_INLINE: <JID>`.
- Si no puede verificarse inline automáticamente, el closer debe emitir `JOURNEY_PENDING_VERIFY: <JID>`.
- En DAG-only, pending journey bloquea sólo tasks que referencian ese journey, no todo el grafo.

## Paso 6 — Orquestación de cierre

Cuando el handoff tiene validator approved + tester pass + `## verify-slice` con `VERIFY_OUTCOME: verified`, ejecuta:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice
```

Si pasa, spawnea **un único** `closer` con este contexto:

```text
TASK_ID: <TASK_ID>
CLAUDE_TASK_PACK: orchestrator-state/tasks/task-packs/<TASK_ID>.md
MODO DAG ACTIVO: production = explicit_dag.
cierra sólo el TASK_ID explícito.
El estado verificado previo es verified_pending_close; sólo closer puede pasar a done.
Las FU formales proposed del origin_task_id se meten en la PR, no bloquean este close.
Ejecuta report + sync baseline + git-add-slice + commit + workflow Git configurado mediante ./scripts/git-workflow.sh + slice-clean + cleanup-worktrees + deferred cleanup. `git-add-slice` debe crear/stagear `orchestrator-state/tasks/lifecycle-events/<TASK_ID>.json`; no stagees `registry.json` ni crees commits manuales de sync post-close state. El cleanup debe ser hook-safe: no debe borrar la worktree activa del closer antes del SubagentStop; `active_deferred=1` es aceptable si no hay dirty/skipped y el cleanup imprimió `DEFERRED_CLEANUP_COMMAND` y dejó una petición en `cleanup-requests/`.
En pr-flow, done exige PR merged y root canónico sincronizado; PR abierta/queued = blocked mecánico, no FU.
```

Acepta cierre sólo si el trailer de `closer` trae exactamente:

```text
OUTCOME: committed
NEXT_STATUS: done
REPORT_READY: yes
BASELINE_SYNC_READY: yes
GIT_READY: yes
PUSH_READY: yes
WORKTREES_CLEANED: yes
```

Si `closer` devuelve `blocked` por PR pendiente, CI rojo, auto-merge no habilitado, cleanup dirty o root canónico dirty, no lances debugger salvo que el bloqueo sea un defecto de producto. Corrige el bloqueo mecánico y relanza `closer` o `/verify-slice <TASK_ID>`; la verificación existente en handoff sigue siendo válida si el código no cambió.

## Trailer final del comando

Como comando, resume lo ocurrido al usuario. Los trailers de estado los emiten los subagentes (`slice-verifier`, `screen-journey-reviewer`, `debugger`, `validator`, `tester`, `closer`) y los consume el hook bajo lock.

Incluye en la respuesta final la tabla producida por `slice-verifier` o un resumen fiel de ella:

| URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa? |
|-----|------------|-------------|--------------------|---------------------|-------|

Y debajo:

- MCP usado: Chrome DevTools MCP | Claude-in-Chrome MCP | Agent360 Browser MCP (`browser-mcp`) | blocked.
- Filas del Verification Data Contract usadas.
- Datos reales/proporcionados cargados.
- Datos persistidos observados.
- Logs front/back/DB revisados.

Luego añade:

```text
TASK_ID: <TASK_ID>
VERIFY_ACTION: <acción del router>
CLOSER_ACTION: invoked|not_invoked|relaunch_needed
FOLLOWUPS_PROPOSED: <FU IDs o none>
NEXT_ACTION: /next-slice | relaunch closer | debugger/retest | fix mechanical blocker
```
