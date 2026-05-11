# OrquestadorDAG AnyStack — orquestador production DAG para aplicaciones fullstack

Orquestador para construir aplicaciones fullstack en producción mediante Claude Code, usando cinco documentos source-of-truth, slices verificables, journeys, UX, matriz DAG, memoria en disco, hooks, locks, follow-ups formales y cierre Git estricto.

## Cheat sheet

Para operación diaria rápida, ver [`CHEATSHEET.md`](CHEATSHEET.md). La misma guía está copiada en `docs/guides/CHEATSHEET.md`.

## Modelo mental

```text
ChatGPT Pro rellena templates
  -> 5 docs source-of-truth acumulativos
  -> bootstrap_three_docs.py
  -> registry.json canonical + derived views (work-items/*.yaml, task-dag.json/md, execution-graph.json)
  -> /next-wave propone nodos DAG seguros
  -> claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>" ejecuta agentes en un terminal aislado
  -> /verify-slice valida con datos reales/proporcionados
  -> closer genera report + sync baseline + commit + configured Git workflow + limpia worktrees
  -> /phase-gate valida phase completa
```

La matriz de adyacencia no se escribe a mano. Se deriva del `Canonical Coverage Registry` del checklist, concretamente de `Depends on`. La fuente runtime canónica del DAG es `orchestrator-state/tasks/registry.json` (`tasks[]` + `task_dag.source_digest`); `task-dag.json`, `task-dag.md` y `execution-graph.json` son vistas derivadas que `./scripts/check-task-dag.sh --strict` compara contra el registry antes de paralelizar. `Conflict group` y `Write set` evitan paralelizar slices que pisan los mismos ficheros o recursos.

**Production DAG-only**: en operación normal `task_dag.mode` debe ser `explicit_dag`. Si aparece `legacy_linear`, no sigas como si fuera una cola secuencial: faltan `Depends on` reales o el Coverage Registry está incompleto. Corrige los source-of-truth docs y vuelve a ejecutar `bootstrap_three_docs.py --refresh`.

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
  -> runtime-state.json y ledger.jsonl se actualizan
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
unset CLAUDE_ACTIVE_TASK_ID CLAUDE_TASK_PACK
./scripts/next-wave.sh --limit 1
# copiar el export recomendado y lanzar Claude Code así:
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <NEXT_TASK_ID>"
```

Si el cierre genera `JOURNEY_PENDING_VERIFY`, `/next-wave` aplica `journey_gate_mode=frontier` por defecto: difiere solo tasks que referencian ese journey pendiente. `journey_gate_mode=strict` conserva el bloqueo global legacy. Los follow-ups bloqueantes y conflictos activos sí impiden abrir terminales inseguras.

Los follow-ups productivos no los promueve el closer automáticamente. El closer sólo bloquea si hay FU `high|critical|blocker` propuestas para la slice; la decisión explícita de promoción es `/promote-followup <FU_ID>`; el waiver sigue siendo `/register-followup waive <FU_ID>`. Si un promote crea una task que pisa `Conflict group`/`Write set` de una task activa, queda `blocked` hasta que el DAG sea seguro.

**Comando de promoción seguro**: usa `/promote-followup` desde el main-orchestrator, no desde el closer ni desde un worker activo. Si tienes `CLAUDE_ACTIVE_TASK_ID` exportado en ese terminal, primero limpia el entorno o usa una terminal de control:

```bash
unset CLAUDE_ACTIVE_TASK_ID CLAUDE_TASK_PACK
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"
```

`/promote-followup` lista la FU, muestra plan, pide confirmación literal `PROMOTE <FOLLOWUP_ID>`, ejecuta `./scripts/register-followup-task.sh promote <FOLLOWUP_ID>` bajo locks y después corre checks DAG/wiring.


## Trailer schema y OUTCOME enums

La fuente única de valores de trailer está en:

```text
.claude/orchestrator-contract.json -> trailer_schema.roles.<agent-name>
```

Ahí se declaran `required_keys`, `outcome_values`, `next_status_values` y si el rol puede mutar lifecycle. Los mirrors `outcome_enums` y `next_status_enums` se mantienen solo por compatibilidad. `hook_capture_subagent_stop.py` carga primero `trailer_schema`; sus constantes internas son fallback para instalaciones dañadas, no fuente normativa.


## Source-of-truth acumulativo: existing baseline + v1 + v2 + ...

El producto grande se construye por incrementos. `docs/source-of-truth/` siempre contiene la verdad acumulada de la app completa:

```text
v0 ya construida  -> Product increment=v0, Build state=done
producto v1            -> Product increment=v1,      Build state=planned/done
producto v2            -> Product increment=v2,      Build state=planned/done
...
producto vN            -> Product increment=vN,      Build state=planned
```

`docs/product-baseline/` es un snapshot construido opcional: sirve cuando quieres continuar una app ya hecha, pero no es obligatorio para crear una app nueva desde cero. Para una app nueva puedes vaciarlo con `./scripts/reset-for-new-project.sh` y trabajar solo desde los cinco docs vivos de `docs/source-of-truth/`. No es un sitio para notas sueltas: cuando se use como baseline, el closer lo sincroniza desde `docs/source-of-truth/` con:

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
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
# --refresh preserva runtime-state/task lifecycle por defecto. Para reset destructivo explícito:
# python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh --reset-runtime-state
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

Si sale `legacy_linear`, falta la columna `Depends on` o no está rellena. En este orquestador eso es bloqueo de producción: corrige el Coverage Registry y no abras workers hasta volver a `explicit_dag`.

`bootstrap_three_docs.py --refresh` es seguro para proyectos activos: preserva `runtime-state.json`, estados de tasks ya existentes, `last_*`, blockers y follow-ups abiertos. Usa `--reset-runtime-state` sólo cuando quieras reconstruir desde cero de forma intencional.


## Contratos API generados

El registry es la fuente de endpoints. En cada `bootstrap_three_docs.py --refresh` se genera:

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
export CLAUDE_ACTIVE_TASK_ID=P02-S03-T001 CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P02-S03-T001.md && echo 'Ahora ejecuta en Claude Code: claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P02-S03-T001"'
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
unset CLAUDE_ACTIVE_TASK_ID CLAUDE_TASK_PACK
```

Cerrar el terminal hace el mismo efecto práctico que `unset`. Si reutilizas la terminal sin limpiar, puedes quedarte con un `TASK_ID` viejo y ejecutar comandos sobre la slice incorrecta.

Para comprobar el contexto activo del terminal:

```bash
printf 'CLAUDE_ACTIVE_TASK_ID=%s\nCLAUDE_TASK_PACK=%s\n' "$CLAUDE_ACTIVE_TASK_ID" "$CLAUDE_TASK_PACK"
```

`claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice ..."` hace:

```text
planner
  -> developer ‖ official-docs-researcher
  -> validator ‖ tester
  -> debugger si tester falla
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

El handoff debe contener resultado machine-readable de `validator`, `tester` y `verify-slice`. El trailer de chat sincroniza hooks/registry, pero no sustituye al handoff que leerá `closer` tras `/clear`.

El closer hace:

```text
evidence report
sync-product-baseline
commit atómico y workflow Git configurado sin Co-authored-by de Claude
configured Git workflow (`./scripts/git-workflow.sh`)
slice-clean
cleanup-worktrees --apply --task <TASK_ID>
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

Las propuestas `high|critical|blocker` bloquean `/next-wave`, claims y cierre hasta resolverse. El closer nunca hace `promote` automático: si hay FU bloqueante, debe cerrar con `OUTCOME: blocked` / `NEXT_STATUS: blocked` y pedir decisión humana. Al promover con `/promote-followup`, se actualiza source-of-truth, registry, DAG, work-item YAML, runtime y ledger bajo locks. Si la nueva task ya tiene dependencias cumplidas pero su `conflict_group` o `write_set` choca con una task activa/claimed/in_progress, queda `blocked` con `blocked_reason: conflict_with_active_task`; `promote_ready_tasks` la desbloquea cuando desaparece el conflicto.

## Git workflow

`docs/source-of-truth/STACK_PROFILE.yaml` decide el cierre Git:

```yaml
git_workflow: push-to-main   # alias: direct-main
# o
git_workflow: pr-flow        # requiere feature branch; no vale desde main
```

El closer debe ejecutar siempre `./scripts/git-workflow.sh`. Si el plugin falla, bloquea el cierre; no debe hacer fallback manual a `git push origin main`.

## Phase gate

Antes de pasar de phase:

```bash
./scripts/phase-gate.sh P03
./scripts/phase-gate.sh P03 --require-git-clean
```

Bloquea si faltan tasks `done`, handoffs, evidence, reports, journeys verified/waived, follow-ups abiertos o limpieza Git cuando se exige.

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

Para memorias largas de agentes usa el modo explícito:

```bash
python3 -B -S scripts/compact-agent-memory.py --all          # dry-run
python3 -B -S scripts/compact-agent-memory.py --agent developer
python3 -B -S scripts/compact-agent-memory.py --all --apply  # archiva original completo y compacta
```

Contrato: el original completo queda en `orchestrator-state/agent-memory/<agent>/archive/MEMORY.full.<timestamp>.md` antes de reescribir `MEMORY.md`. No toca `.claude/agents/*.md`, `docs/source-of-truth/**`, registry/runtime/task-dag ni artefactos de tasks.

## Seguridad de escrituras

Los agentes leen `.claude/orchestrator-contract.json` y `.claude/rules/05-runtime-write-contract.md`. Los hooks bloquean:

```text
escrituras cruzadas de otro TASK_ID
edición directa de registry/runtime/ledger/task-dag
edición de source-of-truth o baseline snapshot con TASK_ID activo
edición estática de .claude durante ejecución normal
follow-up YAML escrito a mano fuera del script
```

## Reset de proyecto

Solo al cambiar de app y después de pegar los cinco docs source-of-truth nuevos:

```bash
./scripts/reset-for-new-project.sh
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
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
- [Reports](docs/reports/) — auditorías y validaciones internas. [Guides](docs/guides/) — guías operativas (ChatGPT prompt, legacy/DAG runbook).


## Phase / Step / Slice sizing para templates

- **Phase** = milestone o módulo de producto con visión completa; máximo operativo recomendado: `<=20` slices.
- **Step** = lane coherente dentro de la phase: pantalla/journey lane, módulo de dominio, foundation lane o contrato API que alimenta una pantalla nombrada. Objetivo sano: `6-12` slices; máximo: `<=15`.
- **Slice/Task** = unidad ejecutable/verificable por worker, con `Depends on`, `Write set`, `Conflict group`, `Journey refs` y `Verify mínimo` claros.
- No dividas un step coherente sólo por tener 11-12 slices. Divide cuando mezcle lanes no relacionadas, toque write sets incompatibles o pierda trazabilidad de producto.
- La pantalla no se cierra por capas aisladas: cada pantalla importante debe cubrir contrato de pantalla, API/datos, UI conectada, estados UX obligatorios y verificación del journey.
- API/backend slices pueden existir separadas sólo como foundation real o como contrato que alimenta una pantalla/journey nombrado; no hagas `backend completo -> frontend completo -> UX polish`.
- Los templates deben sustituir todos los ejemplos por el dominio real de la app y usar datos reales/proporcionados; si faltan datos, bloquea o registra follow-up.
