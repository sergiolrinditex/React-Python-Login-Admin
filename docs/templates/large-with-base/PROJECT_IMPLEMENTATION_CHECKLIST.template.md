# {{APP_NAME}} — Implementation Checklist

> Este fichero es la **fuente ejecutable** para `.claude/bin/bootstrap_three_docs.py`.
> ChatGPT debe devolverlo ya rellenado, sin `.template`, con prefijo real:
> `{{APP_PREFIX}}_IMPLEMENTATION_CHECKLIST.md`.
>
> La base-app ya existe para las apps normales. Para el caso especial `BASEAPP`, este mismo formato se usa en modo bootstrap: Phase 0-5 construyen la base reusable.
>
> Regla clave: **un slice oficial = una unidad verificable**. No usar "sub-slices" narrativos. Si algo necesita seguimiento, debe tener su propio `Slice ID` en el Coverage Registry.

> Perfil: **large-with-base**. Hereda `docs/base-app/` y mantiene stack Flutter + FastAPI + Postgres/Supabase-compatible; no convertir a React/Node.

---

## 🔗 Contrato de Cableado — léelo ANTES de generar el Coverage Registry

> Este documento es el **CONSUMIDOR FINAL** de `instrucciones.md` + `*_TECHNICAL_GUIDE.md`. El bootstrap (`.claude/bin/bootstrap_three_docs.py`) lee el Coverage Registry y genera `orchestrator-state/tasks/work-items/*.yaml` desde ahí. Lo que NO esté aquí, NO se construye — punto.
>
> **Wires ENTRANTES** (cada item de los otros 2 docs DEBE convertirse en ≥1 slice aquí):
>
> | Tipo de slice (Coverage Registry) | Origen en `instrucciones.md`              | Origen en `*_TECHNICAL_GUIDE.md`                  |
> |-----------------------------------|--------------------------------------------|----------------------------------------------------|
> | `db` (migración)                  | §3.1 motor (entities)                     | §10.3 tabla + §6.3 entity                          |
> | `api` (endpoint)                  | §3.1 motor / §3.2 feature                 | §6.2 endpoint                                      |
> | `flutter` (page)                  | §3.2 feature                              | §6.1 ruta + §6.3 DTO Dart                          |
> | `ai` (agent / graph / tool / RAG) | §3.1 motor (componente AI)                | §10.4 pieza AI + smoke                             |
> | `journey` (e2e multi-pantalla)    | §3.6 + §3.7 fila de la matriz             | §6.1 + §6.2 (componen el flujo)                    |
> | `library` (intro de lib)          | §11.0 USAR/DEFERRED                       | §2.0 fila técnica                                  |
> | `setup` / `gate`                  | §4 milestones / phase gates               | §13 milestones técnicos                            |
>
> **Cableado VISIBLE en cada slice**: el Coverage Registry incluye `Journey refs`, `Pantalla/Ruta`, `Endpoint`, `Tablas DB`, `Origen-Instr`, `Origen-TechGuide`, `Conflict group` y `Write set`. El bootstrap copia este contrato a `registry.json`, `work-items/*.yaml` y `task-packs/<TASK_ID>.md`, de modo que `planner`, `developer`, `validator` y `tester` trabajan con el mismo mapa front→back→DB sin depender de memoria global.
>
> **Regla de oro**: cero slices huérfanos (sin origen claro) y cero items huérfanos en los otros 2 docs (sin slice aquí). Si un endpoint está en `§6.2` pero no tiene slice → bug silencioso. Si un slice está aquí pero no tiene origen → drift inverso (slice inventado).
>
> **Cómo saber si está bien cableado**: ejecuta mentalmente la verificación final "Final wiring verification" al final del doc.

---

# Contract v3 — Dynamic Slice Registry

El orquestador funciona mejor cuando el CHECKLIST declara primero los slices canónicos y luego desarrolla los steps. El bootstrap lee todas las tablas cuyo primer encabezado sea exactamente `Slice ID`.

## Granularity policy

Usa esta política para generar los slices dinámicamente desde `instrucciones.md` + `TECHNICAL_GUIDE.md`:

| Tipo de trabajo | Granularidad recomendada | Ejemplo bueno | Ejemplo malo |
|---|---|---|---|
| Endpoint backend | 1 endpoint verificable por slice cuando tiene schema/use case/repository/test/curl/logs propios | `POST /auth/login` | `Auth completa` |
| DB/migration | 1 migración coherente por slice; puede agrupar tablas que nacen juntas y se verifican juntas | `0007_analysis_tables.py` | `Toda la DB de la app` |
| AI | 1 tool / prompt / graph / agent verificable por slice; endpoint + graph juntos solo si es trivial | `contract_analysis_graph smoke` | `Todo el motor AI` |
| Flutter | 1 ruta/page completa por slice, con estados loading/empty/error/success | `AnalysisResultPage` | `Todas las pantallas` |
| Integración | 1 journey end-to-end por slice si solo conecta piezas ya construidas | `J101 upload→analysis→result e2e` | `Toda la app e2e` |
| Config externa | 1 proveedor o área de config por slice | `Google OAuth config` | `Configurar todos los providers y probar todo` |

Reglas prácticas:

- Divide si el slice tiene más de 8-10 criterios de aceptación reales.
- Divide si toca más de 4 zonas fuertes a la vez: DB + backend + AI + Flutter + infra.
- Une si una tarea no tiene verificación independiente.
- Cada `Slice ID` debe tener `Acceptance mínimo` y `Verify mínimo` específicos de esa fila.
- `Verify mínimo` debe referenciar datos reales/proporcionados del `TECHNICAL_GUIDE §Verification Data Contract` cuando la slice sea verificable por UI/API; no cierres con mocks decorativos.
- Las fases ejecutables nunca deben depender de checkboxes genéricos: la tabla de Registry manda y los headings son solo guía humana.
- Para feature-app normal: 20-50 slices suele ser sano. Para `BASEAPP`: 70-100 slices es normal porque construye la plataforma completa.

## Canonical Coverage Registry — OBLIGATORIO

> ChatGPT debe generar las filas reales. Mantén las columnas exactamente con estos nombres mínimos para DAG, paralelismo seguro y cableado: `Slice ID`, `Tipo`, `Target`, `Step`, `Product increment`, `Build state`, `Risk level`, `Verify mode`, `Depends on`, `Conflict group`, `Write set`, `Journey refs`, `Pantalla/Ruta`, `Endpoint`, `Tablas DB`, `Origen-Instr`, `Origen-TechGuide`, `Acceptance mínimo`, `Verify mínimo`.
> Puedes añadir más columnas (`Path`, `Provider`, `Widget`, `Migración`, etc.). El bootstrap seguirá funcionando si la primera columna sigue siendo `Slice ID` (parser por header dict — columnas extra se ignoran sin romper). Si omites `Depends on`, el orquestador cae al modo lineal legacy.
>
> 🧭 **DAG / paralelismo**: `Depends on` es la source-of-truth de dependencias entre slices. Usa `—` para roots; usa `TASK_ID`, rangos (`P03-S02-T001..T004`), step refs (`P03-S02`), phase refs (`P03`) o `previous`. El bootstrap deriva la matriz en `orchestrator-state/memory/task-dag.json`; NO escribas una matriz manual aquí.
>
> 🧱 **Versionado acumulativo**: `Product increment` identifica si la fila pertenece a `baseapp`, `v1`, `v2`, etc. `Build state` indica si el slice ya está construido (`done`) o si pertenece al incremento activo (`planned`/`ready`). Para un producto grande, no borres filas antiguas: conserva `baseapp`/`done` y añade las nuevas filas de `vN`; eso permite que ChatGPT mantenga contexto completo sin obligar al orquestador a reconstruir lo ya cerrado.
>
> 🧱 **Serialización segura**: `Conflict group` y `Write set` son guardrails de concurrencia. Dos slices pueden tener `Depends on` libre y aun así NO deben correr juntas si pisan el mismo router, provider, migración, API client, pubspec/pyproject, workflow o ficheros compartidos. Usa grupos estables (`db:migrations`, `api:auth`, `front:dashboard`, `router`, `theme`, `release`) y patrones de ficheros esperados (`app/lib/core/router.dart`, `api/alembic/versions/**`, `app/pubspec.yaml`). `/next-wave` serializa automáticamente los conflictos y `claim_task.py` bloquea claims manuales conflictivos.
>
> 🧩 **Follow-ups en producción**: si durante `validator`, `tester`, `/verify-slice` o `/verify-journey` aparece trabajo real que no estaba contemplado, NO se deja como nota suelta. Se crea propuesta con `register-followup-task.sh propose` y, si el usuario la aprueba, se promueve a una fila real en `Runtime Follow-up Coverage Registry` con `Depends on`, `Conflict group`, `Write set`, journey, UX y verificación real/proporcionada. Así futuros `bootstrap --refresh` no pierden el trabajo añadido.
>
> 🔗 **Columnas de cableado recomendadas** (`Origen-Instr` + `Origen-TechGuide`): visibles en cada fila para que el `planner` resuelva sin adivinanzas qué motor / feature / endpoint / tabla origina el slice. Sintaxis libre tipo `§3.1#contract-analyzer` o `§6.2#POST-/api/v1/contracts/upload`. Mantén el formato `<sección>#<slug>` para facilitar grep.

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | setup | Bootstrap repo + env | Step 0.1 | v1 | planned | low | auto | — | setup:bootstrap | `.env.example`; `scripts/**`; `api/src/**/health*.py` | — | — | `GET /health` | — | §1.1 | §3#dev-restart | proyecto compila; `.env.example` completo; scripts base ejecutables | `./scripts/setup-from-scratch.sh --check` |
| P02-S01-T001 | db | `0001_{{domain}}.py` | Step 2.1 | v1 | planned | medium | auto | P00-S01-T001 | db:migrations, db:{{table}} | `api/alembic/versions/*{{table}}*`; `api/src/**/{{table}}*.py` | J101 | — | — | `{{table}}` | §3.1#{{component}} | §10.3#{{table}} + §6.3#{{Entity}} | migración up/down; FK cascade; índices en queries críticas | `alembic upgrade head && alembic downgrade -1` |
| P02-S02-T001 | api | `POST /api/v1/{{resource}}` | Step 2.2 | v1 | planned | medium | human | P02-S01-T001 | api:{{resource}} | `api/src/**/{{resource}}*.py`; `api/tests/**/{{resource}}*` | J101 | `{{Resource}}CreatePage /{{resource}}/new` | `POST /api/v1/{{resource}}` | `{{table}}` | §3.1#{{component}} | §6.2#POST-/api/v1/{{resource}} | Pydantic schema; use case; repository; integration test; logs BEFORE/AFTER/ERROR | `pytest api/tests/integration -k {{resource}}_create` + curl con datos reales/proporcionados |
| P02-S04-T001 | ai | `{{graph}}_smoke` | Step 2.4 | v1 | planned | medium | auto | P02-S02-T001 | ai:{{graph}} | `api/src/**/{{graph}}*.py`; `api/tests/**/{{graph}}*` | J101 | — | internal/no-front | `{{ai_table}}` | §3.1#{{component-AI}} | §10.4#{{graph}} | graph compila; smoke con FakeListChatModel verde; logs por nodo | `pytest api/tests/ai -k {{graph}}_smoke` |
| P02-S00-T001 | library | intro `<paquete-X>` en `pyproject.toml` | Step 2.0 | v1 | planned | low | auto | P00-S01-T001 | dependency:{{paquete}} | `api/pyproject.toml`; `uv.lock`; primer consumidor | — | primer consumidor | — | — | §11.0#{{área}} | §2.0#{{paquete}} | lib instalada; primer consumidor refactorizado; lockfile actualizado | `pip install -e . && pytest -k {{first-consumer}}` |
| P03-S01-T001 | flutter | `/{{resource}}/new` `{{Resource}}CreatePage` | Step 3.1 | v1 | planned | medium | human | P02-S02-T001 | front:{{resource}}, router | `app/lib/**/{{resource}}*.dart`; `app/test/**/{{resource}}*`; `app/lib/core/router.dart` | J101 | `{{Resource}}CreatePage /{{resource}}/new` | `POST /api/v1/{{resource}}` | — | §3.2#{{feature}} | §6.1#/{{resource}}/new | page con design system; validación inline; seis estados UI; provider wired; next action | `/verify-slice` en Chrome con backend real y datos proporcionados |
| P03-S02-T001 | journey | `J101` e2e happy path | Step 3.2 | v1 | planned | high | human | P03-S01-T001 | journey:J101 | `orchestrator-state/tasks/evidence/journeys/J101/**` | J101 | `/contracts/upload → /contracts/:id/analysis` | `POST /api/v1/contracts/upload`, `GET /api/v1/contracts/:id/analysis` | `contracts`, `analyses` | §3.6#J101 + §3.7#J101 | §6.1 + §6.2 | flujo multi-pantalla real; datos persistidos; next action visible; estados marginales reproducidos | `/verify-journey J101` |


>>> MODELO: reemplaza las filas de ejemplo por TODAS las filas reales del proyecto.
>>>
>>> 🔗 **Cableado obligatorio por fila**: rellena `Journey refs`, `Pantalla/Ruta`, `Endpoint`, `Tablas DB`, `Origen-Instr`, `Origen-TechGuide`, `Conflict group` y `Write set` en cada fila apuntando al elemento real o `—` cuando no aplique. El contenido se copia al task-pack y guía las escrituras del agente. Si una celda productiva quedaría vacía, el slice probablemente no debería existir. Excepción: filas `setup` puras del Phase 0 pueden apuntar a `§1.1` o `§3` genéricos.
>>>
>>> 🧭 **Dependencias DAG obligatorias**: rellena `Depends on` en TODAS las filas. Usa `—` solo cuando el slice pueda ejecutarse como raíz de su phase/wave. No uses dependencias decorativas: una dependencia debe significar que el output del predecessor es necesario para verificar este slice.
>>>
>>> 🧱 **Guardrails de concurrencia obligatorios**: rellena `Conflict group` y `Write set` en TODAS las filas. Si dos slices tocan el mismo router, provider, migración, workflow, pubspec/pyproject, API client, theme o fichero compartido, deben compartir `Conflict group` o solaparse en `Write set`. Usa `read-only` o `—` solo para slices que no escriben código compartido.
>>>
>>> 🔗 **No dejes slices huérfanos**:
>>> - Cada endpoint de `TECHNICAL_GUIDE §6.2` → slice `api` con columna `Endpoint` igual a `METHOD /path`, y consumidor front/journey declarado si no es interno.
>>> - Cada tabla de `§10.3` → slice `db`.
>>> - Cada pieza AI de `§10.4` → slice `ai` con smoke.
>>> - Cada ruta Flutter de `§6.1` → slice `flutter` (o `journey` si solo existe como integración), con columna `Pantalla/Ruta` que incluya Page + ruta.
>>> - Cada lib USAR/DEFERRED de `instrucciones §11.0` + `§2.0` → slice `library` que la introduce en deps.
>>> - Cada journey de `instrucciones §3.7` → slice(s) que cubren las pantallas + endpoint final con `journey` ID en columna `Journey refs`.

---

# Phase 0 — Bootstrap / inherited base verification

> Feature-app normal: verificar que la base-app template está instanciada con credenciales propias.  
> BASEAPP: construir scaffold backend + Flutter + design system + i18n + showcase.

## Step 0.1 — Project bootstrap

- [ ] Confirmar modo: `feature-app` sobre base-app o `BASEAPP` bootstrap.
- [ ] Si es feature-app: clonar template de base-app, renombrar package IDs/package/app name y limpiar restos del template.
- [ ] Si es BASEAPP: crear scaffold backend `api/` y Flutter `app/` desde cero.
- [ ] `.env.example` completo sin secretos reales.
- [ ] Scripts base ejecutables: `setup-from-scratch.sh`, `dev-restart.sh`, `run-all-tests.sh`.
- [ ] `scripts/dev-restart.sh` implementa `--soft`, `--check`, `--reset`.

## Step 0.2 — Supabase + DB baseline

- [ ] Supabase local/cloud configurado.
- [ ] `DATABASE_URL` usa transaction pooler cuando aplique.
- [ ] Alembic listo con migraciones reversibles.
- [ ] `GET /health`, `GET /live`, `GET /ready` funcionan.

## Step 0.3 — Flutter baseline

- [ ] Flutter Web + Android + iOS compilan.
- [ ] Router base, theme, shared widgets e i18n inicial listos.
- [ ] `/showcase` visible en Chrome con design system profesional.

## Step 0.4 — Phase 0 gate

- [ ] `ruff check api/` zero.
- [ ] `mypy api/src/` zero.
- [ ] `flutter analyze` zero.
- [ ] Tests unitarios/integración de Phase 0 verdes.
- [ ] PROGRESS.md actualizado.

---

# Phase 1 — Auth / base capabilities

> Feature-app normal: smoke de capacidades heredadas con credenciales nuevas.  
> BASEAPP: construir auth, profile, GDPR, admin bootstrap según el registry.

## Step 1.1 — External auth/provider configuration

- [ ] Email/password configurado.
- [ ] Google OAuth configurado si aplica.
- [ ] Apple Sign-In configurado si aplica.
- [ ] Microsoft/Azure OAuth configurado si aplica.
- [ ] Redirect URLs web/mobile documentadas.

## Step 1.2 — Auth BFF/API slices

- [ ] Para cada endpoint auth declarado en el registry: schema, use case, repository/client, router, tests, curl y logs.
- [ ] Web usa cookie `HttpOnly; Secure; SameSite=Lax` para refresh token.
- [ ] Mobile usa secure storage; nunca localStorage.

## Step 1.3 — Auth Flutter slices

- [ ] Login/Register/Forgot/Reset o smoke heredado según modo.
- [ ] Auth state provider, redirects y error states.

## Step 1.4 — Phase 1 gate

- [ ] 4 métodos de login funcionales si están en scope.
- [ ] Admin user configurado para pruebas.
- [ ] Tests acumulados Phase 0-1 verdes.
- [ ] PROGRESS.md actualizado.

---

# Phase 2 — MOTOR / domain backend / AI

> Aquí se construye el valor de la app. Sin UI final salvo herramientas de smoke. Cada componente del motor de `instrucciones.md §3.1` debe tener slices en el Coverage Registry.

> 🔗 **CABLEADO de Phase 2** — los steps aquí son **agrupadores narrativos** del registry; los slices reales (con `Origen-Instr` / `Origen-TechGuide` cableados) viven en el Coverage Registry de arriba. Para CADA componente del motor declarado en `instrucciones.md §3.1`:
>
> - 1 slice `db` por tabla nueva → cablea a `§10.3#<tabla>` + `§6.3#<Entity>`.
> - 1 slice `api` por endpoint del componente → cablea a `§6.2#<METHOD-/path>`.
> - 1 slice `ai` por agent / graph / deep_agent / tool / RAG loader (con smoke test) → cablea a `§10.4#<pieza>`.
> - Slices `library` para libs no instaladas todavía → cablean a `§11.0#<área>` + `§2.0#<paquete>`.
>
> Si un componente del motor en `§3.1` no tiene NINGÚN slice aquí, no existe en código. Si un slice aquí no apunta a un componente real de `§3.1`, drift inverso.

>>> MODELO: generar steps reales. Normalmente 3-8 steps. Cada step agrupa slices del registry, pero NO sustituye al registry.

## Step 2.1 — Data model and migrations

- [ ] Implementar las migraciones declaradas en TECHNICAL_GUIDE §10.3 y en el Coverage Registry.
- [ ] Cada migración tiene up/down probado.
- [ ] FKs, índices y constraints reflejan invariantes del dominio.

## Step 2.2 — Domain + repositories + use cases

- [ ] Entities de dominio puras.
- [ ] Repository interfaces en domain.
- [ ] SQLAlchemy models e implementations en infrastructure.
- [ ] Use cases con tests unitarios y logs BEFORE/AFTER/ERROR.

## Step 2.3 — API endpoints

- [ ] Cada endpoint de TECHNICAL_GUIDE §6.2 tiene slice propio o justificación explícita de agrupación.
- [ ] Pydantic schemas tipados.
- [ ] Auth/rate limit/audit log según criticidad.
- [ ] Integration tests contra Supabase real.
- [ ] Curl reproducible.

## Step 2.4 — AI components, if any

- [ ] Tools/prompts/agents/graphs/deep_agents declarados en TECHNICAL_GUIDE §10.4.
- [ ] Tests deterministas con FakeListChatModel o equivalente.
- [ ] Smoke command real para cada graph/agent.
- [ ] official-docs-researcher verifica versiones/imports antes de implementar.

## Step 2.5 — Phase 2 gate

- [ ] Todo endpoint del motor responde por curl con payload realista.
- [ ] DB contiene filas verificables.
- [ ] Logs sin PII/secrets.
- [ ] Tests backend acumulados verdes.
- [ ] PROGRESS.md actualizado.

---

# Phase 3 — FEATURES / Flutter UX

> Cada feature de `instrucciones.md §3.2` se expone visualmente. Cada ruta de TECHNICAL_GUIDE §6.1 debe tener slice propio o formar parte de un journey slice claramente declarado.

> 🔗 **CABLEADO de Phase 3** — los steps aquí agrupan slices del registry. Para CADA feature de `instrucciones.md §3.2`:
>
> - 1 slice `flutter` por pantalla → cablea a `§3.2#<feature>` + `§6.1#<ruta>`.
> - Cada slice `flutter` cubre los 6 estados marginales explícitamente: loading / empty / error_network / error_validation / permission_denied / success.
> - 1 slice `journey` por flujo end-to-end de `instrucciones.md §3.7` → cablea a `§3.6#<JID>` + `§3.7#<JID>`. Solo se construye CUANDO todas las pantallas y endpoints del flujo ya tienen slice y están cerrados.
>
> Si una feature de `§3.2` no tiene NINGÚN slice `flutter` aquí, no se construye pantalla. Si un journey de `§3.7` no tiene slice `journey` aquí, `/verify-journey` no tiene cómo lanzarse.

>>> MODELO: generar phases/lanes reales por milestone/pantalla/módulo. Producción: phase <=20 slices y step <=10 slices; si una fase crece más, divídela en lanes independientes para mantener paralelismo real.

## Step 3.1 — Primary route/pages

- [ ] Pages principales con design system heredado.
- [ ] Riverpod providers / state notifiers conectados al API client.
- [ ] Estados loading, empty, error_network, error_validation, permission_denied, success.
- [ ] Next action después de cada success.

## Step 3.2 — Journey integration

- [ ] Cada journey J101+ de instrucciones §3.7 se puede recorrer en Chrome.
- [ ] Back behavior, deep links y empty/error states verificados.
- [ ] `/verify-journey JXXX` preparado para cada journey.

## Step 3.3 — Phase 3 gate

- [ ] `flutter analyze` zero.
- [ ] Widget tests verdes.
- [ ] E2E/smoke Chrome para cada milestone.
- [ ] Screenshots/evidence guardados en handoff.
- [ ] PROGRESS.md actualizado.

---

# Phase 4 — Hardening specific to this app

## Step 4.1 — Security, observability and performance

- [ ] Audit actions específicas del dominio.
- [ ] Rate limits en endpoints caros.
- [ ] Métricas y logs del motor.
- [ ] Performance smoke sobre dataset real proporcionado por el usuario/equipo.

## Step 4.2 — Phase 4 gate

- [ ] Tests acumulados verdes.
- [ ] Security checks sin findings críticos.
- [ ] PROGRESS.md actualizado.

---

# Phase 5 — Release

## Step 5.1 — Build and release readiness

- [ ] `flutter build web` OK.
- [ ] Docker/backend build OK si aplica.
- [ ] Env vars documentadas.
- [ ] Rollback plan específico si aplica.

## Step 5.2 — Final acceptance

- [ ] Todos los journeys verificados.
- [ ] All tests green.
- [ ] README de app actualizado.
- [ ] Tag/release preparado.

---

# Final wiring verification — OBLIGATORIO

> 🔗 **Antes de devolverme este CHECKLIST, recorre TODA esta verificación**. Esta es la última red de seguridad: si algún wire falla aquí, llega roto al bootstrap, al `planner` y al pipeline. Falla en silencio (slices generados a medias / journeys huérfanos) y se descubre tarde, normalmente en `/verify-journey` cuando ya hay 5-10 slices invertidos.

## A. Wires ENTRANTES — todo identifier de los otros 2 docs tiene slice

### A.1 Desde `instrucciones.md`

- [ ] Cada **componente del motor** de `§3.1` tiene 1+ slice `db`, 1+ slice `api`, y (si aplica) 1+ slice `ai` en el Coverage Registry.
- [ ] Cada **feature** de `§3.2` tiene 1+ slice `flutter` en el Coverage Registry.
- [ ] Cada **journey** de `§3.7` referencia slices existentes en columna `Slices` (verificable expandiendo `P0X-S0Y[-T00Z]`).
- [ ] Cada **milestone** de `§4` tiene su grupo de slices Phase 2 + Phase 3 cableados.
- [ ] Cada **decisión USAR / DEFERRED** de `§11.0` tiene 1 slice `library` que la introduce en deps.
- [ ] Cada **estado marginal** de `§3.2` (loading/empty/error_network/error_validation/permission_denied/success) está cubierto por la `Acceptance mínimo` del slice `flutter` correspondiente.

### A.2 Desde `*_TECHNICAL_GUIDE.md`

- [ ] Cada **lib USAR / DEFERRED** de `§2.0` tiene slice `library` (su ID coincide con la columna "Introducida en slice").
- [ ] Cada **ruta** de `§6.1` tiene slice `flutter` o aparece como paso de un slice `journey`.
- [ ] Cada **endpoint** de `§6.2` tiene slice `api` propio (excepción documentada en agrupaciones de integración).
- [ ] Cada **entity** de `§6.3` tiene tabla en `§10.3` con su slice `db` correspondiente.
- [ ] Cada **tabla** de `§10.3` tiene slice `db` (puede agruparse con tablas que nacen juntas).
- [ ] Cada **agent / graph / deep_agent / tool / RAG loader** de `§10.4` tiene slice `ai` con smoke test.
- [ ] Cada **milestone** de `§13` agrupa slices reales (no decorativo).

## B. Wires SALIENTES — cada slice tiene origen real

Recorre cada fila del Coverage Registry y verifica:

- [ ] Tiene `Origen-Instr` rellenado y la sección apuntada existe en `instrucciones.md`.
- [ ] Tiene `Origen-TechGuide` rellenado y la sección apuntada existe en `*_TECHNICAL_GUIDE.md` (excepción legítima: `setup` de Phase 0, `gate` de phase gates, donde `Origen-TechGuide` puede ser genérico `§3` o `§13`).
- [ ] Si la fila tiene `Tipo = api` → la columna `Path` o `Target` coincide con un endpoint de `§6.2` exacto.
- [ ] Si la fila tiene `Tipo = db` → el `Target` coincide con una migración nombrada `000N_<feature>.py` y la tabla existe en `§10.3`.
- [ ] Si la fila tiene `Tipo = flutter` → el `Target` coincide con `<Page>` y la ruta existe en `§6.1`.
- [ ] Si la fila tiene `Tipo = ai` → el `Target` coincide con un agent / graph / tool de `§10.4`.
- [ ] Si la fila tiene `Tipo = library` → la lib existe en `§2.0` con misma área que `§11.0`.
- [ ] Si la fila tiene `Tipo = journey` → todos los slices que la componen ya tienen filas previas en el registry.

## C. Wires de la Journey Coverage Matrix (`instrucciones.md §3.7`)

Para CADA fila de la matriz:

- [ ] Tiene ≥2 pantallas y todas existen en `§6.1` (TECHNICAL_GUIDE).
- [ ] Cada endpoint de la celda existe en `§6.2`.
- [ ] Cada tabla de la celda existe en `§10.3`.
- [ ] La columna `Slices` se expande a `Slice ID`s reales del Coverage Registry de este doc.
- [ ] Aparece 1 slice `journey` con ese `JID` en columna `Journey refs` y verify `/verify-journey JXXX`.
- [ ] Separadores correctos: `→` en pantallas, coma + espacio en endpoints/tablas/estado/slices, `\|` para pipes literales, sentinels `(none)` o `—` para celdas sin contenido.

## D. Phase gates y orden

- [ ] Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 (orden estricto).
- [ ] `P00..PNN` coherentes — cada phase usada por el registry existe como heading o wrapper sintético válido, y ninguna phase supera 20 slices ni ningún step supera 10.
- [ ] Cada Phase Gate al final del Phase tiene tests acumulados verdes como criterio.
- [ ] `dev-restart.sh` con `--soft` / `--check` / `--reset` está documentado en `TECHNICAL_GUIDE §3` (lo invocan `/next-slice` y `/verify-slice`).

## E. Drift checks — cero tolerancia

- [ ] **Cero `>>> MODELO:`** restantes en el fichero filled.
- [ ] **Cero referencias** a `Slice ID`s que no existan (busca con `grep` en este doc tras rellenar).
- [ ] **Cero referencias** a `§Xs` de `instrucciones.md` o `TECHNICAL_GUIDE` que no existan.
- [ ] **Coverage Registry header** sigue empezando exactamente por `| Slice ID |` (lo que el bootstrap parsea).
- [ ] Si se usa DAG, cada fila tiene `Depends on` correcto y `./scripts/check-task-dag.sh --strict` retorna 0.
- [ ] Las columnas extra `Origen-Instr` / `Origen-TechGuide` están rellenas en TODAS las filas del registry (no solo en las de ejemplo).

## F. Última prueba mental antes de entregar

1. **¿Si el `planner` selecciona el primer slice `api` y sigue `Origen-TechGuide` → encuentra contrato técnico completo en una sola sección?** Si rebota entre 3 secciones, falta detalle en TECHNICAL_GUIDE.
2. **¿Si el `bootstrap_three_docs.py` parsea este registry, genera tantos `work-items/*.yaml` como features + endpoints + tablas + AI pieces declarados en los otros 2 docs?** Cuenta las filas y compara: si faltan, hay items huérfanos.
3. **¿Si un slice de Phase 3 falla en `/verify-journey`, puede el `debugger` rastrear el `Origen-Instr` y `Origen-TechGuide` para entender qué se rompió?** Si los punteros llevan al vacío, el cableado es decorativo.

Si las 3 son "sí", entrega. Si alguna es "no", arregla y vuelve a verificar.

---

# Resumen heredado del CHECKLIST anterior (preservado por compatibilidad)

- [ ] Cada fila de `TECHNICAL_GUIDE §6.2` aparece en el Coverage Registry.
- [ ] Cada fila de `TECHNICAL_GUIDE §6.1` aparece en el Coverage Registry o en un journey slice.
- [ ] Cada tabla/migración de `TECHNICAL_GUIDE §10.3` aparece en el Coverage Registry.
- [ ] Cada journey de `instrucciones.md §3.7` referencia slices existentes.
- [ ] Ninguna celda del Journey Coverage Matrix apunta a pantallas/endpoints/tablas inexistentes.
- [ ] Phase gates mantienen tests acumulados verdes.


## Production hardening actual

Usa source-of-truth acumulativo baseline+vN, `Risk level`, `Verify mode`, phases <=20 slices, steps <=10 slices, journeys reales multi-superficie y verify con datos reales/proporcionados. Ejecuta bootstrap + check-task-dag + check-journey-matrix + check-wiring-contract antes de waves.
