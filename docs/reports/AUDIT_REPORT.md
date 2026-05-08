# Auditoria de produccion del orquestador DAG

Este informe corresponde al paquete final derivado de `OrquestadorFlutter_DAG_PRODUCTION_AUDITED_FINAL_v2.zip`. El objetivo de la auditoria fue comprobar dos veces que el orquestador conserva la informacion funcional del original y que las mejoras DAG no rompen agentes, hooks, comandos, scripts, source-of-truth, memoria runtime, journeys, UX ni verificacion de produccion.

## Estado final

- No falta ningun fichero funcional del orquestador original.
- Los agentes, hooks, comandos, scripts, skills, rules, templates y docs originales se conservan y se han reforzado.
- El DAG runtime tiene una fuente canonica: `orchestrator-state/tasks/registry.json` (`tasks[]` + `task_dag.source_digest`).
- `task-dag.json`, `task-dag.md` y `execution-graph.json` son vistas derivadas; `check-task-dag --strict` detecta drift antes de abrir waves.
- `docs/base-app/` es baseline construido opcional. Para una app nueva puede vaciarse y usar solo `docs/source-of-truth/`; para evolucionar una app se sincroniza desde source-of-truth con `sync-product-baseline`.
- Cada task DAG recibe en su `work-item` y `task-pack` el contrato front->back->DB derivado del Coverage Registry: journey, pantalla/ruta, endpoint, tablas, risk, verify mode, conflict group, write set, acceptance y verify real/prod-like.

## Correcciones finales aplicadas en esta auditoria

### 1. Cableado completo de tasks

Se detecto que el bootstrap generaba tasks validas pero no bajaba todo el cableado del Coverage Registry a cada task runtime. Esto podia dejar a `planner`, `developer`, `validator` y `tester` dependiendo de memoria global en lugar del nodo DAG.

Corregido en `bootstrap_three_docs.py` y `claim_task.py`:

```text
kind
target
journey_refs
route
endpoint
tables
origin_instr
origin_techguide
risk_level
verify_mode
conflict_groups
write_set
allowed_paths
verification_commands
```

Ahora `task-packs/<TASK_ID>.md` incluye una seccion front->back->DB que los agentes deben leer antes de escribir.

### 2. Parser de journeys endurecido

Se detecto que una tabla ajena con cabecera `ID` podia confundirse con una Journey Matrix incompleta. Corregido: `check_wiring_contract.py` solo parsea journeys dentro de la seccion real `Journey Coverage Matrix`.

Tambien se reforzo el parser semantico para aceptar cabeceras bilingues del template:

```text
Pantallas/Screens
Acciones/Actions
Tablas/Tables
Estado cliente/Client state
Verificacion/Verification
```

### 3. Flujo de verify-slice con hallazgos menores

`/verify-slice` queda documentado y actualizado: si encuentra hallazgos menores dentro del scope/write set, llama a `debugger`, repite `validator || tester` y vuelve a ejecutar `/verify-slice`. Si el hallazgo es mayor o fuera de alcance, registra follow-up formal. No se cierra una slice con issues pendientes.

### 4. Agentes alineados con contrato productivo

Se reforzaron instrucciones de `planner`, `developer`, `validator` y `tester` para que miren contratos existentes front->back->DB en ficheros del proyecto antes de crear nuevos, escriban solo dentro de rutas permitidas y documenten el mapa real implementado.

## Cambios de produccion auditados

### Parser y templates

- La `Journey Coverage Matrix` se parsea por cabeceras semanticas, no por posicion.
- El `Coverage Registry` distingue `Verify mode` de `Verify minimo`; no confunde `auto|human` con comandos de verificacion.
- Los templates y prompts exigen `Risk level`, `Verify mode`, `Depends on`, `Conflict group`, `Write set`, UX, endpoints, tablas y datos de verificacion reales/prod-like.
- Las phases y steps tienen presupuesto: phase <= 12 tasks, step <= 10 tasks. `check-task-dag --strict` avisa/falla si se vuelve a crear una mega-phase ingobernable.

### DAG y paralelismo

- `Depends on` deriva matriz de adyacencia, edges, reverse deps y waves topologicas.
- `Conflict group` y `Write set` serializan nodos que podrian pisarse aunque sean independientes en el grafo.
- `claim_task.py` revalida dependencias y conflictos bajo lock para que nadie pueda saltarse `/next-wave`.
- Joins esperan a todos los predecessors `done`, no a un solo predecessor.
- Follow-ups bloqueantes descubiertos por validator/tester/verify bloquean wave/claim/closer hasta promoverse o waivarse.

### Agentes, hooks y escrituras

- Todos los agentes cargan `.claude/orchestrator-contract.json` y `.claude/rules/05-runtime-write-contract.md`.
- El hook `hook_write_scope_guard.py` bloquea escrituras cruzadas de `TASK_ID`, ediciones directas de state derivado y ediciones de source-of-truth durante una slice activa.
- El hook `hook_capture_subagent_stop.py` valida trailers, enums de `OUTCOME`/`NEXT_STATUS`, scope por `CLAUDE_ACTIVE_TASK_ID`, cierre de journeys y guardrail del closer.
- El closer no puede marcar `done` sin `REPORT_READY`, `BASELINE_SYNC_READY`, `GIT_READY`, `PUSH_READY` y `WORKTREES_CLEANED` en `yes`.
- El closer esta instruido a no anadir `Co-authored-by: Claude`, `Generated-by: Claude` ni trailers de coautor IA.

### Verificacion real y auto-verify

- `/verify-slice` y `/verify-journey` deben usar `Verification Data Contract`: persona/rol, datos reales/prod-like, seed/fixture permitido, reset/cleanup y datos persistidos observados.
- `/auto-verify-slice` existe solo para `Risk level=low`, `Verify mode=auto`, comandos deterministas y slices que no cierran journey.
- Slices UI, auth, journeys, endpoints mutantes o riesgo medio/alto siguen pasando por gate humano.

### Evolucion versionada

- `Product increment` y `Build state` permiten representar baseline construido + nuevos incrementos.
- BaseApp viene marcada `done`, por lo que `/next-wave` inicial no reconstruye nada.
- Un incremento nuevo se anade como `v1|v2|...` con `Build state=planned` y dependencies hacia piezas ya construidas.
- `/register-followup` promueve hallazgos reales a tasks del DAG, actualiza source-of-truth y regenera work-items/registry/DAG bajo locks.

## Auditoria 1 — BaseApp incluida

Comandos ejecutados:

```bash
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
./scripts/sync-product-baseline.sh status
```

Resultado:

```text
Three-doc contract is valid.
Bootstrapped project prefix: BASEAPP
Detected phases: 13
Generated tasks: 84
Detected journeys: 8
Task DAG: OK mode=explicit_dag nodes=84 edges=134 waves=8
Journey matrix coherent — 8 journeys validadas, 0 drifts
Wiring contract coherent — 13 routes, 41 endpoints, 84 registry rows, 8 journeys, data_contract=1
Baseline manifest all_in_sync=True
```

Como BaseApp esta construida (`Build state=done`), `/next-wave` devuelve 0 nodos ready. Es correcto: el siguiente frontier aparecera al anadir v1/v2/vN con `Build state=planned`.

## Auditoria 2 — MiniNotes desde templates/source-of-truth

Se creo una app minima `MiniNotes` para validar que el orquestador no depende de BaseApp ni arrastra tablas historicas.

Resultado:

```text
Project prefix: MININOTES
Phases: 3
Tasks: 5
Journeys reales: 1
Endpoints: 2
Routes: 1
Tables: notes only
Edges: 5
Waves: 4
Task DAG: OK mode=explicit_dag
Wiring contract coherent — 1 routes, 2 endpoints, 5 registry rows, 1 journeys, data_contract=1
```

Simulacion runtime realizada:

```text
/next-wave propone P00-S01-T001
claim_task.py crea task-pack con front->back->DB
developer -> validator_tester_pending
validator -> metadata informativa
tester -> ready_for_close
/auto-verify-slice low+auto -> verified
closer falso con PUSH_READY:no -> blocked
closer correcto con REPORT/BASELINE/GIT/PUSH/WORKTREES yes -> done
promote_ready_tasks desbloquea P01
/next-wave serializa endpoints que comparten api:notes/write_set
```

## Tests finales

Ejecutados por lotes para evitar falsos timeouts del harness:

```text
74 passed, 5 warnings
44 passed
43 passed
46 passed
```

Total:

```text
207 passed, 5 warnings
```

Las 5 warnings son de `multiprocessing/fork` en tests de locks. No son fallos funcionales.

Checks estaticos:

```text
python compile OK
settings JSON OK
orchestrator-contract JSON OK
bash -n OK
```

## Auditoria contra el original

Comparacion contra el primer `OrquestadorFlutter.zip`, excluyendo solo caches, bytecode, locks y estado mutable generado:

```text
Original functional files: 92
Final functional files: 155
Missing functional files: 0
```

No falta ningun agente, hook, script, comando, skill, rule, template ni doc funcional original.

## Limitacion externa

No se pudo probar `git push origin main` contra un remoto real porque el entorno no tiene remoto ni credenciales. El contrato si queda protegido: el hook no acepta `done` si `PUSH_READY` no es `yes`, y el closer queda instruido para bloquear si el push falla.


## Auditoría v4 del prompt maestro

`docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md` es el único prompt operativo para generar los tres source-of-truth. Explica cómo leer los templates, cómo preservar contexto acumulativo, cómo declarar BaseApp/vN, journeys, UX, front -> back -> DB, datos reales/prod-like, Risk level, Verify mode, Conflict group y Write set.

## Auditoría final del prompt maestro y permisos de ejecución

Revisión aplicada sobre `docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md`:

- `docs/prompts/` queda con un único prompt operativo.
- El prompt explica cómo leer los tres templates, cómo interpretar placeholders/modelos/secciones obligatorias y cómo generar los tres source-of-truth completos.
- El prompt contiene referencias explícitas a `mode=explicit_dag`, `CLAUDE_TASK_PACK`, `Depends on`, `Risk level`, `Verify mode`, `Conflict group`, `Write set` y el comando `check-wiring-contract.sh --strict --require-new-template-columns`.
- No quedan referencias a prompts obsoletos ni secciones consolidadas duplicadas.
- `docs/CHATGPT_DAG_SOURCE_OF_TRUTH_GUIDE.md` referencia el prompt maestro una sola vez.

Revisión aplicada sobre wrappers:

- `scripts/*.sh` y `.claude/scripts/*.sh` quedan con permiso ejecutable para que los comandos documentados como `./scripts/...` funcionen directamente tras descomprimir.
- Los helpers Python de `.claude/bin/*.py` mantienen shebang y permiso ejecutable, aunque los hooks los llamen mediante `python3 -B -S`.



## Final delta — multi-terminal DAG + trailer schema

- Documented the multi-terminal continuation model: a terminal that closes a task updates registry/runtime/ledger under locks; other terminals see the new frontier by rerunning `./scripts/next-wave.sh`.
- Made `trailer_schema.roles` in `.claude/orchestrator-contract.json` the explicit source of truth for `OUTCOME` and `NEXT_STATUS` values. Legacy `outcome_enums` / `next_status_enums` remain mirrors only.
- Updated `hook_capture_subagent_stop.py` to load `trailer_schema` first and use hardcoded enums only as fallback.
- Updated agents/rules to point at `trailer_schema.roles.<agent-name>` instead of a vague contract reference.

## v7 — Business HTML, minimal template profile and invariant hardening

Changes made surgically on top of `orq_final_v6_terminal_schema.zip`:

- Added `docs/templates/minimal/` for small apps without BaseApp. It still emits the same five source-of-truth docs and the same explicit DAG columns, but guides ChatGPT toward 2-4 phases, 3-8 tasks and 1-2 real journeys.
- Kept the large app templates in `docs/templates/*.template.md` unchanged except for documentation pointers around the profile choice.
- Updated `docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md` to make ChatGPT choose `large-with-base` or `minimal` before generating the five source-of-truth docs.
- Added `site/html-site/` with a business-facing explanation, runtime/DAG walkthrough, terminal coordination, templates page and outcomes page generated from `trailer_schema`.
- Added invariant tests for trailer schema mirrors, agent prompt role references and `CLAUDE.md` agent count.
- Added `planner` and `main-orchestrator` to `trailer_schema.roles` and mirror enums because their prompts reference those schema paths.
- Unified planner spawn-budget wording to `>= spawn_budget`, matching the `hook_spawn_budget.py` deny condition.
- Fixed documentation drift: `CLAUDE.md` now describes variable phases instead of “6 phases”; BaseApp `J5` profile subflows are one journey with sub-bullets; `feature:locale` is treated as a feature sub-area, not a standalone journey.

Validation:

- BaseApp: `mode=explicit_dag`, 13 phases, 84 tasks, 8 journeys, 134 edges, 8 waves.
- Simple/minimal app test: 6 tasks, 1 real journey, explicit DAG, 4 waves.
- Test suite by batches: 216 passed, 5 warnings. Warnings are the known multiprocessing/fork warnings in lock tests.
- Static checks: JSON, Python compile and bash syntax passed.

## Stack/UX decoupling audit — v8

Changes made from `orq_final_v6_terminal_schema.zip` / v7 baseline:

- Added `docs/source-of-truth/STACK_PROFILE.yaml` and `docs/source-of-truth/UX_CONTRACT.md` as optional/modern source-of-truth documents. The bootstrap remains backwards-compatible with 3-doc projects, but production projects should use all five files.
- Added large templates `docs/templates/STACK_PROFILE.template.yaml` and `docs/templates/UX_CONTRACT.template.md`.
- Added minimal templates `docs/templates/minimal/STACK_PROFILE.minimal.template.yaml` and `docs/templates/minimal/UX_CONTRACT.minimal.template.md`.
- Added `.claude/bin/stack_profile.py` for dependency-free profile parsing.
- Converted `scripts/check-design-tokens.sh` into a stack-profile dispatcher.
- Added `.claude/enforcers/design_tokens_v1.sh`, `.claude/enforcers/design_tokens_v1/RULES.md`, `.claude/enforcers/design_tokens_v1.sh`, `.claude/enforcers/design_tokens_v1.sh` and `.claude/enforcers/none.sh`.
- Moved Flutter-specific visual-token rules out of `.claude/rules/01-non-negotiables.md` into the Flutter enforcer rules. The canonical rule is now stack-agnostic.
- Added Git workflow dispatch via `scripts/git-workflow.sh` and `.claude/git-workflows/{push-to-main,pr-flow}.sh`.
- Updated the prompt and docs so ChatGPT can generate either a large app with baseline or a minimal app without BaseApp using the five-doc contract.
- Added tests that prove a MiniReact/Next.js + SQLite source-of-truth passes the same bootstrap/DAG/wiring flow without touching `.claude/` runtime code.

Validation performed:

- BaseApp five-doc bootstrap: `phases=13`, `tasks=84`, `journeys=8`, `edges=134`, `waves=8`.
- MiniReact source-of-truth test: `tasks=3`, `journeys=1`, `mode=explicit_dag`, no historical BaseApp tables.
- Test batches total: `219 passed`, `5 warnings` (known multiprocessing/fork lock-test warnings).


### Perfil large-without-base

Usa `large-without-base` para productos grandes desde cero: mismos templates grandes, sin heredar BaseApp ni arrastrar tablas/endpoints/journeys históricos. Es el punto medio entre `large-with-base` y `minimal`.


## v9 stack-agnostic audit

Partiendo de `orq_v8_stack_ux_plugins.zip` se añadieron tres perfiles de generación:
`large-with-base`, `large-without-base` y `minimal`.

Cambios principales:
- `design_tokens_enforcer` pasa a contrato público agnóstico: `design_tokens_v1` o `none`.
- Los nombres de plugin visual ya no son nombres de framework; `design_tokens_v1` lee `frontend.framework` desde `STACK_PROFILE.yaml`.
- `stack_profile.py` usa defaults neutrales (`none`) y no asume Flutter/Python/Postgres.
- `scripts/check-design-tokens.sh`, `scripts/run-all-tests.sh` y `scripts/setup-from-scratch.sh` leen `STACK_PROFILE.yaml`.
- El template grande se mantiene; el minimal se conserva para apps pequeñas sin BaseApp.
- Se validó BaseApp, app Flutter+Python y app React+Python con el mismo DAG/checkers.

Resultados de auditoría:
- BaseApp: 13 phases, 84 tasks, 8 journeys, 134 edges, 8 waves.
- Simple Flutter+Python: 6 tasks, 1 journey, 6 edges, 4 waves.
- MiniReact+Python: 3 tasks, 1 journey, explicit DAG, sin tablas históricas de BaseApp.
- Tests: 223 passed, 5 warnings conocidas de multiprocessing/fork en tests de locks.


## v10 — AnyStack DAG fixes validated

- Template layout normalized to exactly three profiles: `minimal`, `large-without-base`, `large-with-base`, each with five files.
- `large-with-base` is fixed to the inherited BaseApp stack: Flutter + FastAPI + Postgres/Supabase-compatible. AnyStack remains available for `minimal` and `large-without-base`.
- Added registry-driven API contract generation: OpenAPI JSON/YAML plus TypeScript and Dart frontend stubs under `orchestrator-state/tasks/api-contracts/`.
- Changed journey gating default to `journey_gate_mode=frontier`; strict mode keeps the legacy global block.
- Replaced the design-token stub with a stack-profile dispatcher and a web scanner for React/Next/Vite-style codebases.
- Added template smoke coverage for two apps per profile.
