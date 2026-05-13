---
description: Promueve follow-ups propuestos a tasks DAG reales bajo control del main-orchestrator, con aprobación humana, locks, validación DAG y respeto de conflictos activos.
argument-hint: "<FOLLOWUP_ID>|--blocking|--all-proposed|--list"
---

# /promote-followup

## Rule loading

Antes de actuar, lee:

1. `.claude/CLAUDE.md`
2. `.claude/rules/02-phase-execution.md`
3. `.claude/rules/04-traceability.md`
4. `.claude/rules/05-runtime-write-contract.md`
5. `.claude/orchestrator-contract.json`
6. `orchestrator-state/tasks/runtime-state.json`
7. `orchestrator-state/tasks/registry.json`

Eres el **main-orchestrator** ejecutándose como main thread agent. Este comando convierte FU propuestas en tasks DAG reales. No es un comando de worker ni del closer.

Arranque correcto:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"
```

## Invariantes

- El `closer` nunca ejecuta promote automáticamente.
- Este comando es la vía humana/orquestador para promover FU a tasks DAG.
- No promociones desde un terminal worker con `CLAUDE_ACTIVE_TASK_ID` activo salvo decisión explícita del usuario. Si detectas ese env var, PARA y recomienda:

```bash
unset CLAUDE_ACTIVE_TASK_ID
unset CLAUDE_TASK_PACK
unset CLAUDE_WORKTREE_ROOT
unset CLAUDE_ORCHESTRATOR_ROOT
```

- No edites a mano `registry.json`, `runtime-state.json`, `task-dag.json`, `task-dag.md` ni work-items. La mutación la hace el script bajo locks.
- La promoción puede escribir:
  - `docs/source-of-truth/*_IMPLEMENTATION_CHECKLIST.md`
  - `orchestrator-state/tasks/registry.json`
  - `orchestrator-state/tasks/work-items/<TASK_ID>.yaml`
  - `orchestrator-state/memory/task-dag.json`
  - `orchestrator-state/memory/task-dag.md`
  - `orchestrator-state/tasks/runtime-state.json`
  - `orchestrator-state/tasks/ledger.jsonl`
  - `orchestrator-state/tasks/source-doc-patches/<FOLLOWUP_ID>.md`
- `register_followup_task.py promote` ya evalúa dependencias y conflictos activos. Si la FU promovida pisa `Conflict group` o `Write set` de una task activa/claimed/in_progress, la task nueva debe quedar `blocked` con `blocked_reason: conflict_with_worker_task` hasta que `promote_ready_tasks()` pueda desbloquearla.

## Triage antes de promover

Antes de promover, inspecciona `triage.scope_classification` y `triage.why_not_debugger` de la FU:

- Si `scope_classification` falta o es `unspecified`, no promociones sin preguntar. Pide completar triage con `/register-followup propose --scope-classification ... --why-not-debugger ...` o waiver humano.
- Si el hallazgo realmente es `in_scope_defect`, no promociones: waivea/rechaza la FU y reabre el flujo `debugger -> validator ‖ tester -> /verify-slice`.
- Si `scope_classification` es `out_of_scope|missing_coverage|missing_real_data|external_dependency|future_enhancement|scope_expansion|blocked_by_human_decision` y `why_not_debugger` es claro, puedes pedir confirmación `PROMOTE <FOLLOWUP_ID>`.

Esto evita FU spam: el DAG sólo recibe trabajo nuevo real, no bugs reparables dentro de la slice.

## Modo de uso

### Listar

Si `$ARGUMENTS` está vacío o es `--list`, no promociones nada. Ejecuta:

```bash
./scripts/register-followup-task.sh list --json
```

Muestra al usuario una tabla con:

| FU | status | severity | scope | origin_task_id | title | action |
|---|---|---|---|---|---|---|

Prioriza `status=proposed` y `severity=blocker|critical|high`. Recomienda el comando exacto:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"
```

### Promover una FU

Si `$ARGUMENTS` contiene un `FU-...`, haz:

1. Ejecuta `./scripts/register-followup-task.sh list --json`.
2. Localiza la FU exacta. Si no existe, PARA.
3. Si `status != proposed`, no promociones de nuevo; muestra estado actual (`promoted`, `waived`, etc.).
4. Muestra plan antes de mutar:
   - FU id, severidad, origen, título.
   - `triage.scope_classification` y `triage.why_not_debugger`.
   - `depends_on`, `conflict_groups`, `write_set`, `journey_refs`.
   - Si `journey_refs` contiene IDs que no existen en `UX_CONTRACT.md`/journey matrix, no promociones: primero actualiza source-of-truth o promueve una FU sin `--journey-ref` para definir la nueva journey.
   - Rutas que se van a escribir.
   - Nota: si hay conflicto activo, la task promovida quedará `blocked` automáticamente.
5. Pide confirmación humana literal:

```text
PROMOTE <FOLLOWUP_ID>
```

6. Solo tras esa confirmación, ejecuta:

```bash
./scripts/register-followup-task.sh promote <FOLLOWUP_ID>
```

7. Después ejecuta validaciones:

```bash
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
./scripts/next-wave.sh
```

8. Resume:
   - `promoted_task_id`.
   - `status` resultante (`ready` o `blocked`).
   - si quedó bloqueada, `blocked_reason` y `blocked_by`.
   - siguiente comando seguro para abrir wave o continuar.

### Promover bloqueantes en lote

`/promote-followup --blocking` solo puede promover FU `proposed` con severidad `blocker|critical|high`.

Flujo:

1. Lista FU con `./scripts/register-followup-task.sh list --json`.
2. Muestra todas las FU bloqueantes propuestas.
3. Pide confirmación humana literal:

```text
PROMOTE BLOCKING FOLLOWUPS
```

4. Promueve una por una, ejecutando `./scripts/register-followup-task.sh promote <FOLLOWUP_ID>` por cada FU.
5. Si una promoción falla, PARA y no sigas con las restantes hasta que el usuario decida.
6. Ejecuta los checks finales una sola vez.

### Promover todas las propuestas

`/promote-followup --all-proposed` es deliberadamente más peligroso. Úsalo solo si el usuario lo pidió explícitamente.

Confirmación literal requerida:

```text
PROMOTE ALL PROPOSED FOLLOWUPS
```

## Relación con /register-followup

`/register-followup` sigue existiendo para operaciones CRUD de bajo nivel:

```bash
/register-followup propose ...
/register-followup waive <FOLLOWUP_ID> ...
/register-followup list
```

Para convertir FU en tasks DAG productivas, usa este comando:

```bash
/promote-followup <FOLLOWUP_ID>
```

## Criterio de éxito

Termina con:

```text
PROMOTE_FOLLOWUP_READY: yes|no
FOLLOWUP_ID: <FOLLOWUP_ID>|<count>
PROMOTED_TASK_ID: <TASK_ID>|<none>
STATUS: ready|blocked|already_promoted|failed
NEXT_ACTION: <next-wave|verify|waive|manual_fix>
```
