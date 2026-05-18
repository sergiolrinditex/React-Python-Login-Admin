# OrquestadorDAG AnyStack — orquestador production DAG para aplicaciones fullstack

### PR-flow invariant: next slice must start from integrated main

For `git_workflow: pr-flow`, a closed slice is not `done` just because a PR exists. The closer must run `./scripts/git-workflow.sh`, `pr-flow.sh` must wait until GitHub reports the PR as `MERGED`, and the canonical main checkout must fast-forward to `origin/main`. New task worktrees are cut from the freshly fetched default branch; if local main cannot sync safely, `/next-wave` or `/next-slice` blocks instead of starting work on stale code.


Orquestador para construir aplicaciones fullstack en producción mediante Claude Code, usando cinco documentos source-of-truth, slices verificables, journeys, UX, matriz DAG, memoria en disco, hooks, locks, follow-ups formales y cierre Git estricto.

## Cheat sheet

Para operación diaria rápida, ver [`CHEATSHEET.md`](CHEATSHEET.md). La misma guía está copiada en `docs/guides/CHEATSHEET.md`.

## Modelo mental

```text
ChatGPT Pro rellena templates
  -> 5 docs source-of-truth acumulativos
  -> bootstrap_source_of_truth.py
  -> registry.json local runtime scheduler state + derived views (work-items/*.yaml, task-dag.json/md, execution-graph.json)
  -> /next-wave propone nodos DAG seguros
  -> claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>" ejecuta agentes en un terminal aislado
  -> /verify-slice valida con datos reales/proporcionados
  -> closer genera report + sync baseline + lifecycle-event + commit + configured Git workflow + limpia worktrees
  -> /phase-gate valida phase completa
```

La matriz de adyacencia no se escribe a mano. Se deriva del `Canonical Coverage Registry` del checklist, concretamente de `Depends on`. La fuente runtime canónica del DAG es `orchestrator-state/tasks/registry.json` (`tasks[]` + `task_dag.source_digest`); `task-dag.json`, `task-dag.md` y `execution-graph.json` son vistas derivadas que `./scripts/check-task-dag.sh --strict` compara contra el registry antes de paralelizar. `Conflict group` y `Write set` evitan paralelizar slices que pisan los mismos ficheros o recursos. En workflows PR/worktree, `registry.json` es estado local y no viaja como payload de la slice: el commit incluye `orchestrator-state/tasks/lifecycle-events/<TASK_ID>.json`, y `sync-lifecycle-events.sh --apply` lo rehidrata tras merge/reset.


Nota DAG: los avisos de tamaño de phase/step (`phase >20`, `step >15`) son hygiene/advisory por defecto; `--strict` sigue fallando por errores estructurales del DAG, drift de vistas o dependencias inválidas. Para convertir esos avisos de tamaño en fallo CI, usa `CLAUDE_DAG_ENFORCE_SIZE_BUDGETS=1 ./scripts/check-task-dag.sh --strict` o `--enforce-size-budgets`.

**Production DAG-only**: en operación normal `task_dag.mode` debe ser `explicit_dag`. Si falta `Depends on`, el bootstrap/checker debe bloquear: faltan dependencias reales o el Coverage Registry está incompleto. Corrige los source-of-truth docs y vuelve a ejecutar `bootstrap_source_of_truth.py --refresh`.

**Main thread obligatorio**: Claude Code debe arrancar con `main-orchestrator` como agente principal, no como subagente. El repo fija `.claude/settings.json -> agent: main-orchestrator`, y los comandos operativos usan siempre `claude --agent main-orchestrator --permission-mode bypassPermissions`. No añadas `tools:` al frontmatter de `.claude/agents/main-orchestrator.md`: omitir `tools` es intencional para heredar todas las herramientas disponibles de la sesión, incluidos MCPs y `Agent`; una lista `tools:` sería un allowlist y podría limitar el orquestador.

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"
```


## Multi-terminal DAG: cómo se propaga un cierre

El orquestador no usa notificaciones push entre terminales. La sincronización es por estado en disco y locks:

```text
Terminal A cierra TASK_A
  -> closer emite trailer machine-readable
  -> hook_capture_subagent_stop.py valida OUTCOME/NEXT_STATUS
  -> registry.json TASK_A pasa a done bajo lock
  -> el PR ya trae lifecycle-events/TASK_A.json para reparar ese done tras squash/reset
  -> runtime-state.json se actualiza y ledger.jsonl se mantiene como traza local
  -> promote_ready_tasks desbloquea successors si todas sus deps están done
  -> cualquier terminal vuelve a ejecutar ./scripts/next-wave.sh y ve el nuevo frontier
```

Si Terminal B ya está ejecutando otra task, no se interrumpe. Si Terminal B estaba esperando un successor, debe relanzar:

```bash
./scripts/next-wave.sh --limit 4
```

y copiar el nuevo `export CLAUDE_ACTIVE_TASK_ID=... CLAUDE_TASK_PACK=...`; después lanza `claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"` en ese worker. El `claim_task.py` vuelve a comprobar dependencias, conflictos y write sets bajo lock, por lo que si alguien intenta reclamar demasiado pronto recibe un rechazo seguro en vez de corromper el DAG.

Para continuar desde el mismo terminal después de cerrar una task:

```bash
unset CLAUDE_ACTIVE_TASK_ID
unset CLAUDE_TASK_PACK
unset CLAUDE_WORKTREE_ROOT
unset CLAUDE_ORCHESTRATOR_ROOT
./scripts/next-wave.sh --limit 1
# copiar el export recomendado y lanzar Claude Code así:
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <NEXT_TASK_ID>"
```

Si el cierre genera `JOURNEY_PENDING_VERIFY`, `/next-wave` en DAG-only difiere solo tasks que referencian ese journey pendiente. Los follow-ups bloqueantes impiden abrir nuevas waves/claims hasta promoverlos o waivearlos; no impiden que el PR de la slice se cree si la FU ya está registrada como propuesta formal y entra en el commit. Los conflictos activos sí impiden abrir terminales inseguras.

Los follow-ups productivos no los promueve el closer automáticamente. Si el verify/validator/tester detecta trabajo real fuera de scope, debe quedar como FU `proposed`; el closer la incluye en el report/commit/PR y continúa el cierre sin pedir decisión humana. La decisión posterior de promoción es `/promote-followup <FU_ID>`; el waiver sigue siendo `/register-followup waive <FU_ID>`. Si un promote crea una task que pisa `Conflict group`/`Write set` de una task activa, queda `blocked` hasta que el DAG sea seguro.

**Comando de promoción seguro**: usa `/promote-followup` desde el main-orchestrator, no desde el closer ni desde un worker activo. Si tienes `CLAUDE_ACTIVE_TASK_ID` exportado en ese terminal, primero limpia el entorno o usa una terminal de control:

```bash
unset CLAUDE_ACTIVE_TASK_ID
unset CLAUDE_TASK_PACK
unset CLAUDE_WORKTREE_ROOT
unset CLAUDE_ORCHESTRATOR_ROOT
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"
```

`/promote-followup` lista la FU, muestra plan, pide confirmación literal `PROMOTE <FOLLOWUP_ID>`, ejecuta `./scripts/register-followup-task.sh promote <FOLLOWUP_ID>` bajo locks y después corre checks DAG/wiring.


## Trailer schema y OUTCOME enums

La fuente única de valores de trailer está en:

```text
.claude/orchestrator-contract.json -> trailer_schema.roles.<agent-name>
```

Ahí se declaran `required_keys`, `outcome_values`, `next_status_values`, `info_only` y `mutates_registry_lifecycle`. Es la única fuente machine-readable de trailers; no hay tablas de enums duplicadas ni fallback hardcodeado. `hook_capture_subagent_stop.py` carga `trailer_schema`; si el schema falta o un rol no existe, registra error visible y no muta lifecycle.


## Source-of-truth acumulativo: existing baseline + v1 + v2 + ...

El producto grande se construye por incrementos. `docs/source-of-truth/` siempre contiene la verdad acumulada de la app completa:

```text
v0 ya construida  -> Product increment=v0, Build state=done
producto v1            -> Product increment=v1,      Build state=planned/done
producto v2            -> Product increment=v2,      Build state=planned/done
...
producto vN            -> Product increment=vN,      Build state=planned
```

`docs/product-baseline/` es un snapshot construido opcional: sirve cuando quieres continuar una app ya hecha, pero no es obligatorio para crear una app nueva desde cero. Para una app nueva puedes vaciarlo con `./scripts/reset-for-new-project.sh` y trabajar solo desde los cinco docs vivos de `docs/source-of-truth/`. No es un sitio para notas sueltas: cuando se use como baseline, sólo el closer lo sincroniza desde `docs/source-of-truth/` después de `/verify-slice`; el script verifica el handoff, exige los 5 ficheros modernos y escribe únicamente el snapshot + manifest con:

```bash
./scripts/sync-product-baseline.sh sync --version <v0|v1|v2|current> --task <TASK_ID> --reason "verified slice closed"
./scripts/sync-product-baseline.sh status
```

Este ZIP no trae una baseline de producto por defecto y `docs/source-of-truth/` puede empezar vacío en un checkout nuevo. Para apps nuevas usa `minimal` o `large-without-base`; `docs/product-baseline/` se crea sólo cuando cierres una app/incremento real y quieras planificar v1/v2 conservando contexto.

## Carpetas importantes

```text
docs/templates/        3 perfiles x 5 templates que ChatGPT debe rellenar
docs/prompts/          prompt maestro para generar los documentos source-of-truth sin perder contexto
docs/product-baseline/         baseline construido acumulativo + BASELINE_MANIFEST.json
docs/source-of-truth/  los documentos source-of-truth vivos de la app actual
.claude/               configuración estática: agents, commands, skills, hooks, rules
orchestrator-state/    memoria runtime, tasks, handoffs, evidence, reports, locks
scripts/               wrappers de checks y mantenimiento
```

## Generar o evolucionar una app con ChatGPT

1. Dale a ChatGPT estos ficheros: `docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md`, `docs/guides/CHATGPT_DAG_SOURCE_OF_TRUTH_GUIDE.md`, `docs/templates/<perfil>/*`, `docs/product-baseline/*` si heredas existing baseline y el contexto real del producto.
2. Pide los cinco documentos: `instrucciones.md`, `<APP>_TECHNICAL_GUIDE.md`, `<APP>_IMPLEMENTATION_CHECKLIST.md`, `STACK_PROFILE.yaml` y `UX_CONTRACT.md`.
3. En incrementos v1/v2/vN, exige que conserve el baseline real que le entregues —existing baseline si existe, o el snapshot de tu app actual— con `Build state=done`, y que añada nuevas filas con `Build state=planned`.
4. Copia los source-of-truth docs aceptados en `docs/source-of-truth/`.
5. Ejecuta checks antes de arrancar Claude Code.

Columnas mínimas del Coverage Registry:

```text
Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo
```


### Contrato front→back→DB por task

Cada fila del `Coverage Registry` se copia a la task runtime y al `task-pack` aislado del terminal:

```text
Tipo/Target, Journey refs, Pantalla/Ruta, Endpoint, Tablas DB,
Risk level, Verify mode, Conflict group, Write set,
Origen-Instr, Origen-TechGuide, Acceptance mínimo, Verify mínimo
```

`planner` debe convertir esos campos en un mapa front→back→DB; `developer` debe buscar contratos/ficheros existentes antes de crear nuevos; `validator` y `tester` deben comprobar que la implementación respeta ese mapa. Si falta una pieza fuera del alcance, se crea follow-up formal en vez de dejar notas sueltas.

## Bootstrap y checks obligatorios

```bash
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --validate-only
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh
# --refresh preserva runtime-state/task lifecycle por defecto. Para reset destructivo explícito:
# python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh --reset-runtime-state
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
./scripts/generate-api-contracts.sh --validate-only
```

Resultado esperado en DAG explícito:

```text
Task DAG: OK mode=explicit_dag nodes=<N> edges=<E> waves=<W>
Journey matrix coherent — <J> journeys validadas, 0 drifts
Wiring contract coherent — <R> routes, <E> endpoints, <T> registry rows, <J> journeys
```

Si falta la columna `Depends on` o no está rellena, el bootstrap/checker bloquea. En este orquestador eso es bloqueo de producción: corrige el Coverage Registry y no abras workers hasta volver a `explicit_dag`.

`bootstrap_source_of_truth.py --refresh` es seguro para proyectos activos: preserva `runtime-state.json`, estados de tasks ya existentes, `last_*`, blockers y follow-ups abiertos. Usa `--reset-runtime-state` sólo cuando quieras reconstruir desde cero de forma intencional.


## Contratos API generados

El registry es la fuente de endpoints. En cada `bootstrap_source_of_truth.py --refresh` se genera:

```text
orchestrator-state/tasks/api-contracts/
  openapi.json
  openapi.yaml
  registry-endpoints.json
  frontend/typescript/apiClient.generated.ts
  frontend/<language>/api_client.generated.*
  CONTRACT_MANIFEST.json
```

Valida frescura antes de implementar front/back:

```bash
./scripts/generate-api-contracts.sh --validate-only
```

Si el Coverage Registry cambia y el contrato no se regenera, el check falla por digest. Esto evita drift front↔back.

## Smoke de templates

Para probar que los tres perfiles generan docs, DAG, journeys, wiring, API contracts y frontier:

```bash
python3 -B -S scripts/smoke-template-profiles.py --keep --json
```

El smoke crea dos apps temporales por perfil (`minimal`, `large-without-base`, `large-with-base`) y ejecuta bootstrap, checks DAG/journey/wiring, codegen y `/next-wave` en cada una.

## Ejecución DAG por terminales

```bash
./scripts/next-wave.sh --limit 4
```

El script imprime bloques copiables:

```bash
BOOTSTRAP_ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)}" && ROOT="$(bash "$BOOTSTRAP_ROOT/scripts/ensure-task-worktree.sh" --print-root)" && WT="$(bash "$ROOT/scripts/ensure-task-worktree.sh" P02-S03-T001)" && cd "$WT" && PACK="$WT/orchestrator-state/tasks/task-packs/P02-S03-T001.md" && if [ ! -f "$PACK" ]; then PACK="$ROOT/orchestrator-state/tasks/task-packs/P02-S03-T001.md"; fi && export CLAUDE_ORCHESTRATOR_ROOT="$ROOT" CLAUDE_WORKTREE_ROOT="$WT" CLAUDE_ACTIVE_TASK_ID=P02-S03-T001 CLAUDE_TASK_PACK="$PACK" && echo 'Ahora ejecuta en Claude Code: claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P02-S03-T001"'
```

En ese terminal worker, lanza Claude Code con el orquestador explícito:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P02-S03-T001"
```

Ese `export` vive solo en ese terminal worker. La regla segura es:

```text
1 terminal worker = 1 TASK_ID activo
```

No hagas `unset` al terminar `/next-slice` si vas a verificar la misma task: conserva el mismo `CLAUDE_ACTIVE_TASK_ID` y `CLAUDE_TASK_PACK`, haz `/clear` dentro de Claude Code si necesitas liberar contexto, y lanza la verificación de esa misma slice:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/verify-slice P02-S03-T001"
```

Cuando `/verify-slice` haya ejecutado el `closer` y la task quede cerrada, limpia el terminal antes de reclamar otra task:

```bash
unset CLAUDE_ACTIVE_TASK_ID
unset CLAUDE_TASK_PACK
unset CLAUDE_WORKTREE_ROOT
unset CLAUDE_ORCHESTRATOR_ROOT
```

Cerrar el terminal hace el mismo efecto práctico que `unset`. Si reutilizas la terminal sin limpiar, puedes quedarte con un `TASK_ID` viejo y ejecutar comandos sobre la slice incorrecta.

Para comprobar el contexto activo del terminal:

```bash
printf 'CLAUDE_ACTIVE_TASK_ID=%s\nCLAUDE_TASK_PACK=%s\n' "$CLAUDE_ACTIVE_TASK_ID" "$CLAUDE_TASK_PACK"
```

> En DAG-only, `CLAUDE_ACTIVE_TASK_ID` + `CLAUDE_TASK_PACK` fijan la slice de ese terminal. No hay selector global de tarea/fase en DAG-only.

`claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice ..."` hace:

```text
planner
  -> developer (+ official-docs-researcher si aplica)
  -> validator ‖ tester
  -> debugger si tester falla o validator pide cambios
  -> pausa en tester pass
```

La ruta normal después es:

```text
/clear
/verify-slice P02-S03-T001
```

`/verify-slice` hace hard reset y carga datos reales/proporcionados del `Verification Data Contract`, reproducción humana front→back→DB y, si queda verified, spawnea `closer`. Si encuentra hallazgos menores y dentro del `Write set`, debe llamar a `debugger`, repetir `validator ‖ tester` y relanzar `/verify-slice`; si el hallazgo es mayor o fuera de alcance, registra follow-up formal.

Antes de invocar `closer`, `/verify-slice` valida que el handoff no esté roto:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice
```

Si la task es de pantalla, UX, journey, gate visual o contiene `VISUAL_CONTRACT_CHECK`, `/verify-slice` ejecuta además el reviewer info-only `screen-journey-reviewer` antes de `closer` y exige:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice --require-screen-journey-review
```

Ese reviewer no escribe código ni promueve FU: si detecta un defecto reparable dentro del `TASK_ID`, manda a `debugger/retest`; si falta dato/contrato/ruta fuera de scope, exige FU triageada con `why_not_debugger`. El handoff debe contener resultado machine-readable de `validator`, `tester`, `verify-slice` y, cuando aplique, `Screen/Journey review`. El trailer de chat sincroniza hooks/registry, pero no sustituye al handoff que leerá `closer` tras `/clear`.

El closer hace:

```text
evidence report
sync-product-baseline
commit atómico y workflow Git configurado sin Co-authored-by de Claude
configured Git workflow (`./scripts/git-workflow.sh`)
slice-clean
cleanup-worktrees --apply --task <TASK_ID> --schedule-active
hook marca done solo si REPORT/GIT/PUSH/WORKTREES/BASELINE_SYNC son yes
```

## Datos reales en verificación

Para producción/MVP no se cierra con mocks decorativos. `/verify-slice` y `/verify-journey` deben usar el `Verification Data Contract` del technical guide:

```text
persona/rol real o sandbox
fuente/provisión de datos reales
reset/cleanup
datos persistidos observados
tablas/endpoints/slices vinculados
```

Si faltan datos para verificar una slice, no se inventan: se pide al usuario/equipo que los proporcione o se registra follow-up/bloqueo.

## Follow-ups formales cuando aparece trabajo nuevo

No todo hallazgo merece FU. Primero clasifica:

- **Defecto dentro de la slice**: acceptance ya estaba en el task pack, el arreglo cabe en `Write set`/`allowed_paths` y no requiere nueva ruta/endpoint/tabla/journey/contrato. Va por `validator/tester -> debugger -> retest -> /verify-slice`. No crees FU.
- **Trabajo nuevo fuera de scope**: falta Coverage Registry row, nueva ruta/endpoint/tabla/journey, ampliación de `Write set`/`Conflict group`, datos reales/proporcionados no definidos, dependencia externa o decisión humana. Sí merece FU.

Si `validator`, `tester`, `debugger`, `/verify-slice` o `/verify-journey` descubre trabajo nuevo real fuera del TASK_ID actual, no se queda como nota suelta. Se crea propuesta YAML con triage explícito:

```bash
./scripts/register-followup-task.sh propose \
  --origin-task P02-S03-T001 \
  --severity high \
  --kind ux \
  --scope-classification missing_real_data \
  --why-not-debugger "requiere contrato de datos reales/proporcionados no declarado en el TASK_ID" \
  --title "Estado empty real en ResultsPage" \
  --description "Verify necesita estado empty con datos sandbox persistidos" \
  --product-increment v1 \
  --journey-ref J101 \
  --conflict-group front:results \
  --write-set '<frontend_module_root>/features/<feature>/**' \
  --acceptance "Empty state implementado con datos reales/proporcionados" \
  --verify "/verify-slice observa estado empty con cuenta sandbox persistida"
```

El script rechaza `--scope-classification in_scope_defect` y exige `--why-not-debugger` para `high|critical|blocker`. Esto evita FU spam sin ocultar deuda fuera de scope. Cita siempre los globs de `--write-set` con comillas simples y usa `--journey-ref` sólo si el journey ya existe en `UX_CONTRACT.md`/journey matrix; si el FU crea una journey nueva, no pases `--journey-ref` hasta materializarla en source-of-truth.

Después, con aprobación humana:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"
./scripts/register-followup-task.sh waive <FOLLOWUP_ID> --reason "decisión humana"
./scripts/register-followup-task.sh list --json
```

Las propuestas `high|critical|blocker` bloquean `/next-wave` y claims hasta resolverse, pero no bloquean el cierre/PR de la slice que las originó si ya existen como YAML `proposed` y están staged por `git-add-slice.sh`. El closer nunca hace `promote` automático: registra/incluye las FU propuestas y sigue el PR; la promoción o waiver ocurre después desde main-orchestrator. Al promover con `/promote-followup`, se actualiza source-of-truth, registry, DAG, work-item YAML, runtime y ledger bajo locks. Los Bash PostToolUse van a `orchestrator-state/tasks/bash-ledger.jsonl`, runtime-only e ignorado por Git, para no re-ensuciar el repo tras commit/push. Si la nueva task ya tiene dependencias cumplidas pero su `conflict_group` o `write_set` choca con una task activa/claimed/in_progress, queda `blocked` con `blocked_reason: conflict_with_worker_task`; `promote_ready_tasks` la desbloquea cuando desaparece el conflicto.

## Git workflow

`docs/source-of-truth/STACK_PROFILE.yaml` decide el cierre Git:

```yaml
git_workflow: push-to-main   # alias: direct-main
# o
git_workflow: pr-flow        # requiere feature branch; no vale desde main
```

El closer debe ejecutar siempre `./scripts/git-workflow.sh`. Si el plugin falla, bloquea el cierre; no debe hacer fallback manual a `git push origin main`. `git-workflow.sh` es transporte Git y nunca usa `stash/pop`. El closer debe crear el commit atómico antes de invocarlo; si el workflow sólo detecta trazas tardías permitidas (`ledger.jsonl`, `bash-ledger.jsonl`, `runtime-state.json`), las integra con `git commit --amend --no-edit` antes del push y bloquea cualquier otro path dirty.

Nota DAG importante: el hook `hook_update_ledger.py` escribe eventos Bash en `orchestrator-state/tasks/bash-ledger.jsonl`, runtime-only e ignorado por Git. Así los Bash PostToolUse no re-ensucian el repo después del commit/push. El ledger canónico `ledger.jsonl` queda para eventos lifecycle no-Bash.


## Phase gate

Antes de pasar de phase:

```bash
./scripts/phase-gate.sh P03
./scripts/phase-gate.sh P03 --require-git-clean
```

Bloquea si faltan tasks `done`, handoffs, evidence, reports, journeys verified/waived, follow-ups abiertos o limpieza Git cuando se exige.


### Stack Docker compartido entre worktrees paralelos

`./scripts/next-wave.sh` exporta automáticamente `COMPOSE_PROJECT_NAME` derivado del basename del root canónico. Esto fija el nombre del proyecto Docker Compose para todos los worktrees paralelos, de manera que **todos comparten el mismo stack** (postgres, redis, etc.) en lugar de que cada worktree intente arrancar su propio stack con colisiones de puerto.

Si quieres usar un nombre distinto (por ejemplo para aislar deliberadamente un worktree), exporta `COMPOSE_PROJECT_NAME=<otro>` ANTES de pegar el bloque copy/paste y el bloque respeta tu valor (`${COMPOSE_PROJECT_NAME:-$(basename ...)}`).

## Comandos principales

```text
/next-wave                         lista nodos DAG ready y seguros
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"
                                  ejecuta pipeline hasta tester pass
/verify-slice <TASK_ID>            gate humano + closer si verified
/auto-verify-slice <TASK_ID>       verificación automática solo low+auto y sin cierre de journey
/revise-slice <TASK_ID> "motivo"   corrección sobre slice canónica
/register-followup propose|waive|list  # CRUD bajo nivel
/promote-followup <FU_ID>           # promoción segura vía main-orchestrator
/verify-journey <JID>              journey end-to-end si no se verificó inline
/phase-gate <PHASE_ID>             cierre real de phase
/slice-maintain clean|compact|compact-agent-memory
                                  mantenimiento entre slices y memorias de agentes
```


## Mantenimiento y memoria de agentes

`/slice-maintain compact` compacta `orchestrator-state/memory/PROGRESS.md` y memoria global del proyecto. No toca memorias de agentes.

`./scripts/next-wave.sh` compacta automáticamente memorias de subagentes cuando `orchestrator-state/agent-memory/<agent>/MEMORY.md` supera 250 líneas. Es housekeeping local: archiva el original completo, deja un índice operativo y los snapshots quedan gitignored. Puedes desactivarlo con `CLAUDE_AUTO_COMPACT_AGENT_MEMORY=0` o cambiar el umbral con `CLAUDE_AGENT_MEMORY_COMPACT_THRESHOLD_LINES=<N>`.

Para revisar o ejecutar manualmente:

```bash
python3 -B -S scripts/compact-agent-memory.py --all          # dry-run, umbral 250
python3 -B -S scripts/compact-agent-memory.py --agent developer
python3 -B -S scripts/compact-agent-memory.py --all --apply  # archiva original completo y compacta
```

Contrato: el original completo queda en `orchestrator-state/agent-memory/<agent>/archive/MEMORY.full.<timestamp>.md` antes de reescribir `MEMORY.md`. No toca `.claude/agents/*.md`, `docs/source-of-truth/**`, registry/runtime/task-dag ni artefactos de tasks. Si una memoria cambia mientras se compacta, el script salta ese agente y no pisa la escritura concurrente.

## Seguridad de escrituras

Los agentes leen `.claude/orchestrator-contract.json` y `.claude/rules/05-runtime-write-contract.md`. Los hooks bloquean:

```text
escrituras cruzadas de otro TASK_ID
edición directa de registry/runtime/task-dag; ledger.jsonl es runtime local de sólo append
edición de source-of-truth o baseline snapshot con TASK_ID activo
edición estática de .claude durante ejecución normal
follow-up YAML escrito a mano fuera del script
```

## Reset de proyecto

Solo al cambiar de app y después de pegar los cinco docs source-of-truth nuevos:

```bash
./scripts/reset-for-new-project.sh
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh
```

No borres `orchestrator-state/` entre slices de la misma app: ahí vive la memoria que permite continuar tras `/clear`.



## Onboarding HTML site

Open `site/html-site/index.html` to explain the orchestrator to business and technical stakeholders. The site includes a business view, DAG runtime walkthrough, terminal coordination, commands and trailer outcomes.

## Small app path

For a small app without existing baseline, use `docs/templates/minimal/` plus `docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md`. The minimal profile still produces the same five source-of-truth docs and explicit DAG, but keeps phases small and avoids inherited existing baseline context.


## Stack y UX desacoplados

El orquestador ya no debe asumir un stack concreto. Cada app declara su stack en `docs/source-of-truth/STACK_PROFILE.yaml` y su contrato UX en `docs/source-of-truth/UX_CONTRACT.md`. Los scripts de tokens y Git despachan a plugins (`.claude/enforcers/`, `.claude/git-workflows/`) según ese perfil.


## Stack profile y UX contract

`STACK_PROFILE.yaml` es la fuente única de framework, paths, comandos, enforcer visual y workflow Git. `UX_CONTRACT.md` es la fuente única de personas, pantallas, estados UI y verificación visual/productiva. El motor DAG no debe asumir un stack concreto; si el stack cambia, cambia el profile y el enforcer/plugin, no los hooks.


### Perfiles de templates

`docs/templates/` contiene exactamente tres perfiles, cada uno con cinco ficheros: `minimal`, `large-without-base` y `large-with-base`. Usa `minimal` para MVPs pequeños sin existing baseline; `large-without-base` para productos grandes desde cero y AnyStack; `large-with-base` para evolucionar la existing baseline existente, basada en el STACK_PROFILE.yaml real del baseline existente.


## Documentación visual

- [Pages site (live)](https://slopezrap.github.io/Orquestadorfrontend declaradoDAG-AnyStack/) — overview, negocio, técnico, comandos, DAG, outcomes y stack/UX.
- [Diagramas Mermaid](site/diagrams/) — [arquitectura](site/diagrams/arquitectura.md), [DAG flujo](site/diagrams/dag-flujo.md), [comandos](site/diagrams/comandos.md) y [outcomes](site/diagrams/outcomes.md). 26 diagramas adaptados al modelo AnyStack de 5 documentos source-of-truth (instrucciones + technical guide + checklist + STACK_PROFILE + UX_CONTRACT).
- [Pages site (live)](https://slopezrap.github.io/Orquestadorfrontend declaradoDAG-AnyStack/) servido desde `site/html-site/` vía GitHub Actions.
- [Reports](docs/reports/) — auditorías y validaciones internas. [Guides](docs/guides/) — guías operativas (ChatGPT prompt, DAG runbook).


## Phase / Step / Slice sizing para templates

- **Phase** = milestone o módulo de producto con visión completa; máximo operativo recomendado: `<=20` slices.
- **Step** = lane coherente dentro de la phase: pantalla/journey lane, módulo de dominio, foundation lane o contrato API que alimenta una pantalla nombrada. Objetivo sano: `6-12` slices; máximo: `<=15`.
- **Slice/Task** = unidad ejecutable/verificable por worker, con `Depends on`, `Write set`, `Conflict group`, `Journey refs` y `Verify mínimo` claros.
- No dividas un step coherente sólo por tener 11-12 slices. Divide cuando mezcle lanes no relacionadas, toque write sets incompatibles o pierda trazabilidad de producto.
- La pantalla no se cierra por capas aisladas: cada pantalla importante debe cubrir contrato de pantalla, API/datos, UI conectada, estados UX obligatorios y verificación del journey.
- API/backend slices pueden existir separadas sólo como foundation real o como contrato que alimenta una pantalla/journey nombrado; no hagas `backend completo -> frontend completo -> UX polish`.
- Los templates deben sustituir todos los ejemplos por el dominio real de la app y usar datos reales/proporcionados; si faltan datos, bloquea o registra follow-up.

Git close note: `hook_update_ledger.py` writes Bash PostToolUse events to `orchestrator-state/tasks/bash-ledger.jsonl`, which is runtime-only and ignored by Git. This prevents Bash hooks from re-dirtying the working tree after the atomic commit/push in DAG close. Do not use `git stash` as the normal closer flow; stage required changes into the slice commit before running `./scripts/git-workflow.sh`.
### Limpieza automática de worktrees e identidad Git

En `pr-flow`, el closer no borra la worktree activa antes de que Claude ejecute `SubagentStop`; si lo hiciera, se puede perder el trailer del closer. `cleanup-worktrees.sh` la marca como `active_deferred=1`, registra la limpieza en `orchestrator-state/tasks/cleanup-requests/<TASK_ID>.json` y `scripts/cleanup-deferred-worktrees.sh` la elimina automáticamente desde el Stop hook, y también se reintenta en `scripts/next-wave.sh`/`scripts/ensure-task-worktree.sh` si ya no es la worktree activa. El `DEFERRED_CLEANUP_COMMAND` es sólo fallback; el Stop hook lanza un janitor diferido con reintentos y `next-wave`/`next-slice` reintentan sin intervención manual.

La identidad de commits no está hardcodeada. `scripts/check-git-identity.sh` usa `git config user.name` y `git config user.email`; si quieres exigir una identidad, configura `claude.expectedUserName`/`claude.expectedUserEmail` en Git o exporta `CLAUDE_GIT_EXPECTED_NAME`/`CLAUDE_GIT_EXPECTED_EMAIL`.



### Limpieza diferida de worktrees

Si el closer reporta `active_deferred=1`, no es fallo: protegió los hooks de Claude. La limpieza se reintenta automáticamente al ejecutar `/next-wave` o crear otra worktree, pero sólo borra cuando la task ya está cerrada (`registry.status=done` o lifecycle-event `next_status=done`). Si la PR sigue abierta, la request queda pendiente y no debe ensuciar la wave. Si ya está cerrada pero la worktree sigue dirty, el cleanup no descarta cambios: imprime `DIRTY_STATUS_*` y debes revisar `git -C <worktree> status --short && git -C <worktree> diff --stat` antes de borrar. Fallback manual seguro desde el root canónico, sólo si el janitor no pudo porque la worktree seguía viva/dirty: `bash scripts/cleanup-deferred-worktrees.sh --apply --task <TASK_ID>`.

Además, `/next-wave` ejecuta `scripts/cleanup-closed-task-worktrees.sh --apply --quiet`: borra worktrees limpios y ramas locales `dev/<TASK_ID>`/`feature/<TASK_ID>` de tasks ya cerradas aunque no exista cleanup request. Es el equivalente seguro de `git worktree remove <path>` + `git branch -D dev/<TASK_ID>`, pero sólo si el TASK_ID está `done` por registry/lifecycle-event y la worktree no está activa ni dirty. Manual: `bash scripts/cleanup-closed-task-worktrees.sh --apply --task <TASK_ID> --verbose`.


`/next-wave` también ejecuta `scripts/sync-main-before-wave.sh --apply --quiet` antes de calcular el frontier. Eso hace `git fetch --prune` y fast-forward de `main` a `origin/main` cuando es seguro; si hay cambios dirty no-runtime (por ejemplo `docs/source-of-truth/*`), local-main ahead o divergencia, bloquea la wave en vez de calcular sobre una base vieja. Desactívalo sólo para inspección con `CLAUDE_SKIP_MAIN_SYNC_BEFORE_WAVE=1`.

Además ejecuta `scripts/cleanup-zombie-task-worktrees.sh --apply --quiet`: borra worktrees/ramas locales task-scoped que no tienen patches únicos frente a `origin/main` y no son live según registry. Sirve para cáscaras vacías tras squash merge u old branches equivalentes a main. No borra worktrees dirty, activas, live (`claimed`/`in_progress`/`ready_for_close`/etc.) ni branches con patches únicos. Manual/auditable: `bash scripts/cleanup-zombie-task-worktrees.sh --dry-run --verbose` y luego `--apply`.

También ejecuta `scripts/cleanup-merged-pr-branches.sh --apply --quiet`: borra ramas remotas `origin/dev/<TASK_ID>`/`origin/feature/<TASK_ID>` sólo cuando GitHub confirma que la PR está `MERGED` y el SHA de la rama remota coincide con `headRefOid` de esa PR. PRs abiertas, cerradas sin merge, forks, ramas movidas o ambiguas quedan intactas. Manual/auditable: `bash scripts/cleanup-merged-pr-branches.sh --dry-run --verbose` y, si el plan es correcto, `bash scripts/cleanup-merged-pr-branches.sh --apply --verbose`. Desactívalo en una sesión con `CLAUDE_DISABLE_REMOTE_BRANCH_CLEANUP=1 ./scripts/next-wave.sh` o `CLAUDE_CLEAN_MERGED_PR_BRANCHES=0 ./scripts/next-wave.sh`.

Para limpiar también ramas remotas de PR tras squash-merge en el cierre de la propia slice, `pr-flow.sh` usa `gh pr merge --delete-branch` y, después de confirmar `MERGED`, intenta `git push <remote> --delete <branch>` como fallback idempotente y hace `git fetch --prune`. Recomendado una vez por repo si tienes permisos admin: `bash scripts/configure-github-pr-cleanup.sh` para activar delete-branch-on-merge en GitHub; si reglas/protecciones lo impiden, el cleanup remoto de `/next-wave` hace de janitor conservador.

### Identidad Git y PR squash

El template no hardcodea usuarios. `scripts/check-git-identity.sh --strict` bloquea solo si configuras una expectativa explícita:

```bash
git config --global user.name "<git-user-name>"
git config --global user.email "<email-verificado>"
git config --global claude.expectedUserName "<git-user-name>"
git config --global claude.expectedUserEmail "<email-verificado>"
```

Si los commits aparecen alternando entre cuentas, revisa `git config --show-origin --get-regexp 'user\.|includeIf|gpg|signing|claude\.'`, variables `GIT_AUTHOR_*`/`GIT_COMMITTER_*`, y la cuenta activa de `gh` (`gh auth status`). En `pr-flow`, el squash merge lo ejecuta GitHub vía `gh`; si quieres fijar el email de autor del merge, exporta `CLAUDE_PR_MERGE_AUTHOR_EMAIL=<email-verificado>`.


### Verify-slice human browser MCP gate

`/verify-slice` delegates to `slice-verifier`, which must perform hard reset, load real/provided verification data, exercise the app through a **usable** browser MCP, observe front/back/DB logs, write evidence, and append `## verify-slice`. The priority is Chrome DevTools MCP first, Claude-in-Chrome second fallback, Agent360 Browser MCP (`browser-mcp`) third fallback. `slice-verifier` has `maxTurns: 130` specifically for browser MCP work; keep the global spawn budget at 20 because it counts subagents, not MCP tool calls. Listed tools are not enough: the agent must make a short health call before relying on an MCP. If Chrome DevTools MCP is locked by a stale/active Chrome profile, use `bash scripts/chrome-mcp-doctor.sh || true` plus `scripts/chrome-devtools-isolated-session.sh --task <TASK_ID>` for diagnostics/isolation before trying fallbacks. If no browser MCP is usable it blocks with `browser_mcp_unavailable`; it must not close via API-only fallback. A broken unused MCP does not invalidate a verification already completed through another accepted MCP.

`slice-verifier` has a slightly larger local budget (`maxTurns: 130`) because Chrome DevTools MCP verification is tool-heavy. The global per-slice spawn budget remains 20. Near budget exhaustion the verifier must persist a final blocked handoff with `BLOCKER_REASON: mcp_budget_exhausted_or_scope_too_large`, not leave a partial run.

A verified slice is not closed yet. The lifecycle is:

```text
tester pass -> ready_for_close
slice-verifier verified -> verified_pending_close
closer committed + git/pr/cleanup proof -> done
```

For setup and isolation details see `docs/guides/MCP_BROWSER_VERIFY.md`. Short policy: use Chrome DevTools MCP first for all normal verify work, including MFA/2FA when a visible isolated/per-task Chrome can be used; use Claude-in-Chrome as the second fallback; use Agent360 Browser MCP (`browser-mcp`) as the third fallback for real-session/human-in-the-loop cases when the first two are unusable.

The handoff contract for human `VERIFY_OUTCOME: verified` is intentionally strict: it must include `MCP_BROWSER`, `DATA_CONTRACT_ROWS`, `DATA_SETUP`, `PERSISTED_DATA_OBSERVED`, `FLOWS_TESTED` and `EVIDENCE`. The only no-MCP exception is `VERIFY_MODE: auto` with `RISK_LEVEL: low` and deterministic command evidence. This prevents a thin/partial `verified` block from letting the closer mutate the DAG to `done`.

Handoff fields must be written as plain key lines inside the agent section (`- AGENT: validator`, `- OUTCOME: approved`), not as markdown subheadings like `### AGENT: validator`. The parser tolerates old/bad H3 field lines for recovery, but agents are instructed to write the clean form.

### Inspector read-only para `/next-slice`

`/next-slice <TASK_ID>` reconstruye contexto cada vez. Es normal que, al arrancar dentro de una worktree recién creada, todavía no exista el task-pack/handoff local; el pack puede vivir en el root canónico hasta que `planner` lo materialice. Para evitar snippets frágiles contra `registry.json`, usa:

```bash
ROOT="$(bash scripts/ensure-task-worktree.sh --print-root 2>/dev/null || pwd -P)"
bash "$ROOT/scripts/inspect-task-state.sh" --task <TASK_ID>
```

El schema canónico del registry es `tasks[]` lista, no mapping.

### Janitor diferido con reintentos

Cuando el closer está ejecutándose dentro de la worktree activa, `cleanup-worktrees.sh` no puede borrarla sin arriesgar el trailer `SubagentStop`. Ahora deja una cleanup request y el Stop hook arranca `cleanup-deferred-worktrees-loop.sh`, que reintenta durante una ventana acotada. El comando `DEFERRED_CLEANUP_COMMAND` es fallback, no acción pendiente normal del usuario.


### Learned guardrails

- FU path drift: resolve real files with `find`/`grep`; do not open a second FU just to fix a `write_set` string.
- Duplicate FU: recommend waiver `duplicate_of_done:<id>`; only main-orchestrator/user decides.
- Shared frontend/auth/chat/router/error files require real browser `/verify-slice` evidence before closer; auto verify is for low-risk non-UI/non-shared tasks only.
- Planner must block stale task worktrees as `stale_worktree_dep_missing`; it must not auto-rebase/merge/reset.

### Operational guardrails from lifecycle/FU lessons

Recent framework hardening treats stale worktrees, duplicate follow-ups and shared-file regressions as mechanical risks rather than product follow-ups. `/next-slice` should run `scripts/check-worktree-deps-visible.sh <TASK_ID>` before planning. Validator/tester emit `FU_PROPOSAL` fields; the main orchestrator registers/promotes once and checks duplicates. `git-add-slice.sh` blocks undeclared file deletions and large/structural removals in shared-risk files unless the task declares `delete_set`/`destructive_edit_set`; such shared-risk slices require human browser MCP verification.

### PR/worktree sync invariant

For `pr-flow`, new task worktrees are cut from the newest `origin/main`, not from a stale local `main`. `scripts/next-wave.sh` resolves the canonical repository root even when invoked from a task worktree, fast-forwards canonical `main` to `origin/main` when safe, and then computes the DAG frontier. `scripts/ensure-task-worktree.sh` repeats the same fast-forward check before creating a new `dev/<TASK_ID>` branch, so direct `/next-slice <TASK_ID>` launches do not start from an old base. Existing in-flight task branches are never auto-rebased by planner/next-slice; stale worktrees block and must be reconciled explicitly.

### Follow-up promotion and bootstrap refresh safety

`register-followup-task.sh promote` appends a runtime follow-up as new DAG work; it must not reopen already-closed slices. Bootstrap refresh preserves closer-final tasks as `done` even if their source fingerprint later drifts, records `source_fingerprint_changed_after_done`, and keeps all-done phases as `complete`. If the changed source represents new product work, create/promote a new follow-up instead of mutating the closed slice.

