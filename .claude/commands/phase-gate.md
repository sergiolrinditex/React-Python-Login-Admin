---
description: "Verifica mecánicamente que una phase está cerrada antes de avanzar: tasks done, journeys verificados, reports/evidence y git opcional."
argument-hint: "[PHASE_ID] [--require-git-clean]"
---

# /phase-gate

## Rule loading

Considera cargadas `.claude/CLAUDE.md`, `.claude/rules/02-phase-execution.md`, `.claude/rules/04-traceability.md`, `.claude/rules/05-runtime-write-contract.md` y `.claude/orchestrator-contract.json`.

Eres el **main-orchestrator** cerrando una phase. Este comando no implementa código ni spawnea agentes: solo valida si se puede avanzar a la siguiente phase.

## Ejecución mecánica obligatoria

Ejecuta:

```bash
./scripts/phase-gate.sh $ARGUMENTS
```

Usa exactamente el resultado del script. No declares una phase cerrada si el script dice `BLOCKED`.

## Qué valida

- `registry.task_dag` sin errores ni ciclos.
- Todas las tasks de la phase están `done`.
- Cada task cerrada tiene handoff, evidence dir y report de closer.
- `runtime-state.pending_journey_verifications` está vacío.
- Todo journey cuya frontera terminal DAG cae en esta phase está `verified` o `waived`. No se usa `task_ids[-1]`; se usa `terminal_task_ids`/`completion_policy=all_task_ids_done`.
- Con `--require-git-clean`: repo en `main`, working tree limpio y sin commits pendientes frente a `origin/main` cuando exista remoto.

## Si está OK

Reporta:

```text
PHASE_GATE: pass
PHASE_ID: <Pxx>
NEXT_ACTION: /next-wave para la siguiente phase o /next-slice si se trabaja serializado
```

## Si está BLOCKED

No avances. Lista los errores concretos y la acción:

- task no `done` → terminar `/verify-slice` + `closer` de esa task.
- journey pendiente → ejecutar `/verify-journey <JID>`.
- report/evidence/handoff faltante → revisar closer de la task.
- git no limpio/no pusheado → resolver Git antes de avanzar.

No modifiques `registry.json` a mano para forzar el gate.
