---
description: Gate de verificación por slice DAG. Coordina slice-verifier, screen/journey-reviewer cuando aplica, debugger/retest si hay issues y closer para commit + PR/push + merge + cleanup.
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

## Paso 4 — Spawn de `slice-verifier`

Sólo si `verify-slice-state` devuelve `invoke_slice_verifier`, spawnea **un único** subagente `slice-verifier` con este contexto literal:

```text
TASK_ID: <TASK_ID>
CLAUDE_TASK_PACK: orchestrator-state/tasks/task-packs/<TASK_ID>.md
MODO DAG ACTIVO: production = explicit_dag.
Unidad verificable = TASK_ID canónico del registry.
Hard reset obligatorio con datos reales/proporcionados del Verification Data Contract.
Reproduce como usuario, vigila logs y escribe ## verify-slice en el handoff.
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
```

Mapeo obligatorio:

- `verified` → `verified_pending_close`.
- `issues_found` → `needs_debug`.
- `blocked` → `blocked`.

Cuando vuelva, ejecuta otra vez `./scripts/verify-slice-state.sh <TASK_ID> --json`. Si devuelve `invoke_closer`, sigue al Paso 6. Si devuelve `invoke_debugger_or_register_followup`, sigue al Paso 5. Si el trailer se pierde, revisa el handoff: el agente debe haber escrito `## verify-slice`. Si está escrito y el checker pasa, puedes continuar por el helper; si no, relanza `slice-verifier`, no `closer`.

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
Ejecuta report + sync baseline + git-add-slice + commit + workflow Git configurado mediante ./scripts/git-workflow.sh + slice-clean + cleanup-worktrees.
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

Incluye en la respuesta final:

```text
TASK_ID: <TASK_ID>
VERIFY_ACTION: <acción del router>
CLOSER_ACTION: invoked|not_invoked|relaunch_needed
FOLLOWUPS_PROPOSED: <FU IDs o none>
NEXT_ACTION: /next-slice | relaunch closer | debugger/retest | fix mechanical blocker
```
