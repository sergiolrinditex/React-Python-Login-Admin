# PROMPT MAESTRO — Source of Truth DAG

Usa este prompt con ChatGPT para generar el source-of-truth completo de `docs/source-of-truth/` a partir de los templates de `docs/templates/`. El objetivo es que el orquestador pueda construir una aplicación real en modo DAG: journeys reales, UX, contrato front -> back -> DB, phases pequeñas, slices verificables, matriz de adyacencia derivable, datos reales/proporcionados y evolución acumulativa `v0 + v1 + v2 + ... + vN`.

## 0. Salida obligatoria

Entrega siempre un contrato completo, no un diff parcial. El modo moderno usa cinco documentos:

1. `docs/source-of-truth/instrucciones.md`
2. `docs/source-of-truth/<APP>_TECHNICAL_GUIDE.md`
3. `docs/source-of-truth/<APP>_IMPLEMENTATION_CHECKLIST.md`
4. `docs/source-of-truth/STACK_PROFILE.yaml`
5. `docs/source-of-truth/UX_CONTRACT.md`

Los tres primeros siguen siendo los documentos de producto/técnica/ejecución. `STACK_PROFILE.yaml` desacopla framework, paths, comandos, enforcer visual y workflow Git. `UX_CONTRACT.md` desacopla UX/personas/pantallas/estados/verificación visual. No dejes TODOs. No entregues tablas a medias. No sustituyas el `Coverage Registry` por texto narrativo.

## 1. Elige perfil: large-with-base, large-without-base o minimal

- Usa **large-with-base** cuando el producto hereda `docs/product-baseline/`, conserva versiones previas (`v0 + v1 + v2 + ...`) o debe extender un baseline ya construido. Lee `docs/templates/large-with-base/*.template.*`, incluyendo `STACK_PROFILE.template.yaml` y `UX_CONTRACT.template.md`, conserva lo existente con `Build state=done` y respeta el stack real heredado declarado en STACK_PROFILE.yaml.
- Usa **large-without-base** cuando la app es grande/modular pero empieza desde cero, sin existing baseline. Lee `docs/templates/large-without-base/*.template.*`; no arrastres rutas, endpoints, tablas ni journeys históricos de existing baseline. Declara `Product increment=v1` o el nombre de release inicial y `Build state=planned`.
- Usa **minimal** para apps pequeñas sin existing baseline. Lee `docs/templates/minimal/*.template.*`. Genera el mismo contrato DAG y los mismos 5 source-of-truth docs, pero con 2-4 phases y 3-8 tasks.
- No mezcles existing baseline en una app nueva salvo que el usuario lo pida explícitamente.

## 1.b Ficheros que debes leer

Lee en este orden:

1. `docs/templates/<perfil>/instrucciones.template.md`
2. `docs/templates/<perfil>/PROJECT_TECHNICAL_GUIDE.template.md`
3. `docs/templates/<perfil>/PROJECT_IMPLEMENTATION_CHECKLIST.template.md`
4. `docs/templates/<perfil>/STACK_PROFILE.template.yaml`
5. `docs/templates/<perfil>/UX_CONTRACT.template.md`
6. Si el perfil es `large-with-base`: `docs/product-baseline/*` y `docs/product-baseline/BASELINE_MANIFEST.json`
7. Si existe producto previo: los documentos actuales de `docs/source-of-truth/`, incluyendo `STACK_PROFILE.yaml` y `UX_CONTRACT.md`
8. El contexto real que te dé el usuario sobre la app a construir

El baseline no es obligatorio para todas las apps. Si la app es nueva y no debe heredar existing baseline, no arrastres tablas, endpoints, routes o journeys históricos que no pertenezcan a esa app.

## 2. Cómo leer e interpretar los templates

Los templates son contratos, no sugerencias decorativas.

- Reemplaza todos los placeholders `{{...}}` con contenido real de la app.
- Las líneas `>>> MODELO`, ejemplos y tablas de ejemplo explican el formato; no copies ejemplos como si fueran requisitos reales.
- Las secciones marcadas como `CABLEADO`, `OBLIGATORIO`, `no negociable` o `cero tolerancia` deben cumplirse literalmente.
- Mantén los nombres de columnas requeridas exactamente. El parser es semántico, pero los checkers esperan cabeceras reconocibles.
- No añadas columnas dentro de tablas canónicas salvo que el template lo permita. Si necesitas más contexto, ponlo en una sección narrativa y enlázalo con IDs.
- Todo elemento creado en un doc debe tener wire en los otros docs: journey, pantalla, endpoint, tabla, librería, milestone, slice y task.
- Las secciones append-only de runtime, si existen, deben quedar vacías al generar docs iniciales. Solo el orquestador las rellena cuando QA descubre follow-ups.
- `HEREDADO` significa: conservar y referenciar, no reimplementar.
- `NO APLICA` es válido solo si explicas por qué no aplica.
- `internal/no-front` es válido solo para endpoints internos, jobs o webhooks sin pantalla directa.

## 2.b Cómo interpretar STACK_PROFILE.yaml y UX_CONTRACT.md

`STACK_PROFILE.yaml` es fuente única de stack. No escribas `flutter test`, `pytest`, `app/lib`, `api/src`, `alembic` o `git push origin main` por costumbre: usa el stack real declarado. Si el stack es React/Node/SQLite, los comandos, paths y enforcer deben reflejarlo.

`UX_CONTRACT.md` es fuente única de UX. No escondas pantallas, estados UI, personas o verificación visual dentro de texto técnico. Cada pantalla productiva del technical guide debe poder rastrearse al UX contract y al Coverage Registry.

## 2.c Stack agnóstico

No elijas comandos, paths o enforcers por costumbre. Usa siempre `STACK_PROFILE.yaml`. Excepción deliberada: `large-with-base` debe conservar el stack real del baseline existente declarado en STACK_PROFILE.yaml; no lo reescribas por costumbre.

- El valor público recomendado para tokens visuales es `design_tokens_enforcer: design_tokens_v1`.
- No uses nombres públicos por framework para el enforcer visual; `design_tokens_v1` lee `frontend.framework` y aplica el scanner adecuado internamente.
- Para stacks sin control visual todavía, usa `design_tokens_enforcer: none` de forma explícita.
- `git_workflow` decide si el closer empuja a main (`push-to-main`/`direct-main`), abre PR (`pr-flow`) o usa otro workflow; no hardcodees `git push origin main` en documentos genéricos.

## 3. Áreas funcionales que debes evaluar

Antes de fijar slices, haz library discovery y arquitectura por áreas aplicables. Evalúa al menos seis áreas con criterio real entre estas, marcando `USAR`, `CUSTOM`, `NO APLICA` o `DEFERRED`:

- Frontend del stack declarado: forms y validación, iconografía, componentes UI extra, cache de imágenes, file pickers, chat/streaming AI, charts, animations, layouts responsive, codegen, deep links, date/time avanzado, maps, pagos, push, crash reporting, permissions nativos, almacenamiento offline.
- Backend: procesamiento de documentos/archivos proporcionados, procesamiento multimedia si aplica, HTTP a APIs externas, jobs/queues, email custom, scraping, validaciones específicas, extensiones cripto, observabilidad backend, storage no-proveedor declarado.
- BBDD: extensiones motor DB declarado específicas como `pg_trgm`, `unaccent`, `pgcrypto`, `PostGIS`.
- AI/ML: structured outputs, constrained generation, prompt eval, reference retrieval metrics, token counting, loaders/chunkers específicos.
- Producto/operación: auditoría, métricas, billing, exportación de datos, permisos avanzados, administración, soporte.

Cada decisión `USAR` o `DEFERRED` debe aparecer también en `*_TECHNICAL_GUIDE.md §2.0` y tener una slice de introducción en el `Coverage Registry` cuando se implemente.

## 4. Reglas de producto versionado

Usa este modelo:

- `Product increment=v0` para baseline ya construido.
- `Product increment=v1|v2|...|vN` para incrementos nuevos.
- `Build state=done` para lo ya construido y sincronizado.
- `Build state=planned` para lo que debe entrar en el frontier ejecutable del DAG.
- No reconstruyas `done` salvo revisión explícita.
- Para evolucionar un producto, entrega documentos acumulativos: conserva existing baseline/v1/v2 previos y añade vN.
- Para una app nueva, usa `Product increment=v1` o el nombre del incremento inicial, y no copies existing baseline si no aplica.

## 5. Granularidad DAG de phases, slices y tasks

Diseña para paralelismo seguro, no para una lista secuencial enorme.

- Phase/lane ideal: 6-12 tasks en products grandes; hard advisory cap: 20 tasks per phase.
- Step ideal: 6-12 tasks; hard advisory cap: 15 tasks per step.
- Cada task debe ser pequeña, verificable y con `Write set` concreto.
- Preferencia de diseño: lanes por pantalla/journey, vertical slice o módulo técnico que alimenta una pantalla nombrada cuando eso aumente paralelismo sin pisar ficheros.
- Evita mega-phases, fan-in degenerado y joins de decenas de tasks salvo integración final justificada.
- Evita ciclos. Si A depende de B, B no puede depender directa ni indirectamente de A.
- Un join se desbloquea solo cuando todos sus predecesores están `done`.
- Usa `Conflict group` y `Write set` para proteger router, theme, migrations, deps, state handlers, API clients y ficheros compartidos.

## 6. Journey, UX y contrato front -> back -> DB

Solo llames journey a un flujo real end-to-end o multi-superficie. No infles journeys con tabs, state handlers o features de una sola pantalla.

Cada journey debe declarar:

- pantallas/rutas.
- acciones del usuario.
- endpoints.
- tablas.
- estado cliente/state handler.
- slices implicadas.
- verificación con datos reales/proporcionados.

Cada pantalla productiva debe declarar:

- ruta/page.
- journey refs.
- endpoints consumidos.
- estado cliente/state handler.
- estados UI obligatorios: loading, empty, error, success cuando apliquen.
- next action visible.
- slice ID.

Cada endpoint productivo debe declarar:

- método/path.
- request/response.
- auth.
- errores.
- consumidor front/journey o justificación `internal/no-front`.
- tablas/side effects.
- slice ID.

Cada task productiva debe poder reconstruir esta cadena:

```text
Journey -> Pantalla/Ruta -> Endpoint -> Tabla/Side effect -> Test/Verify
```

## 7. Reglas de Library Discovery

Estas reglas completan las referencias de `instrucciones.template.md §11.0`:

- No dupliques el stack heredado si la app hereda existing baseline.
- `<20 LOC` de código propio: `CUSTOM` gana, no metas librería.
- Una librería debe ahorrar al menos una slice o reducir riesgo material.
- Prioriza librerías con adopción real, mantenimiento reciente y documentación oficial suficiente.
- Para AI/ML, exige mantenimiento especialmente reciente y ejemplo compatible con el stack actual.
- Licencias MIT/BSD/Apache son preferentes. GPL/comercial requieren ADR.
- Backend y frontend no deben inflarse de dependencias. Si introduces una dependencia, justifica qué elimina o simplifica.
- No pinees versiones en `instrucciones.md`; el `official-docs-researcher` confirmará versión exacta en la slice de introducción.

## 8. Cómo rellenar `PROJECT_TECHNICAL_GUIDE.template.md`

La guía técnica debe ser suficientemente concreta para que `planner`, `developer`, `validator` y `tester` no tengan que adivinar.

Incluye:

- stack y library discovery técnico.
- estructura de proyecto esperada.
- arquitectura y flujo de datos.
- rutas/pantallas del stack declarado con endpoints consumidos, estado cliente, estados UI, next action y slice ID.
- endpoints con request/response, auth, errores, consumidor, tablas/side effects y slice ID.
- modelos/tablas nuevos.
- navigation contract.
- verification data contract.
- testing y comandos reales.
- constraints e invariants.
- ADRs cuando haya decisiones no triviales.

## 9. Cómo rellenar `PROJECT_IMPLEMENTATION_CHECKLIST.template.md`

El `Canonical Coverage Registry` es la fuente principal para el DAG. Debe contener estas columnas:

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |

Reglas:

- `Depends on` activa `explicit_dag`; no lo omitas. El resultado esperado de los checkers es `mode=explicit_dag`, siempre `explicit_dag` para docs nuevos.
- `Risk level`: `low|medium|high|critical`.
- `Verify mode`: `auto` solo para low-risk que no cierran journey; `human` para UI, auth, datos, journeys y riesgo medio/alto.
- `Verify mínimo` contiene comandos/evidencia reales. No puede ser solo `auto` o `human`.
- `Conflict group` agrupa recursos lógicos compartidos.
- `Write set` declara patrones de ficheros esperados.
- `Journey refs` debe apuntar a IDs existentes en la Journey Matrix o quedar vacío/`—` si no aplica.
- `Pantalla/Ruta`, `Endpoint` y `Tablas DB` no pueden contradecir la guía técnica.
- Cada fila debe tener acceptance y verify suficientes para cerrar una task en producción.

## 10. Verification Data Contract y datos reales

Incluye en la guía técnica un contrato de datos de verificación:

- Flow/Journey.
- Persona/Rol.
- Datos reales/proporcionados requeridos.
- Carga de datos reales/proporcionados permitida.
- Reset/Cleanup.
- Slices/Journeys cubiertos.

Regla de producción: no cierres verificación con lorem ipsum, mocks decorativos, payloads inventados no persistidos o inserts hechos por el mismo endpoint que se está probando. Para edge cases (`empty`, `error_network`, `permission_denied`, payload inválido), usa datos reales/proporcionados o casos controlados explícitamente etiquetados; si faltan datos, bloquea o registra follow-up.

## 11. Auto-verify y verify humano

Puedes usar `Verify mode=auto` solo si se cumplen todas estas condiciones:

- `Risk level=low`.
- no cierra un journey.
- no toca auth, pagos, PII sensible, permisos, migraciones críticas ni datos destructivos.
- tiene comando determinista en `Verify mínimo`.
- produce handoff y evidence.

Usa `Verify mode=human` para journeys, UX visible, auth, datos reales, integraciones críticas y riesgo medio/alto.


## 12. Runtime esperado en Claude Code

Cada task se ejecuta aislada por terminal. El comando `/next-wave` imprimirá variables como:

```bash
export CLAUDE_ACTIVE_TASK_ID=<TASK_ID> CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md
```

Los documentos que generes deben permitir que `claim_task.py` construya ese `CLAUDE_TASK_PACK` con route, endpoint, tables, journey refs, risk, verify mode, conflict groups, write set y comandos reales de verify.

## 13. Doble verificación documental antes de entregar

Antes de entregar, haz dos revisiones y corrige errores:

1. Revisión de producto: UX, journeys reales, front -> back -> DB, endpoints con consumidores, tablas coherentes, datos reales/proporcionados.
2. Revisión del scheduler: phases pequeñas, slices no gigantes, `Depends on`, `Conflict group`, `Write set`, `Risk level`, `Verify mode`, sin ciclos y sin fan-in degenerado innecesario.

Después verifica mentalmente que estos comandos pasarían:

```bash
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --validate-only
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
```

## 14. Errores prohibidos

No entregues documentos que tengan:

- `Coverage Registry` sin `Depends on`.
- journeys de una sola pantalla inflados como journey end-to-end.
- endpoints sin consumidor o sin justificación `internal/no-front`.
- pantallas sin route/page o sin estado UI.
- tablas mencionadas en un doc y ausentes en los otros.
- `Verify mode=auto` en slices de riesgo medio/alto o que cierren journey.
- `Verify mínimo=auto` o `Verify mínimo=human` como si fuera comando.
- mega-phase con decenas de tasks si puede partirse por pantalla/lane.
- existing baseline copiada a una app que no debe heredarla.


Nota worktree: en proyectos `pr-flow`, `./scripts/next-wave.sh` imprime un bloque que crea/entra en el worktree `dev/<TASK_ID>` antes de lanzar Claude Code. Usa el bloque exacto que imprime; no lances `/next-slice` desde `main` para una task de PR.
