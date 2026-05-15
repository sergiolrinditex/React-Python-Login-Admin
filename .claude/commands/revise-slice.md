---
description: Reabre una slice concreta ya implementada para corregir issues sin inventar una slice nueva. Mantiene TASK_ID, memoria, DAG, journeys y cableado; luego revalida y vuelve a closer con commit correctivo + configured Git workflow.
argument-hint: "<TASK_ID> \"motivo o hallazgo\""
---

# /revise-slice

## Rule loading

Antes de ejecutar este comando, considera cargadas las reglas no-scoped de `.claude/rules/`. Si no ves esas reglas en contexto tras `/clear`, léelas explícitamente en este orden: `00-source-of-truth.md`, `01-non-negotiables.md`, `02-phase-execution.md`, `03-dev-loop.md`, `04-traceability.md`, `05-runtime-write-contract.md`.

Eres el **main-orchestrator** en modo corrección. Este comando existe para arreglar una slice canónica sin crear sub-slices temporales ni alterar la matriz DAG.

## Contrato

- Requiere `TASK_ID` explícito. Si no viene en `$ARGUMENTS`, pide el ID y no hagas nada más.
- El `TASK_ID` debe existir en `orchestrator-state/tasks/registry.json`.
- No cambies `Depends on`, `task-dag.json`, `Journey Coverage Matrix` ni IDs canónicos.
- Usa el mismo handoff: `orchestrator-state/tasks/handoffs/<TASK_ID>.md`.
- Conserva evidencia histórica. Añade nueva evidencia en `orchestrator-state/tasks/evidence/<TASK_ID>/revision-*`.
- Si ya existe `orchestrator-state/tasks/reports/<TASK_ID>.md`, el closer escribirá además `orchestrator-state/tasks/reports/<TASK_ID>-revision-<YYYYMMDD-HHMMSS>.md`.
- En modo DAG, exporta `CLAUDE_ACTIVE_TASK_ID=<TASK_ID>` antes de spawnear agentes para que hooks, ledger, memoria y spawn budget contabilicen contra el nodo correcto.

## Paso 1 — Reconstruir contexto

Lee solo lo necesario:

1. `registry.json` para localizar task, status, deps, journey refs y source refs.
2. `runtime-state.json` para detectar journeys pendientes o workers a medio.
3. `PROGRESS.md` cabecera + últimas 3 entradas.
4. Handoff y evidence report existentes del TASK_ID.
5. Secciones fuente apuntadas por el registry en el source-of-truth pack.
6. Motivo de revisión pasado en `$ARGUMENTS`.

Si `runtime-state.pending_journey_verifications` contiene journeys que no pertenecen a este TASK_ID, informa que la revisión puede seguir. En DAG-only sólo se diferirán tasks que referencian esos journeys.

## Paso 2 — Plan de revisión y aprobación

Presenta:

```md
# Revisión de slice

- TASK_ID: <id>
- Estado actual: <done|claimed|needs_debug|...>
- Motivo: <motivo>
- Journey refs afectados: <JIDs o none>
- DAG: no se cambia; deps actuales = <...>
- Memoria/handoff: se apendiza, no se sobrescribe

## Plan
1. debugger corrige solo el issue descrito.
2. validator ‖ tester vuelven a correr.
3. /verify-slice verifica como usuario.
4. closer genera report de revisión si aplica, commit correctivo en el checkout correcto del TASK_ID, workflow Git configurado (`./scripts/git-workflow.sh`) y cleanup de worktrees.

## Riesgos
- <archivos o journeys que pueden verse afectados>

¿Procedo? Responde sí / adelante / go.
```

No spawnees agentes sin aprobación explícita.

## Paso 3 — Ejecutar corrección

Después de aprobación:

```bash
export CLAUDE_ACTIVE_TASK_ID=<TASK_ID>
```

Spawnea `debugger` con:

- TASK_ID.
- motivo exacto.
- handoff/report/evidence existentes.
- source refs del registry.
- restricción: parche mínimo, sin ampliar scope, sin crear Slice ID nuevo.

El debugger debe apendizar al handoff:

```markdown
## revision-debugger

- TIMESTAMP: <ISO-8601>
- REASON: <motivo>
- FILES_CHANGED: <lista>
- TESTS_RUN: <lista>
- OUTCOME: fixed|blocked
- EVIDENCE: orchestrator-state/tasks/evidence/<TASK_ID>/revision-*
```

Si `OUTCOME: blocked`, para y reporta bloqueo.

## Paso 4 — Revalidar

Lanza en paralelo en un solo mensaje con dos Agent calls:

- `validator` sobre el diff completo + razón de revisión.
- `tester` con los comandos del registry para ese TASK_ID + pruebas de regresión cercanas.

Si tester falla o validator pide cambios, vuelve a debugger. Máximo 3 ciclos. Al cuarto fallo, marca blocked y no cierres.

## Paso 5 — Verify + closer

Si validator y tester pasan:

1. Ejecuta `/verify-slice --task <TASK_ID>`; no saltes el `slice-verifier` MCP ni el router.
2. Si `VERIFY_OUTCOME: issues_found`, vuelve al debugger.
3. Si `VERIFY_OUTCOME: blocked`, muestra el blocker mecánico/humano y para.
4. Si el router devuelve `invoke_closer` (`verified_pending_close` + handoff completo), spawnea `closer`.
5. El closer debe devolver:

```text
OUTCOME: committed
NEXT_STATUS: done
REPORT_READY: yes
GIT_READY: yes
PUSH_READY: yes
WORKTREES_CLEANED: yes
```

Si `REPORT_READY`, `GIT_READY`, `PUSH_READY` o `WORKTREES_CLEANED` no son `yes`, la revisión no está cerrada. Informa el motivo exacto y no marques éxito.

## Salida final

Resume:

- TASK_ID revisado.
- Commit hash si existe.
- Push status.
- Report o report de revisión.
- Worktrees limpiados o pendientes.
- Journeys que deben re-verificarse si aplica.
