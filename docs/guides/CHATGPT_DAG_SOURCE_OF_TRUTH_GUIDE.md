# Guía: generar el source-of-truth pack con ChatGPT en modo DAG explícito

Esta guía explica cómo usar ChatGPT para rellenar los cinco documentos canónicos que después ingiere el orquestador:

```text
docs/source-of-truth/instrucciones.md
docs/source-of-truth/<PROJECT>_TECHNICAL_GUIDE.md
docs/source-of-truth/<PROJECT>_IMPLEMENTATION_CHECKLIST.md
```

El objetivo es que el bootstrap genere un grafo DAG explícito, no el modo lineal legacy.

## 1. Qué debe recibir ChatGPT

Entrega a ChatGPT estos ficheros como contexto. El prompt maestro explica cómo leer los templates y cómo hacer la doble verificación documental:

```text
docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md
docs/templates/instrucciones.template.md
docs/templates/PROJECT_TECHNICAL_GUIDE.template.md
docs/templates/PROJECT_IMPLEMENTATION_CHECKLIST.template.md
docs/base-app/instrucciones.md                 # opcional si existe baseline construido
docs/base-app/BASEAPP_TECHNICAL_GUIDE.md       # opcional si existe baseline construido
```

Además, dale el contexto real de la app: usuarios, problema, valor, V1, milestones, integraciones externas, datos sensibles, LLM por defecto, pantallas esperadas, reglas de negocio, restricciones legales y prioridades.


### Perfil minimal para apps pequeñas

Si la app es pequeña y no debe heredar BaseApp, entrega a ChatGPT el mismo prompt maestro pero usa:

```text
docs/templates/minimal/instrucciones.minimal.template.md
docs/templates/minimal/PROJECT_TECHNICAL_GUIDE.minimal.template.md
docs/templates/minimal/PROJECT_IMPLEMENTATION_CHECKLIST.minimal.template.md
```

El resultado sigue siendo el mismo contrato final: cinco documentos completos en `docs/source-of-truth/`, `Coverage Registry` con `Depends on`, `Conflict group`, `Write set`, `Risk level`, `Verify mode`, y bootstrap en `mode=explicit_dag`. La diferencia es el on-ramp: 2-4 phases, 3-8 tasks y 1-2 journeys reales en lugar de un baseline grande.

### Modo incremental baseline + v1 + v2 + ...

Para una aplicación grande, ChatGPT debe recibir también el baseline construido actual si existe. Puede ser BaseApp, una app propia ya construida o ningún baseline si arrancas desde cero:

```text
docs/base-app/instrucciones.md
docs/base-app/*_TECHNICAL_GUIDE.md
docs/base-app/*_IMPLEMENTATION_CHECKLIST.md
docs/base-app/BASELINE_MANIFEST.json
```

Los docs que entregue ChatGPT son **acumulativos**, no diferenciales sueltos: conservan las filas ya construidas (`Build state = done`) y añaden las nuevas filas `v1`, `v2`, etc. con `Build state = planned`. Así el orquestador mantiene journeys, UX, endpoints, DB y matriz DAG completos sin reconstruir lo ya cerrado.


## 2. Entrega por fases, no todo de golpe

Pide a ChatGPT que entregue los documentos uno a uno:

1. `instrucciones.md`.
2. `<PROJECT>_TECHNICAL_GUIDE.md`.
3. `<PROJECT>_IMPLEMENTATION_CHECKLIST.md`.

No aceptes el siguiente documento hasta revisar el anterior. El tercer documento es el más crítico para DAG porque contiene el `Canonical Coverage Registry`.

## 3. Regla que activa el modo DAG no legacy

El modo DAG se activa solo si el Coverage Registry del checklist contiene una columna de dependencias con uno de estos nombres:

```text
Depends on
Dependencies
Deps
After
Blocked by
Dependencias
```

La plantilla estándar usa `Depends on`. Todas las filas deben rellenarla:

```text
—                         root real, no tiene predecessor
P02-S01-T001              depende de una task exacta
P02-S01-T001..T004        depende de un rango de tasks del mismo step
P02-S01                   depende de todas las tasks de un step
P02                       depende de todas las tasks de una phase
previous                  conserva orden local cuando no se puede paralelizar
```

Si la columna falta, el bootstrap crea `mode=legacy_linear`. Si la columna existe pero todo usa `previous`, será DAG explícito pero sin ahorro útil.

## 4. Columnas mínimas del Coverage Registry

El checklist debe incluir esta tabla con la primera columna exacta `Slice ID` y estas columnas mínimas en este orden:

```text
Slice ID
Tipo
Target
Step
Product increment
Build state
Risk level
Verify mode
Depends on
Conflict group
Write set
Journey refs
Pantalla/Ruta
Endpoint
Tablas DB
Origen-Instr
Origen-TechGuide
Acceptance mínimo
Verify mínimo
```

Estas columnas permiten que el planner construya el task pack sin adivinar:

- `Risk level` y `Verify mode` deciden si una slice puede usar `/auto-verify-slice` (`low + auto` y sin cierre de journey) o necesita `/verify-slice` humano.
- `Depends on` alimenta la matriz de adyacencia del DAG.
- `Conflict group` y `Write set` evitan paralelizar slices que comparten ficheros, routers, providers, migraciones, workflows o dependencias globales.
- `Journey refs` conecta slices con journeys.
- `Pantalla/Ruta`, `Endpoint` y `Tablas DB` evitan pantallas, endpoints o tablas huérfanas.
- `Origen-Instr` y `Origen-TechGuide` apuntan a las secciones exactas de los otros dos docs.
- `Acceptance mínimo` y `Verify mínimo` se convierten en checklist ejecutable de cada task.

## 5. Cómo diseñar dependencias y conflictos para paralelizar bien

Usa dependencias reales, no decorativas. Una task debe depender de otra solo si necesita su output para implementarse o verificarse. Usa `Conflict group`/`Write set` para otro problema distinto: dos tasks pueden ser independientes en el DAG, pero no deben ejecutarse a la vez si pisan los mismos ficheros o recursos globales.

Patrón recomendado:

```text
P00 roots en paralelo: scaffold, design tokens, scripts dev cuando no pisan los mismos ficheros.
P01 auth/base data: secuencial donde haya migraciones o contratos compartidos.
P02 motor: migraciones root -> endpoints/use cases en paralelo -> AI/tools/RAG que dependan de contratos.
P03 front: pantallas dependen de endpoints que consumen; pantallas independientes pueden ir en paralelo.
Journey slices: dependen de todas las pantallas/endpoints que componen el journey.
P04 harden: depende de journeys críticos.
P05 release: depende de P04.
```


Patrón de conflictos recomendado:

```text
Migrations Alembic: Conflict group = db:migrations; Write set = api/alembic/versions/**
Router Flutter:     Conflict group = router;        Write set = app/lib/core/router.dart
Theme/design:       Conflict group = theme;         Write set = app/lib/core/theme/**
Deps Python/Dart:   Conflict group = dependencies;  Write set = api/pyproject.toml; app/pubspec.yaml
Workflow CI:        Conflict group = ci;            Write set = .github/workflows/**
```

`/next-wave` usa esos campos para proponer solo terminales seguros. `claim_task.py` repite la validación para que un claim manual no pueda pisar una task ya activa.

Para un join, declara todos los predecessors:

```text
| P03-S04-T001 | journey | J101 e2e | Step 3.4 | P03-S01-T001, P03-S02-T001, P03-S03-T001 | J101 | ... |
```

El orquestador no desbloquea ese nodo hasta que **todos** esos predecessors estén `done`.

## 6. Cableado endpoint/front/journey

Cada endpoint de `TECHNICAL_GUIDE §6.2` debe estar en el checklist como slice `api`, o debe declarar que es `internal/no-front`, `webhook`, `job`, `admin-only` o similar.

Cada endpoint con consumidor UI debe aparecer en al menos una ruta de `TECHNICAL_GUIDE §6.1` o en un journey de `instrucciones.md §3.7`.

Cada ruta de `TECHNICAL_GUIDE §6.1` debe especificar:

```text
ruta GoRouter
Page/Widget
Auth
Journey refs
Endpoints consumidos
Estado cliente/provider
Estados UI obligatorios: loading, empty, error_network, error_validation, permission_denied, success
Next action
Slice ID
```

Estos campos UX no son decorativos: el planner los copia al task pack y `check-wiring-contract.sh --strict --require-new-template-columns` los valida para que una pantalla no llegue al developer sin journey, endpoint, estados o siguiente acción.

Cada journey debe cruzar dos o más pantallas y referenciar rutas, endpoints, tablas y slices existentes.

## 7. Copiar los documentos al sitio canónico

Cuando los cinco documentos estén aceptados, guárdalos aquí:

```text
docs/source-of-truth/instrucciones.md
docs/source-of-truth/<PROJECT>_TECHNICAL_GUIDE.md
docs/source-of-truth/<PROJECT>_IMPLEMENTATION_CHECKLIST.md
```

Debe haber exactamente un `instrucciones.md`, un `*_TECHNICAL_GUIDE.md` y un `*_IMPLEMENTATION_CHECKLIST.md` en `docs/source-of-truth/`.

## 8. Ingesta y checks obligatorios

Ejecuta:

```bash
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
```

Resultado esperado para DAG explícito:

```text
Three-doc contract is valid.
Bootstrapped project prefix: <PROJECT>
Task DAG: OK mode=explicit_dag nodes=<N> edges=<E> waves=<W>
Journey matrix coherent — <J> journeys validadas, 0 drifts
Wiring contract coherent — <R> routes, <E> endpoints, <T> registry rows, <J> journeys
```

Si ves `mode=legacy_linear`, vuelve al checklist y añade/rellena `Depends on`.

## 9. Qué genera el bootstrap

El bootstrap escribe estado derivado, no fuente de verdad:

```text
orchestrator-state/tasks/registry.json              fuente runtime canónica: tasks[] + task_dag.source_digest
orchestrator-state/tasks/runtime-state.json         estado runtime
orchestrator-state/tasks/work-items/*.yaml          work items por task
orchestrator-state/memory/task-dag.json             vista derivada: adjacency_index + adjacency_matrix + levels
orchestrator-state/memory/task-dag.md               vista derivada: waves legibles
orchestrator-state/memory/execution-graph.json      vista derivada: grafo de journeys/slices/docs
orchestrator-state/memory/PROGRESS.md               snapshot vivo inicial
```

No edites estos ficheros a mano salvo para debug. Si cambia el orden del DAG, edita el Coverage Registry y vuelve a ejecutar bootstrap. `check-task-dag --strict` compara las vistas contra `registry.task_dag.source_digest` para detectar refreshes incompletos.

## 10. Ejecutar en terminales como Airflow

Pide la wave actual:

```bash
./scripts/next-wave.sh --limit 4
```

El script imprime comandos copy/paste de este estilo:

```bash
export CLAUDE_ACTIVE_TASK_ID=P02-S03-T001 CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P02-S03-T001.md && echo 'Ahora ejecuta en Claude Code: /next-slice P02-S03-T001'
```

Abre un terminal por task ready. En cada terminal:

```bash
export CLAUDE_ACTIVE_TASK_ID=<TASK_ID> CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md
# dentro de Claude Code:
/next-slice <TASK_ID>
```

`/next-slice` hace el claim atómico después del plan humano. El planner enriquece `orchestrator-state/tasks/task-packs/<TASK_ID>.md`. Developer, official-docs-researcher, validator, tester y debugger deben leer ese pack por task, no el singleton legacy `orchestrator-state/memory/active-task.md`.

## 11. Cierre de cada nodo

El cierre correcto de una task es:

```text
planner
  -> developer || official-docs-researcher
  -> validator || tester
  -> debugger loop si falla
  -> tester pass
  -> /clear opcional
  -> /verify-slice
  -> closer
  -> commit atómico y workflow Git configurado
  -> configured Git workflow (`./scripts/git-workflow.sh`)
  -> slice-clean
  -> cleanup-worktrees
  -> task done
  -> successors desbloqueados si todos sus deps están done y no hay conflicto activo
```

El closer no debe marcar `done` sin handoff, validator pass, tester pass y `VERIFY_OUTCOME: verified` o waiver explícito. Si el push falla o quedan worktrees sucios, el cierre queda bloqueado.

## 12. Phase gate antes de avanzar

Al terminar una phase, ejecuta:

```bash
./scripts/phase-gate.sh P03
# o, si quieres verificar Git además:
./scripts/phase-gate.sh P03 --require-git-clean
```

El gate exige que todas las tasks de la phase estén `done`, que sus reports/evidence/handoffs existan, que no queden `pending_journey_verifications`, y que los journeys cerrados por esa phase estén `verified` o `waived`. Si falla, no abras la siguiente phase aunque el DAG tenga nodos ready.

## 13. Diferencia entre legacy y DAG explícito

Legacy:

```text
Coverage Registry sin Depends on
bootstrap => mode=legacy_linear
una sola cadena secuencial
/next-slice sin TASK_ID específico
```

DAG explícito:

```text
Coverage Registry con Depends on relleno
bootstrap => mode=explicit_dag
/next-wave lista nodos ready
varios terminales pueden ejecutar nodos independientes
joins esperan a todos sus predecessors
```

Ambos modos comparten los mismos agentes, hooks, quality gates, memoria y closer. El DAG solo cambia el scheduling y añade packs por task para evitar corrupción entre terminales.


## Contrato de datos reales para verificación

Al rellenar el `TECHNICAL_GUIDE`, incluye la sección `Verification Data Contract`. Cada journey/flow verificable debe declarar persona/rol, datos reales o prod-like, seed/fixture permitido, reset/cleanup y slices vinculados. `/verify-slice` y `/verify-journey` usan esa sección: los mocks solo valen para unit tests o edge cases marcados como `synthetic-edge-case`, no para cerrar slices productivas.


## Production hardening actual

Usa source-of-truth acumulativo baseline+vN, `Risk level`, `Verify mode`, phases <=20 slices, steps <=10 slices, journeys reales multi-superficie y verify con datos reales/proporcionados. Ejecuta bootstrap + check-task-dag + check-journey-matrix + check-wiring-contract antes de waves.


## Contrato front→back→DB en cada fila

Al generar el checklist, cada slice productiva debe poder ejecutarse sin adivinar contexto: la fila debe declarar journey, pantalla/ruta, endpoint, tablas, origen funcional, origen técnico, write set, conflict group, acceptance y verify real/prod-like. El bootstrap copia estos campos a `work-items/*.yaml` y al `task-pack`; si falta el contrato, los agentes deben bloquear o registrar follow-up.
