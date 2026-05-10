# Legacy y DAG runbook

Este documento enseña los dos modos del orquestador: el modo legacy lineal y el modo DAG explícito tipo Airflow. Ambos usan los mismos agentes, hooks, locks, memoria, journeys y closer. Lo único que cambia es el scheduler de slices.

## 1. Regla de oro

La source-of-truth sigue siendo el trío de documentos:

```text
docs/source-of-truth/instrucciones.md
docs/source-of-truth/<APP>_TECHNICAL_GUIDE.md
docs/source-of-truth/<APP>_IMPLEMENTATION_CHECKLIST.md
```

No se edita a mano ni `registry.json` ni `task-dag.json` ni la matriz de adyacencia. El bootstrap los deriva desde el `Coverage Registry` del checklist.

Para productos grandes, el registry es acumulativo: BaseApp y versiones ya cerradas siguen en los docs con `Build state=done`; el incremento activo usa `Product increment=vN` y `Build state=planned`. Así el DAG conserva el contexto completo y no reconstruye trabajo ya cerrado.

## 2. Modo legacy lineal

Usa este modo cuando el `Coverage Registry` no tenga columna `Depends on`.

```md
| Slice ID | Tipo | Target | Step | Product increment | Build state | Verify mínimo |
|---|---|---|---|---|---|---|
| P00-S01-T001 | setup | scaffold | Step 0.1 | baseapp | done | test A |
| P00-S01-T002 | api | GET /health | Step 0.1 | v1 | planned | test B |
| P00-S02-T001 | flutter | HomePage / | Step 0.2 | v1 | planned | test C |
```

El bootstrap genera una cadena secuencial:

```text
T001 -> T002 -> T003 -> ...
```

Comandos:

```bash
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-journey-matrix.sh --strict
./scripts/check-task-dag.sh --strict
./scripts/check-wiring-contract.sh --strict
```

Resultado esperado:

```text
Task DAG: OK mode=legacy_linear nodes=<N> edges=<N-1> waves=<N>
```

Ejecución:

```text
/next-slice
/verify-slice
/clear
/next-slice
```

## 3. Modo DAG explícito

Usa este modo cuando el `Coverage Registry` tenga columna `Depends on`. En este modo, cada fila debe declarar si es root o de quién depende.

```md
| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | api | GET /health | Step 0.1 | baseapp | done | low | auto | — | api:health | api/src/**/health* | — | — | GET /health | — | §7 | §6.2 | endpoint responde 200 | curl /health |
| P00-S01-T002 | db | init DB | Step 0.1 | v1 | planned | medium | human | — | db:migrations | api/alembic/versions/** | — | — | — | users | §3.1 | §10.3 | migration up/down | alembic upgrade head |
| P00-S02-T001 | api | GET /ready | Step 0.2 | v1 | planned | P00-S01-T001, P00-S01-T002 | api:ready | api/src/**/ready* | — | — | GET /ready | users | §7 | §6.2 | espera API + DB | curl /ready |
```

El bootstrap deriva:

```text
orchestrator-state/tasks/registry.json
orchestrator-state/memory/task-dag.json
orchestrator-state/memory/task-dag.md
orchestrator-state/tasks/work-items/*.yaml
```

`task-dag.json` contiene:

```text
nodes
edges
adjacency_index
adjacency_matrix
adjacency_list
reverse_dependencies
topological_levels
```

La matriz de adyacencia es derivada: filas = nodo origen, columnas = nodo destino; `1` significa `origen -> destino`.

## 4. Bootstrap DAG completo

```bash
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
```

Resultado esperado para la BASEAPP DAG incluida:

```text
Three-doc contract is valid.
Bootstrapped project prefix: BASEAPP
Detected phases: 13
Generated tasks: 84
Detected journeys: 8
Task DAG: OK mode=explicit_dag nodes=84 edges=134 waves=8
Journey matrix coherent — 8 journeys validadas, 0 drifts
Wiring contract coherent — 13 routes, 41 endpoints, 84 registry rows, 8 journeys, data_contract=1
```

## 5. Cómo abrir una wave paralela

Primero lista la wave:

```bash
./scripts/next-wave.sh
```

La salida tiene bloques copiables. Ejemplo:

```text
# DAG wave propuesta

- DAG mode: `explicit_dag`
- Phase: `P00`
- Ready nodes: 3
- Recomendación de paralelo: 3 terminales

## Copia y pega por terminal

### Terminal 1 — P00-S01-T001
export CLAUDE_ACTIVE_TASK_ID=P00-S01-T001 CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P00-S01-T001.md && echo 'Ahora ejecuta en Claude Code: /next-slice P00-S01-T001'

### Terminal 2 — P00-S01-T003
export CLAUDE_ACTIVE_TASK_ID=P00-S01-T003 CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P00-S01-T003.md && echo 'Ahora ejecuta en Claude Code: /next-slice P00-S01-T003'

### Terminal 3 — P00-S03-T001
export CLAUDE_ACTIVE_TASK_ID=P00-S03-T001 CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P00-S03-T001.md && echo 'Ahora ejecuta en Claude Code: /next-slice P00-S03-T001'
```

En cada terminal:

```bash
export CLAUDE_ACTIVE_TASK_ID=<TASK_ID> CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md
```

Después, dentro de Claude Code en ese mismo terminal:

```text
/next-slice <TASK_ID>
```

No cambies `CLAUDE_ACTIVE_TASK_ID` hasta terminar ese slice. Los hooks lo usan para escribir ledger, spawn budget, evidence, handoffs y runtime de ese nodo, aunque el singleton `active-task.json` haya cambiado por otro terminal.

## 6. Más de dos terminales

Sí, el DAG permite más de dos terminales. El límite real no es el orquestador sino los conflictos de Git, ficheros compartidos, migraciones y capacidad de revisión humana.

Regla práctica:

```text
1 terminal por TASK_ID ready con riesgo bajo.
Serializa TASK_IDs que toquen la misma pantalla, mismo provider, misma migración, misma familia de endpoint o mismo fichero global.
```

`./scripts/next-wave.sh` recomienda N terminales seguros y mueve a la seccion "Serializados por conflicto" los ready que comparten `Conflict group` o `Write set`. Si quieres limitar:

```bash
./scripts/next-wave.sh --limit 4
```

## 7. Journeys y DAG

La `Journey Coverage Matrix` de `instrucciones.md` no es el scheduler. Sirve para cobertura funcional:

```text
Journey Matrix Slices -> qué slices prueban el journey
Coverage Registry Depends on -> orden y paralelismo del DAG
```

Si un closer deja journeys pendientes en `runtime-state.pending_journey_verifications`, `/next-wave` aplica `journey_gate_mode=frontier` por defecto: las ramas independientes siguen y solo se difieren tasks que referencian esos journeys. En `strict` se conserva el bloqueo global hasta ejecutar:

```text
/verify-journey <JID>
```

`/verify-journey` no debe editar `registry.json`/`runtime-state.json` a mano. Para cerrar o waiverear una journey usa el helper lockeado:

```bash
./scripts/update-journey-verification.sh <JID> --outcome verified
./scripts/update-journey-verification.sh <JID> --outcome waived --reason "<motivo>"
```

## 8. Hooks, locks y memoria en paralelo

Flujo por terminal:

```text
CLAUDE_ACTIVE_TASK_ID=<TASK_ID>
  -> claim_task.py marca TASK_ID como claimed
  -> /next-slice ejecuta planner/developer/validator/tester/debugger/closer
  -> hook_capture_subagent_stop.py valida trailer y scope
  -> registry lock primero
  -> runtime-state lock segundo
  -> ledger + evidence + handoff quedan asociados al TASK_ID del terminal
```

Invariantes:

```text
- Un nodo con varios predecessors solo pasa a ready cuando TODOS están done.
- claim_task.py impide doble claim del mismo TASK_ID.
- Si el trailer del agente trae otro TASK_ID bajo CLAUDE_ACTIVE_TASK_ID, el hook registra scope mismatch y no muta otro nodo.
- Las journey mutations también se ignoran en caso de scope mismatch.
- El closer no cierra si falta verify-slice, tester verde, evidence o push cuando aplica.
```


## 8.bis Contrato central de escritura y UX

Para que los subagentes no dependan de memoria implícita, el contrato está centralizado en:

```text
.claude/orchestrator-contract.json
.claude/rules/05-runtime-write-contract.md
```

Cada agente lee ambos al arrancar. El JSON define qué puede escribir cada agente, qué ficheros son estado derivado, qué trailer exige el closer y qué campos UX debe traer una pantalla. El rule `.md` es la versión humana resumida.

El hook `hook_write_scope_guard.py` protege los casos peligrosos:

```text
- bloquea edición de `.claude/` durante ejecución normal de apps;
- bloquea escribir handoff/evidence/report/task-pack de otro TASK_ID;
- bloquea editar docs/source-of-truth con un TASK_ID activo;
- bloquea editar registry/runtime/ledger/task-dag directamente con Write/Edit/MultiEdit.
```

Esto mantiene el DAG rápido pero no corruptible: los scripts y hooks escriben estado core bajo locks; los agentes escriben solo su pack, handoff, evidence, report o código de su slice.

UX en el task pack: cuando una slice toca Flutter, el planner debe incluir route/page, journey refs, endpoints consumidos, estado cliente/provider, estados UI obligatorios y next action. El checker de wiring valida esos campos en modo nuevo.

## 9. Ahorro estimado de tiempo

No prometas speedups fijos. El DAG produce una cota superior; `Conflict group`, `Write set`, `phase-gate`, `/verify-slice` y `/verify-journey` reducen la ganancia real. Para medir una app concreta:

```bash
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-task-dag.sh --strict
python3 - <<'PY'
import json
r=json.load(open('orchestrator-state/tasks/registry.json'))
dag=r['task_dag']
print('nodes=', len(dag['nodes']), 'edges=', len(dag['edges']), 'waves=', len(dag['topological_levels']))
PY
```

Regla práctica de producción:

- 2 terminales: suele ser el punto seguro inicial.
- 3-4 terminales: solo si `/next-wave` no serializa por conflictos.
- 5+ terminales: útil únicamente con lanes muy separadas y reviews humanas preparadas.
- Si una phase supera 20 slices o un step supera 10, divide antes de ejecutar; un fan-in gigante convierte el DAG en una cola.

BASEAPP refactorizada usa lanes pequeñas: ninguna phase supera 20 slices y la matriz DAG queda validada por header, no por posición.

## 10. Cierre y limpieza

El closer debe terminar así:

```text
verify-slice verde
report/evidence/handoff presentes
commit atómico en main
git push origin main
slice-clean
cleanup-worktrees
```

Limpieza segura:

```bash
./scripts/cleanup-worktrees.sh --task <TASK_ID>
./scripts/cleanup-worktrees.sh --task <TASK_ID> --apply
```

`--apply` no borra worktrees dirty ni toca main.

## Follow-ups dentro del DAG

Un hallazgo nuevo no debe romper el grafo ni quedar fuera de memoria. Usa:

```bash
./scripts/register-followup-task.sh list
./scripts/register-followup-task.sh propose --origin-task <TASK_ID> --severity high --kind wiring --title "..." --acceptance "..." --verify "..."
./scripts/register-followup-task.sh promote <FOLLOWUP_ID>
# o, solo con decisión humana explícita:
./scripts/register-followup-task.sh waive <FOLLOWUP_ID> --reason "..."
```

`promote` crea una task con ID canónico en el mismo step/fase, la añade al checklist source-of-truth, genera `work-items/*.yaml` y recalcula la matriz de adyacencia. Las propuestas bloqueantes impiden `/next-wave`, `claim_task.py` y falso `done` del closer hasta resolverse.


## Baseline acumulativo por versiones

`docs/base-app/` no es un seed estático: es el snapshot construido de la app completa hasta el último cierre aceptado. El closer lo sincroniza antes del commit:

```bash
./scripts/sync-product-baseline.sh sync --version <baseapp|v1|v2|current> --task <TASK_ID> --reason "verified slice closed"
```

El manifest `docs/base-app/BASELINE_MANIFEST.json` registra la línea temporal. Al pedir a ChatGPT v2/v3, pásale `docs/base-app/*` para que no pierda contexto y genere docs acumulativos, no diferenciales sueltos.


## Production hardening actual

Usa source-of-truth acumulativo baseline+vN, `Risk level`, `Verify mode`, phases <=20 slices, steps <=10 slices, journeys reales multi-superficie y verify con datos reales/proporcionados. Ejecuta bootstrap + check-task-dag + check-journey-matrix + check-wiring-contract antes de waves.



## Multi-terminal continuation model

DAG parallelism is coordinated through files plus locks, not through live push notifications.

When a task finishes in one terminal:

1. `closer` emits a machine-readable trailer.
2. `hook_capture_subagent_stop.py` validates the role-specific `OUTCOME` / `NEXT_STATUS` against `.claude/orchestrator-contract.json -> trailer_schema.roles`.
3. The hook updates `orchestrator-state/tasks/registry.json` and `runtime-state.json` under lock.
4. `promote_ready_tasks` marks successors `ready` only when all dependencies are `done`.
5. Any terminal can run `./scripts/next-wave.sh --limit <N>` to see the new frontier.

A terminal already running another task keeps going. An idle terminal should rerun `/next-wave` or `./scripts/next-wave.sh`; it will not be interrupted by another terminal's close event.

To continue in the same terminal after a close:

```bash
unset CLAUDE_ACTIVE_TASK_ID CLAUDE_TASK_PACK
./scripts/next-wave.sh --limit 1
# copy the new export
/next-slice <NEXT_TASK_ID>
```

If a successor is still blocked, `claim_task.py` rejects the claim with the missing deps. If it shares `Conflict group` or `Write set` with active work, `/next-wave` serializes it and `claim_task.py` enforces the same decision under lock.
