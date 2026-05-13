# {{APP_NAME}} — Instrucciones (large app sin baseline snapshot)

## Screen/Journey Lane Redactor Contract

- No modeles la app como `backend/API primero`, luego `frontend`, y `UX polish` al final. Esa separación rompe la pantalla aunque los tests pasen.
- Cada pantalla importante debe nacer de una **screen/journey lane**: contrato de pantalla + contrato API/datos + implementación conectada + estados UX obligatorios + verificación del journey.
- Las slices de API/backend pueden existir separadas sólo si son foundation real o contrato técnico que alimenta una pantalla/journey nombrado en `Journey refs`.
- Criterio de cierre de pantalla: datos reales/proporcionados conectados front -> back -> DB, estados `loading`, `empty`, `error_network`, `error_validation`, `permission_denied` cuando aplique, `success`, navegación/next action, responsive básico y accesibilidad básica.
- Tamaño recomendado: pantalla crítica 3-6 slices; módulo/journey lane 8-15 slices. No hagas una slice por botón/componente pequeño; tampoco cierres una pantalla sólo porque compila.
- Defectos dentro de la pantalla actual van por `validator/tester -> debugger -> retest`. Sólo crea FU si falta trabajo nuevo fuera de scope: pantalla, endpoint, tabla, journey, contrato de datos reales o decisión humana no declarada.

> **SIN BASELINE**: define producto, stack, foundation, auth, UX, backend, datos y delivery desde cero usando `STACK_PROFILE.yaml`. No heredes rutas, tablas, endpoints, journeys ni decisiones de `docs/product-baseline/`.
>
> **TU TRABAJO aquí**: rellenar todo lo necesario para una app grande nueva. Las secciones marcadas `>>> MODELO:` se rellenan; cualquier bloque que no aplique debe resolverse como `NO APLICA` con motivo.
>
> Después de rellenar, copia los 5 ficheros a `docs/source-of-truth/` (sin `.template`) y corre `python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh`.

> Perfil: **large-without-base**. App grande nueva desde cero; AnyStack permitido vía `STACK_PROFILE.yaml`, sin asumir ningún framework salvo que el perfil lo declare.

---

## 🔗 Contrato de Cableado — léelo ANTES de empezar a rellenar

> Este documento es **ORIGEN** de identifiers que viajan a `*_TECHNICAL_GUIDE.md` y `*_IMPLEMENTATION_CHECKLIST.md`. Cada elemento que declares aquí DEBE quedar cableado simultáneamente en su par del otro doc, o el orquestador construirá a medias / dejará journeys huérfanos / generará slices vacíos.
>
> **Wires SALIENTES de este doc** (origen aquí → destino obligatorio en el otro):
>
> | Sección de `instrucciones.md`            | DEBE existir en `*_TECHNICAL_GUIDE.md`                                                                          | DEBE existir en `*_IMPLEMENTATION_CHECKLIST.md`                |
> |------------------------------------------|------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
> | §3.1 cada **componente del motor**        | §6.3 entity + §10.3 tabla + §6.2 endpoint(s) + §10.4 agent/graph/tools (si tiene AI)                            | Coverage Registry: 1+ slice Phase 2 (db / api / ai)            |
> | §3.2 cada **feature**                     | §6.1 ruta + §6.2 endpoints consumidos                                                                            | Coverage Registry: 1+ slice Phase 3 (frontend / journey)        |
> | §3.6 cada **journey J1+**               | §6.1 todas sus rutas + §6.2 todos sus endpoints                                                                  | Coverage Registry: slices que componen el journey              |
> | §3.7 cada **fila de la matriz**           | TODAS las celdas (pantallas/endpoints/tablas) deben ya EXISTIR en sus secciones canónicas del TECHNICAL_GUIDE   | columna `Slices` se expande a TASK_IDs reales del Registry     |
> | §4 cada **milestone**                     | §13 fila correspondiente en milestones técnicos                                                                  | agrupa slices reales del Registry (Phase 2 + Phase 3)          |
> | §11.0 cada **decisión USAR / DEFERRED**   | §2.0 fila técnica con paquete + URL + slice de introducción                                                      | Coverage Registry: slice que añade la lib en el manifiesto de dependencias declarado por `STACK_PROFILE.yaml` |
>
> **Regla de oro del cableado**: si una celda apunta a algo que aún no existe en su doc destino → CREA la entrada destino PRIMERO, LUEGO añade la celda aquí. Cero referencias huérfanas.
>
> **Cómo saber si está bien cableado**: ejecuta mentalmente la verificación final en §19 antes de entregar. Si fallas alguna casilla, vuelves al template y arreglas antes de mandarme el fichero.

---

## 1. Identidad del Proyecto

### 1.1 Nombre

>>> MODELO: Nombre en kebab-case (2-4 palabras). Ej: `operations-planner-pro`, `clinic-workflow-hub`, `team-insights-ai`.

### 1.2 Descripción

>>> MODELO: 3-5 frases: qué hace la app, para quién, qué problema concreto resuelve, qué hace distinta vs alternativas existentes. Escribir en tono ejecutivo.

### 1.3 Tipo de proyecto

⚙️ **DEFINIR PARA ESTE STACK** — declara plataforma(s), backend, DB, auth, AI y comandos desde `STACK_PROFILE.yaml`. No asumas ningún stack concreto salvo que el perfil lo declare.

---

## 2. Objetivo

### 2.1 Objetivo de negocio

>>> MODELO: Problema CONCRETO que resuelve tu app (3-6 frases). Incluir:
>>> - Pain point real del usuario.
>>> - Cómo lo solventas.
>>> - Qué valor tangible obtiene (ahorro tiempo, dinero, errores evitados).
>>> - Métrica de éxito del negocio.

### 2.2 Usuario objetivo

⚙️ **DEFINIR PARA ESTE STACK**: describe roles, permisos, tenant model y dispositivo predominante de esta app nueva. No heredes roles de existing baseline.

>>> MODELO: Descripción concreta del usuario normal de TU app:
>>> - Demográfico + contexto (ej: "abogados junior en despachos medianos, 25-35 años, mucha presión de tiempo").
>>> - Acciones principales en la app (mín 3).
>>> - Frecuencia de uso esperada (diaria, semanal, on-demand).
>>> - Device predominante (desktop web, mobile, ambos).

### 2.3 Definition of Done global — extensiones específicas

⚙️ **DEFINIR PARA ESTE STACK**: define los criterios globales propios de esta app nueva; deben ser verificables con datos reales/proporcionados.

>>> MODELO: añadir 5+ criterios específicos de TU app. Ej:
>>> - [ ] Un usuario completa el flujo principal con un dato/documento real proporcionado y ve el resultado visible dentro del umbral definido.
>>> - [ ] El motor principal cumple la métrica de calidad definida sobre datos reales de validación proporcionados.
>>> - [ ] La pantalla "Plan de estudio" muestra la planificación generada por el AI agent con todos los enlaces a recursos.
>>> - [ ] {milestone verificable} funciona end-to-end con datos reales en la superficie real declarada y mobile.

---

## 3. Alcance

### 3.1 EL MOTOR — lo que construyes en Phase 2

**Phase 2 del app = MOTOR / contratos de dominio**. Aquí se implementa el núcleo que alimenta pantallas y journeys nombrados; se valida por API/tests y siempre queda trazado a las pantallas que lo expondrán.

> 🔗 **CABLEADO de §3.1** — por CADA componente que declares aquí debes cablear:
>
> 1. **Entities** → `*_TECHNICAL_GUIDE.md §6.3` (con sus schemas/validadores y DTOs/modelos frontend tipados).
> 2. **Tablas DB nuevas** → `*_TECHNICAL_GUIDE.md §10.3` (SQL completo + índices + FK cascade).
> 3. **Endpoints nuevos** → `*_TECHNICAL_GUIDE.md §6.2` (method + path + req + res + auth + errors).
> 4. **AI (si aplica)** → `*_TECHNICAL_GUIDE.md §10.4` (agent/graph/deep_agent + tools + prompts + reference retrieval config).
> 5. **Slices ejecutables** → `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, **Phase 2** (1 fila por migración + 1 fila por endpoint + 1 fila por pieza AI con smoke test).
>
> Si te saltas alguno de los 5 → el orquestador lee §3.1 pero no encuentra recurso técnico ni slices → marca el componente "presente" pero lo deja sin implementar. Cero referencias huérfanas.

>>> MODELO: describe la LÓGICA NÚCLEO de la app. Por cada componente del motor, especifica:
>>>
>>> **Componente del motor: {nombre}**
>>> - **Qué hace**: 2-3 frases explicando la lógica de negocio.
>>> - **Entities de dominio**: listar (ej: `{{PrimaryEntity}}`, `{{SecondaryEntity}}`, `{{ResultEntity}}`).
>>> - **Use cases principales**: listar (ej: `{{MainUseCase}}`, `{{SecondaryUseCase}}`, `{{RecommendationUseCase}}`).
>>> - **Componente AI** (si aplica): qué agent/graph/deep_agent lo implementa.
>>>   - Tipo: `agent` simple / `graph` custom / `deep_agent` (para pipelines largos con planning + subagents + filesystem).
>>>   - Tools que usa (existentes o nuevos).
>>>   - Prompt base (descripción alta-level).
>>>   - reference retrieval config si aplica (qué se ingesta, qué se recupera).
>>> - **Tablas DB nuevas**: listar con campos principales.
>>> - **Endpoints nuevos**: listar method + path + propósito.
>>> - **Reglas de negocio**: 3+ reglas concretas aplicables (ej: "un registro no puede superar el límite definido", "cada resultado crítico debe tener acción recomendada").
>>>
>>> REPETIR POR CADA COMPONENTE. MÍNIMO 1 componente principal, habitualmente 2-4.

### 3.2 LAS FEATURES — lo que construyes en Phase 3

**Phase 3 = SCREEN/JOURNEY LANES**. Cada feature = pantalla/ruta del frontend declarado en `STACK_PROFILE.yaml` + flujo de usuario que expone el motor con API/datos/UX/journey cerrados juntos.

> 🔗 **CABLEADO de §3.2** — por CADA feature debes cablear:
>
> 1. **Pantalla(s)/ruta(s) frontend dentro de la screen/journey lane** → `*_TECHNICAL_GUIDE.md §6.1` (ruta + page + auth + descripción) — una fila por pantalla nueva.
> 2. **Endpoints consumidos** → ya declarados en `§6.2` (vienen del motor §3.1). Si falta uno, vuelve a §3.1 y añádelo allí PRIMERO.
> 3. **Estados marginales OBLIGATORIOS** (los 6): `loading`, `empty`, `error_network`, `error_validation`, `permission_denied`, `success`. Si tu feature de verdad no tiene uno (ej. no requiere permisos), márcalo como `n/a` con razón. NO los omitas en silencio.
> 4. **Next action** tras success: a qué pantalla / acción se sugiere ir. Sin esto el journey queda colgado.
> 5. **Slices ejecutables** → `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, **Phase 3** (screen/journey lane con contrato API/datos, pantalla conectada, estados UX y journey verification).
>
> Cada feature que declares aquí es validable por `/verify-slice` y/o `/verify-journey` — si no tiene pantalla en §6.1 ni slice en CHECKLIST, NO se construye.

>>> MODELO: listar TODAS las features. Por cada una:
>>>
>>> **Feature: {nombre}**
>>> 1. **{Funcionalidad concreta}**:
>>>    - Descripción 2-3 frases.
>>>    - Pantalla/s frontend involucradas (ej: `{{PrimaryActionPage}}`, `{{ResultPage}}`, `{{DetailPage}}`, o nombres equivalentes del framework declarado).
>>>    - Endpoints del motor que consume.
>>>    - Validaciones usuario (inline) + backend según framework declarado.
>>>    - Estados UI: idle / loading / empty / error / success.
>>>    - Edge cases (qué pasa si la entrada real proporcionada es inválida, si el motor tarda demasiado o si un servicio externo/AI falla).
>>>    - Reglas de negocio aplicadas en esta pantalla.
>>>
>>> MÍNIMO 3 features principales, habitualmente 4-8. Cada una debe ser verificable visualmente con datos reales/proporcionados.

### 3.3 Foundation propia — NO heredar existing baseline

Define aquí la foundation mínima que TU app construye desde cero, siempre alineada con `STACK_PROFILE.yaml`:

- **Identidad/roles**: state handler, pantallas/endpoints y claims si aplica. Si no aplica, escribir `NO APLICA` y motivo.
- **Perfil/cuenta**: qué datos de usuario existen y qué operaciones reales se soportan.
- **i18n**: idiomas, formato de keys y fallback si aplica.
- **Design system**: tokens, componentes base y showcase/verificación visual.
- **Logging + observabilidad**: request/correlation id, health checks, logs estructurados, métricas si aplica.
- **Infraestructura**: rate limiting, security headers, CORS, Docker/CI/CD mínimos.
- **AI stack**: solo si el producto lo necesita; declara carpetas, state handlers y smoke tests reales.

### 3.4 Excluido

>>> MODELO: qué NO entra en TU app y por qué. Ejemplos:
>>> - Pagos in-app en V1 (se añadirá en V2).
>>> - Modo offline completo (requiere replicación compleja).
>>> - Notificaciones push (no aplica al caso de uso).
>>> Mínimo 3 exclusiones explícitas.

### 3.5 Scope

⚙️ **DEFINIR PARA ESTE STACK**: PRODUCTO REAL DE PRODUCCIÓN desde día 1. Código de producción desde el primer commit.

>>> MODELO: definir tipo:
>>> - **Tipo**: MVP (mínimo viable para producción) o Producción completa.
>>>   NOTA: "MVP" = menos features, pero cada una AL 100%. Nunca "feature a medias".
>>> - **Qué va en V1** (imprescindibles): listar las features del §3.2 que entran en V1.
>>> - **V2 o siguientes**: listar features pospuestas con razón.
>>> - **Preparado para escalar**: si tu app requiere patrones específicos (ej: multi-idioma dinámico, replicación, CQRS), mencionar aquí.

📋 **SI APLICA — Multi-país**:
>>> MODELO: país inicial, qué varía por país (impuestos, formatos, regulaciones), qué se prepara desde día 1.

---


### 3.5.1 Granularidad esperada de los slices

> Esta sección no genera código directamente, pero guía a ChatGPT para que el CHECKLIST cree un `Coverage Registry` útil para Claude Code.
>
> Un slice oficial debe ser **pequeño, verificable y cerrable**. No escribas “Identidad/acceso completo”, “Motor completo” o “Todas las pantallas” como slice. Usa unidades como:
>
> - `POST /api/v1/<recurso>` con schema + use case + repository + integration test + curl + logs.
> - `GET /api/v1/<recurso>/:id` si tiene query/autorización/error handling propios.
> - `000N_<feature>.py` si una migración crea un grupo coherente de tablas.
> - `<FeaturePage>` si una pantalla tiene estados y state handler propios.
> - `<agent_or_graph> smoke` si una pieza AI se puede probar aislada.
> - `J1 e2e` si solo conecta piezas ya construidas.
>
> Objetivo orientativo: app grande nueva 20-60 slices. Menos no siempre es mejor: un slice grande falla más, pierde memoria entre validaciones y produce handoffs vagos.

### 3.6 Recorridos del usuario de la app

No hay journeys heredados. Esta sección declara journeys reales del motor + features de tu app, numerados desde **J1**.
>
> Cada journey usa **identificadores compartidos** con el resto de docs: rutas del frontend/router en `PROJECT_TECHNICAL_GUIDE.md §6.1` y nombres de pantalla/página del `PROJECT_IMPLEMENTATION_CHECKLIST.md`. Si una ruta no existe en §6.1, primero se añade ahí, luego se referencia aquí — cero rutas inventadas.

>>> MODELO: **Lista 2-6 journeys del MOTOR (§3.1) que ya tengas claros al generar el proyecto.**
>>> El resto se descubren durante implementación — un journey nuevo se añade aquí ANTES del
>>> slice que lo implementa. NO inventes journeys "para rellenar"; mejor pocos y reales.
>>>
>>> **Convención de notación**: `actor → /ruta → acción → /siguiente-ruta → … → estado final`.
>>>
>>> **Plantilla a completar** (un bloque por journey):
>>>
>>> ```
>>> #### J1 — <título del recorrido>
>>>
>>> <1 frase: por qué este recorrido importa para el motor / la app>.
>>>
>>> `actor → /ruta-A → acción → /ruta-B → … → /destino`.
>>>
>>> Estado final: <qué queda persistido / qué ve el user>.
>>> ```
>>>
>>> **Cuántos**: si tu app es una herramienta de un solo flujo principal, 1-2 journeys
>>> bastan. Si tiene varios subdominios, hasta 6. NUNCA más de 6 al generar — el resto se
>>> añaden a medida que aparezcan.
>>>
>>> **Si todavía no tienes ninguno claro al generar**, deja la sección con la línea final
>>> `(rellenar con journeys del motor durante Phase 2)` y eso es válido.

(rellenar con journeys del motor — mínimo J1)

---

### 3.7 Journey Coverage Matrix

> 🔒 **OBLIGATORIA**. Una fila por journey de §3.6. Cada celda referencia identificadores que YA existen en otras secciones (rutas §6.1 del TECHNICAL_GUIDE, endpoints §6.2, tablas §10.3, slices del CHECKLIST). El validador `scripts/check-journey-matrix.sh` falla si hay drift.
>
> **Convención de IDs**:
> - Journey IDs: `J1+` para journeys de TU app nueva. No reserves IDs para un baseline que no existe.
> - **Phase IDs: `P00..PNN`** (0-indexed/versionado). El bootstrap deriva fases del Coverage Registry y headings `# Phase N`; no concentres más de 20 slices por phase ni más de 15 por step; objetivo recomendado por step 6-12 slices para no fragmentar demasiado ni perder visión de la app.
> - Step IDs: `P0X-S0Y` (e.g. `P03-S02`). En modo Coverage Registry deben coincidir con la columna `Step` del CHECKLIST. Los headings `PRE-GATE`, `PHASE GATE` o notas no cuentan como steps; solo cuentan headings `## Step N.M`. En la práctica, `Step 3.2` suele mapear a `P03-S02`. La salida de `bootstrap_source_of_truth.py --refresh` lo confirma en `orchestrator-state/tasks/work-items/`.
> - Task IDs: `P0X-S0Y-T00Z` (e.g. `P03-S02-T001`).
>
> **Formatos aceptados en la columna Slices** (los expande `bootstrap_source_of_truth.py:_expand_slice_ref`):
> - Task ID completo: `P03-S02-T001`.
> - Rango: `P03-S02-T001..T004`.
> - **Step ref**: `P03-S02` → expande a TODAS las tasks de ese step (recomendado cuando todo el step pertenece al mismo journey).
> - **Phase ref**: `P03` → expande a TODAS las tasks de la phase (rara vez útil, solo para journeys que cruzan toda una phase).
> - Varios refs separados por coma: `P01-S05, P01-S06, P01-S07`.

> **Separadores de celdas**: en `Endpoints`, `Tablas DB`, `Estado cliente` y `Slices`, usa **coma + espacio** para múltiples valores. No uses punto y coma (`;`) porque el validador solo separa listas por coma. En `Pantallas` usa flecha `→` para el orden visual.
>
> La columna `Slices` NO es la matriz de dependencias DAG. Esta matriz solo dice qué slices cubren un journey. El orden/paralelismo entre slices vive en el CHECKLIST Coverage Registry, columna `Depends on`, y el bootstrap deriva `orchestrator-state/memory/task-dag.json`.

>>> MODELO: rellena la tabla con UNA FILA POR JOURNEY de §3.6. Si una celda apunta a algo que aún no existe (pantalla, endpoint, tabla, slice) → primero crea esa entrada en su sección canónica (TECHNICAL_GUIDE §6.1/§6.2/§10.3 o CHECKLIST Coverage Registry), luego añade la fila aquí. Mínimo 2 journeys si la app es simple; recomendado 3-6; nunca inventes journeys decorativos. Patrón:

| ID    | Milestone | Pantallas (en orden)                        | Acciones clave           | Endpoints                                            | Tablas DB              | Estado cliente             | Slices                       | Verificación         |
|-------|-----------|---------------------------------------------|--------------------------|------------------------------------------------------|------------------------|----------------------------|------------------------------|----------------------|
| J1  | M2        | {{LoginScreen}} → {{DashboardScreen}} → {{PrimaryActionPage}} → {{ResultPage}} | submit, confirm, primary action | POST {{primary_endpoint}}, GET {{result_endpoint}}     | {{primary_table}}, {{result_table}}        | {{primary_state_handler}}, {{result_state_handler}} | P02-S02                      | /verify-journey J1 |
| J2  | M2        | {{DashboardScreen}} → {{DetailScreen}} → {{SecondaryActionDialog}} | request secondary action           | GET {{detail_endpoint}}, POST {{secondary_action_endpoint}} | {{primary_table}}, audit_log    | {{secondary_action_state_handler}}             | P02-S03-T001..T002           | /verify-journey J2 |
| ...   | ...       | ...                                         | ...                      | ...                                                  | ...                    | ...                        | ...                          | ...                  |

>>> MODELO: si un journey cruza menos de 2 pantallas, NO es un journey — es una feature; queda en §3.2 y NO se mete aquí. Si una pantalla / endpoint / tabla referenciada aún no existe en TECHNICAL_GUIDE, créala primero ahí.

#### 3.7.1 Reglas de la matriz (no negociables)

- Una fila por journey. Mínimo 2 pantallas por journey.
- Toda celda apunta a IDs que existen en su sección canónica.
- Slices acepta los 4 formatos descritos arriba (TASK_ID, rango, step ref, phase ref). El bootstrap los expande automáticamente.
- Pipes literales dentro de una celda se escapan como `\|` (ej. `tap Continue with {ProveedorA\|ProveedorB}`). El parser los respeta.
- Las celdas que de verdad no aplican (ej. journey 100% client-side sin endpoint) usan el sentinel `(none)` o `—` — el validador los ignora.
- Verificación siempre `/verify-journey JXXX` (waiver explícito documentado solo en casos extremos).
- Milestone obligatorio (M1..Mn de §4).

---

## 4. Milestones

### 4.1 Definición

> 🔗 **CABLEADO de §4** — cada milestone aquí debe estar simultáneamente en:
>
> 1. **Mapeo técnico** → `*_TECHNICAL_GUIDE.md §13` (tabla milestone → features → rutas → endpoints → tablas → AI). Si declaras M2 aquí pero no aparece en §13, no hay recurso técnico.
> 2. **Slices agrupados** → `*_IMPLEMENTATION_CHECKLIST.md` (slices Phase 2 + Phase 3 que componen el milestone). Sin grupos cableados no hay verificación posible.
> 3. **Demo script verificable** → cada paso del script de verificación (login, click, submit, verificar resultado) debe ser ejecutable en `/verify-slice` o `/verify-journey`. Si declaras "Verificar X" pero X no tiene endpoint ni pantalla, drift inmediato.

>>> MODELO: milestones concretos con script de verificación. Cada milestone = motor + feature que expone ese motor.
>>>
>>> **Milestone N: {Nombre}**
>>> **Objetivo**: {valor entregable al usuario}
>>> **Motor requerido**: {componentes del §3.1}
>>> **Features requeridas**: {pantallas del §3.2}
>>> **Backend**: endpoints que deben responder.
>>> **Demo script**:
>>> 1. Abrir la superficie real declarada en `STACK_PROFILE.yaml`.
>>> 2. Autenticarse o seleccionar rol real/proporcionado si el journey lo requiere.
>>> 3. Click en {botón}.
>>> 4. Rellenar {datos concretos}.
>>> 5. Verificar que aparece {resultado concreto con datos reales del backend}.
>>> **Tras entrega**: {qué puede hacer el usuario end-to-end}.
>>>
>>> MÍNIMO 3 milestones. Cada milestone debe entregarse en <1 semana de trabajo humano equivalente.

### 4.2 Reglas de milestone

⚙️ **DEFINIR PARA ESTE STACK**: cada milestone funciona end-to-end con el frontend/backend/DB declarados en `STACK_PROFILE.yaml` y datos reales. Health + endpoints del milestone responden. No N+1 hasta que N funciona al 100%. Tests acumulados verdes usando los comandos del stack profile.

---

## 5. Modo de Trabajo

Principios obligatorios para esta app nueva: flujo por slice, tests reales, DRY/KISS/YAGNI, trazabilidad con `Coverage Registry`, documentación oficial antes de introducir APIs/dependencias y verificación visual/humana cuando `Verify mode=human`.

---

## 6. i18n — keys específicas de la app

⚙️ **DEFINIR PARA ESTE STACK**: idiomas, formato de recursos y generación i18n según el framework declarado. Si no hay i18n en v1, marcar `NO APLICA` con razón.

>>> MODELO: lista de keys que tu app añade:
>>> ```
>>> {
>>>   "domainProcessTitle": "Resultado del proceso",
>>>   "primaryActionHint": "Carga el dato/documento real proporcionado para empezar",
>>>   ...
>>> }
>>> ```
>>> Traducir sólo a los idiomas declarados para esta app. Si tu app tiene terminología específica de dominio, deja notas para revisión humana y no inventes traducciones no requeridas.

---

## 7. Theme

⚙️ **DEFINIR PARA ESTE STACK**: tokens de diseño + componentes compartidos según framework. CERO valores inline fuera del sistema de diseño.

>>> MODELO: si TU app necesita branding específico (logo, color primario distinto del default azul de la base), documentar aquí:
>>> - Logo: path + variantes (horizontal, icon-only, dark, light).
>>> - Color primario override: variable/token equivalente del sistema de diseño declarado.
>>> - Typography: si usas una fuente distinta de la declarada por el stack.
>>> - Si nada cambia: "Sin overrides de marca".

---

## 8-9. Prioridades de ejecución + Git

⚙️ **DEFINIR PARA ESTE STACK** — declara prioridad de ejecución, flujo Git y comandos reales desde `STACK_PROFILE.yaml`.

---

## 10. Criterios de Aceptación

Criterios fijos: comandos `frontend.test_cmd`, `backend.test_cmd`, checks de lint/build del `STACK_PROFILE.yaml` verdes. Arquitectura limpia. Cero hardcodeado/duplicado/muerto.

>>> MODELO: 5+ criterios específicos del dominio de TU app. Ej:
>>> - [ ] El motor de dominio devuelve el resultado esperado para cada caso crítico definido por el usuario/equipo.
>>> - [ ] El tiempo de procesamiento de una entrada real dentro del límite declarado cumple el umbral definido.
>>> - [ ] La exportación del informe en el formato declarado mantiene estructura, accesibilidad y trazabilidad.
>>> - [ ] El flujo de login declarado funciona y el usuario aterriza en la home con datos reales cargados.

---

## 11. Restricciones técnicas

⚙️ **DEFINIR PARA ESTE STACK**: stack completo declarado en `STACK_PROFILE.yaml`; versiones exactas se fijan en lockfiles al implementar, no aquí.

### 11.0 Library Discovery Pass — OBLIGATORIO antes de §11.1

> 🔗 **CABLEADO de §11.0** — cada decisión USAR / DEFERRED aquí debe estar simultáneamente en:
>
> 1. **Detalle técnico** → `*_TECHNICAL_GUIDE.md §2.0` (paquete + URL + frontend/backend + justificación + alternativa descartada + slice donde se introduce). Sin §2.0, el `developer` no sabe qué importar.
> 2. **Slice de introducción** → `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, una fila explícita que añade la lib en el manifiesto de dependencias correcto y refactoriza el primer consumidor. Sin este slice, la lib queda en el limbo: declarada pero nunca instalada.
> 3. **Resumen tabular** → §11.1 más abajo (lista corta sin versión).
>
> Las decisiones CUSTOM y NO APLICA NO se replican fuera de §11.0 (no necesitan slice de introducción). Las DEFERRED tienen que indicar fase de introducción y entonces sí necesitan slice en CHECKLIST cuando llegue esa fase.

> **Por qué existe**: si rellenas §3.1 (motor) y §3.2 (features) sin antes preguntarte "¿hay una librería que ya hace esto?", acabas describiendo 4-6 slices de código artesanal que una librería estable resuelve en 0.5 slice. Este paso evita la rueda reinventada.
>
> **Cómo funciona**: por cada área funcional aplicable a TU app, ChatGPT **piensa y busca** una librería estable que resuelva el problema. La guía completa del proceso está en `docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md` — léela ANTES de rellenar.
>
> **Importante — política de versiones**:
> - **NO pinees versiones en este documento**. Las versiones cambian cada semanas; lo que escribas hoy puede no existir en 6 meses.
> - **Sí declara el nombre del paquete** (si tienes alta confianza de que existe y está mantenido). Si dudas, déjalo como `<librería candidata, official-docs-researcher confirmará>`.
> - El `official-docs-researcher` corre antes del developer en CADA slice y resuelve la versión exacta cuando se introduce la lib en el manifiesto de dependencias correcto. El lockfile fija la versión, no este documento.
>
> **Reglas no negociables** (extracto — completas en `PROMPT_SOURCE_OF_TRUTH_DAG.md §7`):
> - NO añadas dependencias por costumbre ni copies stack existing baseline. Usa solo el stack declarado en `STACK_PROFILE.yaml` y justifica cada paquete nuevo.
> - <20 LOC → CUSTOM gana. La librería NO entra.
> - Solo libs con adopción real (≥1k stars o equivalente, mantenidas en últimos 6 meses; 2 meses para AI/ML).
> - License MIT/BSD/Apache. GPL/comercial requieren ADR.
> - Backend ≤30 deps, frontend ≤30 deps. Si pasas, justifica eliminando otra.

>>> MODELO: ChatGPT recorre las áreas funcionales típicas listadas en `PROMPT_SOURCE_OF_TRUTH_DAG.md §3` y, **para CADA área aplicable a esta app concreta**, decide:
>>>
>>> - **USAR**: hay una librería estable que ahorra ≥1 slice. Indica QUÉ TIPO de librería se busca (no nombre concreto si no estás seguro). El detalle (nombre + URL + justificación) va a `*_TECHNICAL_GUIDE.md §2.0`.
>>> - **CUSTOM**: el problema se resuelve en <20 LOC propias. Justifica brevemente.
>>> - **NO APLICA**: la app no tiene esa funcionalidad.
>>> - **DEFERRED**: aplicará en una fase futura (ej. crash reporting solo en release). Indica fase.
>>>
>>> **Mínimo 6 áreas evaluadas** (incluidas NO APLICA explícitas — eso demuestra que pensaste). No copies áreas que no aplican; declara solo las que evaluaste con criterio real.
>>>
>>> Patrón de tabla (no copies estos ejemplos verbatim — son orientativos):

| Área funcional | Decisión | Tipo de librería buscada (sin versión) | Slices estimados ahorrados |
|---|---|---|---|
| {Forms y validación} | {USAR \| CUSTOM \| NO APLICA \| DEFERRED} | {ej: form builder con validación tipada compatible con el gestor de estado declarado} | {ej: 1-2} |
| {Procesamiento de entrada/documento backend} | {USAR \| ...} | {ej: parser/validador del formato real proporcionado} | {ej: 1} |
| {...} | {...} | {...} | {...} |

>>> **Áreas a recorrer** (ver descripción de cada una en `PROMPT_SOURCE_OF_TRUTH_DAG.md §3`). Evalúa las que apliquen a TU app:
>>>
>>> Frontend según `STACK_PROFILE.yaml`: forms y validación · iconografía · componentes UI extra · cache de imágenes · file pickers · chat/streaming AI · charts · animations · layouts responsive · codegen · deep links · date/time avanzado · maps · pagos · push · crash reporting · permissions nativos · almacenamiento offline.
>>>
>>> Backend: procesamiento de documentos/datos · procesamiento Office · procesamiento imagen/video · HTTP a APIs externas · jobs/queues · email custom · scraping · validaciones específicas (phones, IDs, IBAN) · extensiones cripto · observabilidad backend · storage externo/no declarado en perfil.
>>>
>>> BBDD: extensiones motor DB declarado específicas (pg_trgm, unaccent, pgcrypto, PostGIS).
>>>
>>> AI/ML: structured outputs · constrained generation · prompt eval · reference retrieval metrics · token counting · loaders/chunkers específicos.
>>>
>>> Si una de estas áreas NO aplica a tu app, omítela — basta evaluar las que sí (mínimo 6). Si descubres una que no está en la lista pero aplica a tu app, añádela.

### 11.1 Paquetes adicionales — detalle (referencia a §2.0 del TECHNICAL_GUIDE)

>>> MODELO: el detalle técnico (nombre exacto del paquete + URL oficial + justificación + alternativa descartada + slice donde se introduce) va en `*_TECHNICAL_GUIDE.md §2.0` — NO se duplica aquí.
>>>
>>> Aquí en §11.1 basta una **lista resumen** de las decisiones USAR / DEFERRED del §11.0, en formato:
>>>
>>> - **<Área>**: `<paquete>` (sin versión — la pinea el lockfile al implementar). Ver `*_TECHNICAL_GUIDE.md §2.0` para detalle.
>>>
>>> Si tu §11.0 declaró todas las áreas como CUSTOM o NO APLICA: "Sin adiciones; library discovery pass declaró todas las áreas como NO APLICA o resueltas con código custom pequeño."

### 11.2 Paquetes prohibidos

- Cualquier alternativa no justificada al stack declarado en `STACK_PROFILE.yaml` (state manager, router, ORM, HTTP client, etc.).
- Librerías abandonadas (sin commits en últimos 6 meses; 2 meses para AI/ML).
- Tokens en `SharedPreferences` / `localStorage` directo.
- Dependencias síncronas en pipelines async (preferir async-first).
- Cualquier dependencia que requiera CORS `*` o CSP laxa.
- Librerías con license incompatible (GPL viral, comerciales con field-of-use restrictions) sin ADR explícito.

---

## 12. Plataforma

⚙️ **DEFINIR PARA ESTE STACK**: declara plataformas reales según `STACK_PROFILE.yaml` (web, mobile, desktop, API-only, etc.), responsive/adaptaciones y abstracciones necesarias para storage/auth.

>>> MODELO: si tu app tiene funcionalidad que varía POR PLATAFORMA, documentar aquí:
>>> - Camera / photo capture: mobile nativo, web file picker.
>>> - Notificaciones push: FCM/APNs mobile, web push opcional.
>>> - Pagos: Stripe web, App Store / Play Store in-app purchases en mobile.
>>> - File system access: limitado en web, amplio en mobile con permisos.
>>> - Biometric auth: Face ID / fingerprint mobile, no web.
>>>
>>> Si nada varía: "Sin variación por plataforma".

---

## 13. Riesgos

>>> MODELO: 3+ riesgos específicos del dominio de TU app con mitigación concreta. Ej:
>>> - **Riesgo**: Las entradas reales proporcionadas tienen formato variable → parsing/validación inconsistente.
>>>   **Mitigación**: Pipeline de ingestion validado con datos reales proporcionados; si falta cobertura, bloquear o registrar follow-up antes de release.
>>> - **Riesgo**: LLM o motor de reglas genera recomendaciones incorrectas para el dominio.
>>>   **Mitigación**: Aviso contextual claro + revisión humana cuando aplique + feedback loop + sistema de reportes.
>>> - **Riesgo**: Costes de LLM escalan sin control.
>>>   **Mitigación**: Rate limit por user + cache de análisis recientes + alert de consumo en Admin AI.

---

## 14. Logging y Observabilidad

⚙️ **DEFINIR PARA ESTE STACK**: structlog + flag verbose + request_id + audit_log + Prometheus.

>>> MODELO: si tu app necesita logs/métricas específicas (ej: métricas de negocio como "recursos procesados/hora"), listar aquí:
>>> - Métricas custom: nombre + tipo (counter/histogram/gauge) + labels.
>>> - Audit log actions nuevas: ej `resource_created`, `process_completed`, `recommendation_accepted`.

---

## 15. Datos reales de verificación

⚙️ **DEFINIR PARA ESTE STACK**: usuarios/proveedores base reales proporcionados.

>>> MODELO: tu app puede necesitar datos reales proporcionados específicos para milestones:
>>> - Milestone N: X registros/documentos reales proporcionados, Y usuarios reales de prueba con historial.
>>> - Fuente: el usuario/equipo proporcionará los datos necesarios antes de verificar; si faltan, la slice se bloquea o se registra follow-up.
>>> - Carga: script idempotente de importación de datos proporcionados, sin inventar datos ni cargas no proporcionadas.

---

## 16. Protocolo de Entrega

⚙️ **DEFINIR PARA ESTE STACK**.

---

## 17. Visualización

📋 **SI APLICA**:
>>> MODELO: si diseñas mockups previos de las pantallas nuevas, guardarlos en `docs/visualization/{feature}/`. No obligatorio si usas el design system directamente.

---

## 18. Relación con baseline

**Sin existing baseline.** Este perfil empieza desde cero.

**Lo que NO se debe arrastrar:**
- Rutas, pantallas, endpoints, tablas o journeys de `docs/product-baseline/`.
- Suposiciones de stack si `STACK_PROFILE.yaml` declara otro stack.
- Dependencias, state handlers, routers u ORMs heredados sin slice explícita.

**Lo que TU app debe declarar:**
- Foundation mínima propia: health checks, auth/roles si aplica, design tokens, logging, tests, scripts y reset/carga de datos reales proporcionados.
- Módulos backend/frontend en los paths reales de `STACK_PROFILE.yaml`.
- Migraciones/tablas/endpoints/pantallas/journeys del dominio.
- Cualquier dependencia nueva como slice `library` con `Conflict group`/`Write set`.

---

## 19. Verificación de cableado pre-entrega — OBLIGATORIO

> 🔗 **Antes de devolverme este fichero, recorre TODA esta checklist mentalmente y verifica que cada wire está cerrado**. Si alguno falla, vuelves al template y arreglas ANTES de entregar. ChatGPT no entrega un `instrucciones.md` con cableado roto. El validador `scripts/check-journey-matrix.sh --strict` y el bootstrap fallarán si hay drift.

### 19.1 Wires desde §3.1 (MOTOR)

Para CADA componente declarado en §3.1, confirmar en orden:

- [ ] Tiene **entity** declarada en `*_TECHNICAL_GUIDE.md §6.3`.
- [ ] Tiene **tabla(s) DB** declarada(s) en `*_TECHNICAL_GUIDE.md §10.3` con SQL completo + FKs + índices.
- [ ] Tiene **endpoint(s)** declarado(s) en `*_TECHNICAL_GUIDE.md §6.2` con method + path + req + res + auth + errors.
- [ ] Si tiene AI: tiene **agent / graph / deep_agent** + **tools** + **prompts** + **reference retrieval config** declarados en `*_TECHNICAL_GUIDE.md §10.4`.
- [ ] Tiene **1+ slice Phase 2** en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (db / api / ai).
- [ ] Las **reglas de negocio** declaradas aquí se cumplen como invariantes en `*_TECHNICAL_GUIDE.md §12` (Constraints & Invariants).

### 19.2 Wires desde §3.2 (FEATURES)

Para CADA feature declarada en §3.2, confirmar en orden:

- [ ] Tiene **pantalla(s)** declarada(s) en `*_TECHNICAL_GUIDE.md §6.1` con ruta + page + auth + descripción.
- [ ] Cada **endpoint que consume** existe en `*_TECHNICAL_GUIDE.md §6.2` (sale del motor §3.1).
- [ ] Declara los **6 estados marginales** (loading / empty / error_network / error_validation / permission_denied / success). Si alguno no aplica de verdad, está marcado `n/a` con razón.
- [ ] Declara su **Next action** tras success.
- [ ] Tiene **1+ slice Phase 3** en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (frontend o journey).

### 19.3 Wires desde §3.6 + §3.7 (JOURNEYS)

Para CADA fila de la matriz §3.7:

- [ ] Tiene **≥2 pantallas** y todas existen en `*_TECHNICAL_GUIDE.md §6.1`.
- [ ] Cada **endpoint** de la celda existe en `*_TECHNICAL_GUIDE.md §6.2`.
- [ ] Cada **tabla** de la celda existe en `*_TECHNICAL_GUIDE.md §10.3`.
- [ ] Cada **slice** de la columna `Slices` existe en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (verificable expandiendo `P0X-S0Y[-T00Z]` con el bootstrap).
- [ ] **Milestone** referenciado existe en §4.
- [ ] Columna `Verificación` cita `/verify-journey JXXX`.
- [ ] **Separadores correctos**: `→` en pantallas; coma + espacio en endpoints/tablas/estado/slices; **NUNCA** `;`. Pipes literales escapados como `\|`.

### 19.4 Wires desde §4 (MILESTONES)

Para CADA milestone declarado en §4:

- [ ] Aparece en `*_TECHNICAL_GUIDE.md §13` con motor + features + rutas + endpoints + tablas + AI mapeados.
- [ ] Agrupa **slices reales** del `*_IMPLEMENTATION_CHECKLIST.md` (no es decorativo).
- [ ] Su **script de verificación** es ejecutable paso a paso usando endpoints / pantallas que YA existen en los otros 2 docs.

### 19.5 Wires desde §11.0 (LIBRARY DISCOVERY)

Para CADA decisión **USAR / DEFERRED** declarada en §11.0:

- [ ] Tiene **fila completa** en `*_TECHNICAL_GUIDE.md §2.0` con paquete + URL + frontend/backend + justificación + alternativa descartada + slice de introducción.
- [ ] **NINGUNA fila lleva versión pineada** (debe decir literal `pendiente — official-docs-researcher confirmará al implementar`).
- [ ] Tiene **slice de introducción** real en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (la slice que añade la lib en el manifiesto de dependencias correcto y refactoriza el primer consumidor).
- [ ] Aparece en el **resumen §11.1** de este doc.

### 19.6 Drift checks — cero tolerancia

- [ ] **Cero `>>> MODELO:`** restantes en el fichero filled.
- [ ] **Cero `📋 SI APLICA`** sin resolver (o rellenas o eliminas la sección).
- [ ] **Cero referencias a existing baseline/herencia** salvo que estén marcadas explícitamente como `NO APLICA` para este perfil sin base.
- [ ] **Cero referencias** a IDs (rutas, endpoints, tablas, slices, JIDs) que no existan en su doc destino.
- [ ] Si hay AI/ML libs en §11.0: están declaradas como `pendiente — official-docs-researcher confirmará` (cambian cada semanas, no inventes versiones).

### 19.7 Última prueba mental antes de entregar

Hazte estas 3 preguntas:

1. **¿Si Claude Code lee §3.1, encuentra TODO el recurso técnico necesario en TECHNICAL_GUIDE para implementar el motor?** Si la respuesta es "necesita inferir algo", falta cableado.
2. **¿Si Claude Code lee §3.7 (Journey Matrix), puede expandir cada celda a un identifier que existe en otra sección?** Si una celda apunta al vacío, falta cableado.
3. **¿Si el `planner` selecciona el primer slice del Coverage Registry, encuentra origen claro en §3.1 / §3.2 / §3.7 + recurso técnico claro en §6.1 / §6.2 / §6.3 / §10.3 / §10.4?** Si tiene que adivinar, falta cableado.

Si las 3 son "sí", entrega. Si alguna es "no", arregla y vuelve a verificar.


## Production hardening actual

Usa source-of-truth acumulativo de app nueva (`v1`, luego `v2`, ...), `Risk level`, `Verify mode`, phases <=20 slices, steps <=15 slices, journeys reales multi-superficie y verify con datos reales/proporcionados. Ejecuta bootstrap + check-task-dag + check-journey-matrix + check-wiring-contract antes de waves.