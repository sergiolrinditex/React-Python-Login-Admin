---
description: "Lista la wave DAG actual: tasks ready independientes, deps, posibles conflictos y comandos para abrir terminales paralelos. No implementa ni spawnea agentes."
argument-hint: "[opcional: phase id o límite N; sin argumento = earliest incomplete phase]"
---
### Root split obligatorio

- Lee `registry.json`, `runtime-state.json`, `PROGRESS.md`, `task-dag.*` desde `$CLAUDE_ORCHESTRATOR_ROOT/orchestrator-state/`.
- Lee/escribe handoff, evidence, report y task-pack desde la worktree activa (`./orchestrator-state/tasks/...`) cuando la slice corre en worktree.
- No registres follow-ups por errores mecánicos del orquestador (root stale, heading de handoff, checker/lint flake, cleanup omitido). Corrige, reintenta o bloquea; FU solo para trabajo de producto fuera de scope.


# /next-wave

Eres el **main-orchestrator** en modo planificación. Este comando NO implementa nada y NO invoca subagentes. Solo lee estado y propone una wave paralelizable.

## Ejecución mecánica recomendada

Antes de resumir manualmente, ejecuta:

```bash
./scripts/next-wave.sh
```

El wrapper hace housekeeping no destructivo antes de calcular la wave: compacta automáticamente `orchestrator-state/agent-memory/*/MEMORY.md` cuando superan 250 líneas, sincroniza el root canónico con `origin/main` mediante fast-forward seguro, limpia worktrees diferidas si ya es seguro, rehidrata registry desde lifecycle-events, borra worktrees limpios + ramas locales `dev/<TASK_ID>`/`feature/<TASK_ID>` de tasks ya cerradas, limpia ramas locales zombis sin patches únicos frente a `origin/main` y limpia ramas remotas de PR ya mergeadas con `cleanup-merged-pr-branches.sh`. La sincronización de main bloquea si hay cambios dirty no-runtime como `docs/source-of-truth/*`; no calcula una wave sobre source-of-truth local sin integrar. La limpieza remota sólo borra si GitHub confirma `MERGED` y el OID de la rama remota coincide con el `headRefOid` de esa PR; PR abierta, branch movida, falta de `gh` o auth no bloquean la wave. Una cleanup request con PR todavía abierta queda pendiente y no es warning; una task cerrada pero dirty debe mostrar diagnóstico y requiere revisión humana antes de borrar. Usa su salida como base. No inventes ready nodes a mano si el script dice que no hay.

No reinicies ni mates MCPs desde `/next-wave`. Los MCPs de navegador pertenecen al preflight de `/verify-slice`/`slice-verifier`, porque puede haber terminales DAG paralelas usando sesiones visibles.

## Lectura obligatoria

1. `.claude/CLAUDE.md`
2. `.claude/rules/02-phase-execution.md`
3. `.claude/rules/04-traceability.md`
4. `.claude/rules/05-runtime-write-contract.md`
5. `.claude/orchestrator-contract.json`
6. `orchestrator-state/tasks/registry.json`
7. `orchestrator-state/tasks/runtime-state.json`
8. `orchestrator-state/memory/task-dag.json` y `task-dag.md` si existen
9. `orchestrator-state/memory/PROGRESS.md` cabecera

## Gates antes de listar

- Si `runtime-state.pending_journey_verifications` no está vacío, DAG-only difiere solo tasks con esos `Journey refs` y lista `/verify-journey <JID>`. No hay otro modo de journey gate.
- Si `runtime-state.open_followups` contiene propuestas `high|critical|blocker` en estado `proposed`, no abras wave: promueve con `/promote-followup <ID>` o descarta con waiver humano explícito.
- Valida con `./scripts/check-task-dag.sh --strict`; si el DAG tiene errores o `task_dag.mode != explicit_dag`, no propongas paralelismo. Este orquestador opera en production DAG-only; si falta `Depends on`, el Coverage Registry debe corregirse.
- Solo considera la earliest incomplete phase. No adelantes Phase N+1 si Phase N tiene tareas no `done`.

## Selección de wave

Una task entra en la wave si:

- `status == ready`;
- todos sus `depends_on` están `done`;
- no está `claimed`;
- no cierra un journey pendiente de verificación anterior;
- no tiene conflicto activo contra otra task ya claimed/in_progress;
- no comparte `Conflict group` ni `Write set` con otra task seleccionada para la misma wave.

Conflictos probables: misma migración, misma pantalla, mismo state handler, mismo endpoint family, mismo fichero de configuración, misma carga global de datos proporcionados, mismo router/theme/dependency file. El script serializa mecánicamente los conflictos declarados en el Coverage Registry; no los fuerces a mano aunque el DAG de dependencias lo permita.

## Salida

Devuelve:

```md
# DAG wave propuesta

- DAG mode: explicit_dag
- Phase: <Pxx>
- Ready nodes: <N>
- Recomendación de paralelo: <N seguro> terminales

| TASK_ID | Título | Depends on | Conflict group | Write set | Comando terminal |
|---|---|---|---|---|---|
| P.. | ... | — | api:auth | {{backend.module_root}}/**/auth* | `export CLAUDE_ACTIVE_TASK_ID=P.. CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P...md` → `claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P.."` |

## Orden sugerido si prefieres serializar
1. <TASK_ID>
2. <TASK_ID>

## Recordatorio
Cada terminal debe mantener `CLAUDE_ACTIVE_TASK_ID=<TASK_ID>` durante todo el slice y pasar `CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md` a los agentes. El script imprime el `export` copy/paste y el comando `claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"`; `/next-slice <TASK_ID>` hará el claim atómico después de la aprobación humana y el `planner` enriquecerá ese pack por task.
```

No abras terminales tú. No spawnees agentes. No cambies registry. El script `next_wave.py` es read-only, imprime bloques copy/paste para más de dos terminales cuando el DAG lo permite, y mueve a "Serializados por conflicto" los nodos ready que comparten `Conflict group`/`Write set` con la wave segura.


Nota worktree: en proyectos `pr-flow`, `./scripts/next-wave.sh` imprime un bloque que crea/entra en el worktree `dev/<TASK_ID>` antes de lanzar Claude Code. Usa el bloque exacto que imprime; no lances `/next-slice` desde `main` para una task de PR.
