# {{APP_NAME}} — Instrucciones (feature-app sobre base-app)

> **HEREDADO DE LA BASE-APP** (no redefinir): auth multi-provider (email + Google + Apple + Microsoft), i18n ES/EN/FR, Profile + GDPR, admin AI panel con multi-proveedor dinámico, design system, logging estructurado, observabilidad básica, rate limiting, audit log, security headers, stack completo (Flutter + FastAPI + Supabase + pgvector + LangChain + LangGraph + DeepAgents).
>
> Detalle completo de lo heredado: `docs/base-app/instrucciones.md` + `docs/base-app/BASEAPP_TECHNICAL_GUIDE.md`.
>
> **TU TRABAJO aquí**: rellenar SOLO lo específico de esta app (motor de dominio + features). Las secciones marcadas `>>> MODELO:` se rellenan; las marcadas `HEREDADO` NO se tocan.
>
> Después de rellenar, copia los 5 ficheros a `docs/source-of-truth/` (sin `.template`) y corre `python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh`.

> Perfil: **large-with-base**. Hereda `docs/base-app/` y mantiene stack Flutter + FastAPI + Postgres/Supabase-compatible; no convertir a React/Node.

---

## 🔗 Contrato de Cableado — léelo ANTES de empezar a rellenar

> Este documento es **ORIGEN** de identifiers que viajan a `*_TECHNICAL_GUIDE.md` y `*_IMPLEMENTATION_CHECKLIST.md`. Cada elemento que declares aquí DEBE quedar cableado simultáneamente en su par del otro doc, o el orquestador construirá a medias / dejará journeys huérfanos / generará slices vacíos.
>
> **Wires SALIENTES de este doc** (origen aquí → destino obligatorio en el otro):
>
> | Sección de `instrucciones.md`            | DEBE existir en `*_TECHNICAL_GUIDE.md`                                                                          | DEBE existir en `*_IMPLEMENTATION_CHECKLIST.md`                |
> |------------------------------------------|------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
> | §3.1 cada **componente del motor**        | §6.3 entity + §10.3 tabla + §6.2 endpoint(s) + §10.4 agent/graph/tools (si tiene AI)                            | Coverage Registry: 1+ slice Phase 2 (db / api / ai)            |
> | §3.2 cada **feature**                     | §6.1 ruta + §6.2 endpoints consumidos                                                                            | Coverage Registry: 1+ slice Phase 3 (flutter / journey)        |
> | §3.6 cada **journey J101+**               | §6.1 todas sus rutas + §6.2 todos sus endpoints                                                                  | Coverage Registry: slices que componen el journey              |
> | §3.7 cada **fila de la matriz**           | TODAS las celdas (pantallas/endpoints/tablas) deben ya EXISTIR en sus secciones canónicas del TECHNICAL_GUIDE   | columna `Slices` se expande a TASK_IDs reales del Registry     |
> | §4 cada **milestone**                     | §13 fila correspondiente en milestones técnicos                                                                  | agrupa slices reales del Registry (Phase 2 + Phase 3)          |
> | §11.0 cada **decisión USAR / DEFERRED**   | §2.0 fila técnica con paquete + URL + slice de introducción                                                      | Coverage Registry: slice que añade la lib en `pubspec.yaml` / `pyproject.toml` |
>
> **Regla de oro del cableado**: si una celda apunta a algo que aún no existe en su doc destino → CREA la entrada destino PRIMERO, LUEGO añade la celda aquí. Cero referencias huérfanas.
>
> **Cómo saber si está bien cableado**: ejecuta mentalmente la verificación final en §19 antes de entregar. Si fallas alguna casilla, vuelves al template y arreglas antes de mandarme el fichero.

---

## 1. Identidad del Proyecto

### 1.1 Nombre

>>> MODELO: Nombre en kebab-case (2-4 palabras). Ej: `legal-contract-analyzer`, `meal-planner-pro`, `study-buddy-ai`.

### 1.2 Descripción

>>> MODELO: 3-5 frases: qué hace la app, para quién, qué problema concreto resuelve, qué hace distinta vs alternativas existentes. Escribir en tono ejecutivo.

### 1.3 Tipo de proyecto

🔒 **HEREDADO** — Flutter Web primera plataforma + Android + iOS desde día 1. Backend Python 3.12 + FastAPI. Supabase Postgres + pgvector + Auth. Stack AI completo. **NO REDEFINIR**.

---

## 2. Objetivo

### 2.1 Objetivo de negocio

>>> MODELO: Problema CONCRETO que resuelve tu app (3-6 frases). Incluir:
>>> - Pain point real del usuario.
>>> - Cómo lo solventas.
>>> - Qué valor tangible obtiene (ahorro tiempo, dinero, errores evitados).
>>> - Métrica de éxito del negocio.

### 2.2 Usuario objetivo

🔒 **HEREDADO**: app móvil de un único tipo de usuario (más rol admin excepcional para el AI admin panel). NO hay roles complejos ni multi-tenant.

>>> MODELO: Descripción concreta del usuario normal de TU app:
>>> - Demográfico + contexto (ej: "abogados junior en despachos medianos, 25-35 años, mucha presión de tiempo").
>>> - Acciones principales en la app (mín 3).
>>> - Frecuencia de uso esperada (diaria, semanal, on-demand).
>>> - Device predominante (desktop web, mobile, ambos).

### 2.3 Definition of Done global — extensiones específicas

🔒 **HEREDADO**: los 16 criterios de `docs/base-app/instrucciones.md §2.3`.

>>> MODELO: añadir 5+ criterios específicos de TU app. Ej:
>>> - [ ] Un usuario puede subir un PDF de contrato y ver el análisis completo en <30 segundos.
>>> - [ ] El motor de clasificación de riesgos tiene precisión >85% en el dataset de validación.
>>> - [ ] La pantalla "Plan de estudio" muestra la planificación generada por el AI agent con todos los enlaces a recursos.
>>> - [ ] {milestone demo} funciona end-to-end con datos reales en Chrome y mobile.

---

## 3. Alcance

### 3.1 EL MOTOR — lo que construyes en Phase 2

🔒 **Phase 2 del feature-app = MOTOR**. Aquí está el valor de tu app. SIN UI aún. Se valida por curl + tests backend.

> 🔗 **CABLEADO de §3.1** — por CADA componente que declares aquí debes cablear:
>
> 1. **Entities** → `*_TECHNICAL_GUIDE.md §6.3` (con sus campos Pydantic + DTOs Dart freezed).
> 2. **Tablas DB nuevas** → `*_TECHNICAL_GUIDE.md §10.3` (SQL completo + índices + FK cascade).
> 3. **Endpoints nuevos** → `*_TECHNICAL_GUIDE.md §6.2` (method + path + req + res + auth + errors).
> 4. **AI (si aplica)** → `*_TECHNICAL_GUIDE.md §10.4` (agent/graph/deep_agent + tools + prompts + RAG config).
> 5. **Slices ejecutables** → `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, **Phase 2** (1 fila por migración + 1 fila por endpoint + 1 fila por pieza AI con smoke test).
>
> Si te saltas alguno de los 5 → el orquestador lee §3.1 pero no encuentra contrato técnico ni slices → marca el componente "presente" pero lo deja sin implementar. Cero referencias huérfanas.

>>> MODELO: describe la LÓGICA NÚCLEO de la app. Por cada componente del motor, especifica:
>>>
>>> **Componente del motor: {nombre}**
>>> - **Qué hace**: 2-3 frases explicando la lógica de negocio.
>>> - **Entities de dominio**: listar (ej: `Contract`, `Clause`, `Risk`, `Suggestion`).
>>> - **Use cases principales**: listar (ej: `AnalyzeContract`, `ClassifyClauses`, `SuggestEdits`).
>>> - **Componente AI** (si aplica): qué agent/graph/deep_agent lo implementa.
>>>   - Tipo: `agent` simple / `graph` custom / `deep_agent` (para pipelines largos con planning + subagents + filesystem).
>>>   - Tools que usa (existentes o nuevos).
>>>   - Prompt base (descripción alta-level).
>>>   - RAG config si aplica (qué se ingesta, qué se recupera).
>>> - **Tablas DB nuevas**: listar con campos principales.
>>> - **Endpoints nuevos**: listar method + path + propósito.
>>> - **Reglas de negocio**: 3+ reglas concretas aplicables (ej: "un contrato no puede tener >100 cláusulas", "cada cláusula clasificada como riesgo alto debe tener sugerencia").
>>>
>>> REPETIR POR CADA COMPONENTE. MÍNIMO 1 componente principal, habitualmente 2-4.

### 3.2 LAS FEATURES — lo que construyes en Phase 3

🔒 **Phase 3 del feature-app = FEATURES**. Cada feature = pantalla Flutter + flujo de usuario que EXPONE el motor construido en Phase 2.

> 🔗 **CABLEADO de §3.2** — por CADA feature debes cablear:
>
> 1. **Pantalla(s) Flutter** → `*_TECHNICAL_GUIDE.md §6.1` (ruta + page + auth + descripción) — una fila por pantalla nueva.
> 2. **Endpoints consumidos** → ya declarados en `§6.2` (vienen del motor §3.1). Si falta uno, vuelve a §3.1 y añádelo allí PRIMERO.
> 3. **Estados marginales OBLIGATORIOS** (los 6): `loading`, `empty`, `error_network`, `error_validation`, `permission_denied`, `success`. Si tu feature de verdad no tiene uno (ej. no requiere permisos), márcalo como `n/a` con razón. NO los omitas en silencio.
> 4. **Next action** tras success: a qué pantalla / acción se sugiere ir. Sin esto el journey queda colgado.
> 5. **Slices ejecutables** → `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, **Phase 3** (1 slice por pantalla mínimo + slices de integración / journey si componen flujo).
>
> Cada feature que declares aquí es validable por `/verify-slice` y/o `/verify-journey` — si no tiene pantalla en §6.1 ni slice en CHECKLIST, NO se construye.

>>> MODELO: listar TODAS las features. Por cada una:
>>>
>>> **Feature: {nombre}**
>>> 1. **{Funcionalidad concreta}**:
>>>    - Descripción 2-3 frases.
>>>    - Pantalla/s Flutter involucradas (ej: `ContractUploadPage`, `AnalysisResultsPage`, `ClauseDetailPage`).
>>>    - Endpoints del motor que consume.
>>>    - Validaciones usuario (inline) + backend (Pydantic).
>>>    - Estados UI: idle / loading / empty / error / success.
>>>    - Edge cases (qué pasa si el PDF es corrupto, si el motor tarda demasiado, si LLM falla).
>>>    - Reglas de negocio aplicadas en esta pantalla.
>>>
>>> MÍNIMO 3 features principales, habitualmente 4-8. Cada una debe ser demoable visualmente.

### 3.3 HEREDADO — NO redefinir ni reimplementar

Lista de lo que YA viene listo desde base-app (solo para referencia):

- **Auth**: email + Google + Apple + Microsoft. Pantallas `LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`.
- **Profile + GDPR**: `ProfilePage` completa (cambio password, logout global, export, delete).
- **Admin AI**: `AdminAIPage` con CRUD de proveedores LLM + embeddings, test, activate, StatusBadge.
- **i18n**: ES/EN/FR con cambio runtime. Tu app añade keys nuevas a los 3 `.arb`.
- **Design system**: ThemeData + shared widgets (AppButton, AppInput, AppCard, StatusBadge, etc). Tu app USA estos, no crea duplicados.
- **Logging + observabilidad**: structlog + request_id + audit_log + Prometheus + health/ready/live.
- **Infraestructura**: rate limiting, security headers, CORS, graceful shutdown, Docker base, CI/CD base.
- **AI stack scaffoldeado**: carpetas `agents/`, `deep_agents/`, `graphs/`, `chains/`, `tools/`, `prompts/`, `rag/`, `llms/`, `embeddings/`, `memory/` preparadas. Tu app AÑADE en esas carpetas.

### 3.4 Excluido

>>> MODELO: qué NO entra en TU app y por qué. Ejemplos:
>>> - Pagos in-app en V1 (se añadirá en V2).
>>> - Modo offline completo (requiere replicación compleja).
>>> - Notificaciones push (no aplica al caso de uso).
>>> Mínimo 3 exclusiones explícitas.

### 3.5 Scope

🔒 **HEREDADO**: PRODUCTO REAL DE PRODUCCIÓN desde día 1. Código de producción desde el primer commit.

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
> Un slice oficial debe ser **pequeño, verificable y cerrable**. No escribas “Auth completa”, “Motor completo” o “Todas las pantallas” como slice. Usa unidades como:
>
> - `POST /api/v1/<recurso>` con schema + use case + repository + integration test + curl + logs.
> - `GET /api/v1/<recurso>/:id` si tiene query/autorización/error handling propios.
> - `000N_<feature>.py` si una migración crea un grupo coherente de tablas.
> - `<FeaturePage>` si una pantalla tiene estados y provider propios.
> - `<agent_or_graph> smoke` si una pieza AI se puede probar aislada.
> - `J101 e2e` si solo conecta piezas ya construidas.
>
> Objetivo orientativo: feature-app normal 20-50 slices; base-app 70-100 slices. Menos no siempre es mejor: un slice grande falla más, pierde memoria entre validaciones y produce handoffs vagos.

### 3.6 Recorridos del usuario específicos de la feature-app

> **Heredado**: los journeys reales de la base-app **J1–J8** viven en `docs/base-app/instrucciones.md §3.7` y NO se redefinen aquí. Cambio de idioma, tabs internos y estados de una sola pantalla son features/UX states, no journeys.
>
> **Esta sección**: journeys ESPECÍFICOS del motor + features de tu feature-app, numerados desde **J101**.
>
> Cada journey usa **identificadores compartidos** con el resto de docs: rutas GoRouter de `PROJECT_TECHNICAL_GUIDE.md §6.1` (rutas nuevas, no las heredadas) y nombres de pantalla del `PROJECT_IMPLEMENTATION_CHECKLIST.md`. Si una ruta no existe en §6.1, primero se añade ahí, luego se referencia aquí — cero rutas inventadas.

>>> MODELO: **Lista 2-6 journeys del MOTOR (§3.1) que ya tengas claros al generar el proyecto.**
>>> El resto se descubren durante implementación — un journey nuevo se añade aquí ANTES del
>>> slice que lo implementa. NO inventes journeys "para rellenar"; mejor pocos y reales.
>>>
>>> **Convención de notación**: `actor → /ruta → acción → /siguiente-ruta → … → estado final`.
>>>
>>> **Plantilla a completar** (un bloque por journey):
>>>
>>> ```
>>> #### J101 — <título del recorrido>
>>>
>>> <1 frase: por qué este recorrido importa para el motor / la feature-app>.
>>>
>>> `actor → /ruta-A → acción → /ruta-B → … → /destino`.
>>>
>>> Estado final: <qué queda persistido / qué ve el user>.
>>> ```
>>>
>>> **Cuántos**: si tu feature-app es una herramienta de un solo flujo principal, 1-2 journeys
>>> bastan. Si tiene varios subdominios, hasta 6. NUNCA más de 6 al generar — el resto se
>>> añaden a medida que aparezcan.
>>>
>>> **Si todavía no tienes ninguno claro al generar**, deja la sección con la línea final
>>> `(rellenar con journeys del motor durante Phase 2)` y eso es válido.

(rellenar con journeys del motor — mínimo J101)

---

### 3.7 Journey Coverage Matrix

> 🔒 **OBLIGATORIA**. Una fila por journey de §3.6. Cada celda referencia identificadores que YA existen en otras secciones (rutas §6.1 del TECHNICAL_GUIDE, endpoints §6.2, tablas §10.3, slices del CHECKLIST). El validador `scripts/check-journey-matrix.sh` falla si hay drift.
>
> **Convención de IDs**:
> - Journey IDs: `J100+` para journeys de TU app (los `J1-J99` quedan reservados para el baseline si existe).
> - **Phase IDs: `P00..PNN`** (0-indexed/versionado). El bootstrap deriva fases del Coverage Registry y headings `# Phase N`; no concentres más de 12 slices por phase ni más de 10 por step.
> - Step IDs: `P0X-S0Y` (e.g. `P03-S02`). En modo Coverage Registry deben coincidir con la columna `Step` del CHECKLIST. Los headings `PRE-GATE`, `PHASE GATE` o notas no cuentan como steps; solo cuentan headings `## Step N.M`. En la práctica, `Step 3.2` suele mapear a `P03-S02`. La salida de `bootstrap_three_docs.py --refresh` lo confirma en `orchestrator-state/tasks/work-items/`.
> - Task IDs: `P0X-S0Y-T00Z` (e.g. `P03-S02-T001`).
>
> **Formatos aceptados en la columna Slices** (los expande `bootstrap_three_docs.py:_expand_slice_ref`):
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
| J101  | M2        | LoginPage → DashboardPage → UploadPage → AnalysisResultPage | submit, confirm, upload | POST /api/v1/analysis, GET /api/v1/analysis/{id}     | analyses, files        | analysisProvider, fileProvider | P02-S02                      | /verify-journey J101 |
| J102  | M2        | DashboardPage → AnalysisDetailPage → ExportDialog | request export           | GET /api/v1/analysis/{id}, GET /api/v1/profile/export | analyses, audit_log    | exportProvider             | P02-S03-T001..T002           | /verify-journey J102 |
| ...   | ...       | ...                                         | ...                      | ...                                                  | ...                    | ...                        | ...                          | ...                  |

>>> MODELO: si un journey cruza menos de 2 pantallas, NO es un journey — es una feature; queda en §3.2 y NO se mete aquí. Si una pantalla / endpoint / tabla referenciada aún no existe en TECHNICAL_GUIDE, créala primero ahí.

#### 3.7.1 Reglas de la matriz (no negociables)

- Una fila por journey. Mínimo 2 pantallas por journey.
- Toda celda apunta a IDs que existen en su sección canónica.
- Slices acepta los 4 formatos descritos arriba (TASK_ID, rango, step ref, phase ref). El bootstrap los expande automáticamente.
- Pipes literales dentro de una celda se escapan como `\|` (ej. `tap Continue with {Google\|Apple\|Microsoft}`). El parser los respeta.
- Las celdas que de verdad no aplican (ej. journey 100% client-side sin endpoint) usan el sentinel `(none)` o `—` — el validador los ignora.
- Verificación siempre `/verify-journey JXXX` (waiver explícito documentado solo en casos extremos).
- Milestone obligatorio (M1..Mn de §4).

---

## 4. Milestones

### 4.1 Definición

> 🔗 **CABLEADO de §4** — cada milestone aquí debe estar simultáneamente en:
>
> 1. **Mapeo técnico** → `*_TECHNICAL_GUIDE.md §13` (tabla milestone → features → rutas → endpoints → tablas → AI). Si declaras M2 aquí pero no aparece en §13, no hay contrato técnico.
> 2. **Slices agrupados** → `*_IMPLEMENTATION_CHECKLIST.md` (slices Phase 2 + Phase 3 que componen el milestone). Sin grupos cableados no hay demo posible.
> 3. **Demo script verificable** → cada paso del demo script (login, click, submit, verificar resultado) debe ser ejecutable en `/verify-slice` o `/verify-journey`. Si declaras "Verificar X" pero X no tiene endpoint ni pantalla, drift inmediato.

>>> MODELO: milestones concretos con demo script. Cada milestone = motor + feature que expone ese motor.
>>>
>>> **Milestone N: {Nombre}**
>>> **Objetivo**: {valor entregable al usuario}
>>> **Motor requerido**: {componentes del §3.1}
>>> **Features requeridas**: {pantallas del §3.2}
>>> **Backend**: endpoints que deben responder.
>>> **Demo script**:
>>> 1. Abrir Chrome en `localhost:5000`.
>>> 2. Login con test@user.com.
>>> 3. Click en {botón}.
>>> 4. Rellenar {datos concretos}.
>>> 5. Verificar que aparece {resultado concreto con datos reales del backend}.
>>> **Tras entrega**: {qué puede hacer el usuario end-to-end}.
>>>
>>> MÍNIMO 3 milestones. Cada milestone debe entregarse en <1 semana de trabajo humano equivalente.

### 4.2 Reglas de milestone

🔒 **HEREDADO**: cada milestone funciona end-to-end Flutter → FastAPI → Supabase con datos reales. Backend health + todos los endpoints del milestone respondiendo. No N+1 hasta que N funciona al 100%. ALL tests verdes para milestones acumulados. `flutter build web` sin errores.

---

## 5. Modo de Trabajo

🔒 **HEREDADO ÍNTEGRAMENTE** — ver `docs/base-app/instrucciones.md §5`. Principios, flujo por slice TDD-first, Clean Architecture, patrones DRY/KISS/YAGNI, testing, doc oficial obligatoria. **NO REDEFINIR**.

---

## 6. i18n — keys específicas de la app

🔒 **HEREDADO**: ES/EN/FR con `.arb` + `gen-l10n`. Base ya tiene auth, profile, admin keys.

>>> MODELO: lista de keys que tu app añade:
>>> ```
>>> {
>>>   "contractAnalysisTitle": "Análisis de contrato",
>>>   "uploadContractHint": "Sube un PDF para empezar",
>>>   ...
>>> }
>>> ```
>>> Traducir cada key a EN + FR. Si tu app tiene terminología específica de dominio (legal, médico, etc.), cuidado con traducción literal — dejar notas para el traductor si hace falta.

---

## 7. Theme

🔒 **HEREDADO**: `ThemeData` + tokens + shared widgets. CERO valores inline.

>>> MODELO: si TU app necesita branding específico (logo, color primario distinto del default azul de la base), documentar aquí:
>>> - Logo: path + variantes (horizontal, icon-only, dark, light).
>>> - Color primario override: `AppColors.primary = Color(0xFF{tu_color})`.
>>> - Typography: si usas una fuente distinta de Inter.
>>> - Si nada cambia: "HEREDADO — sin overrides".

---

## 8-9. Prioridades de ejecución + Git

🔒 **HEREDADO** — ver `docs/base-app/instrucciones.md §8-9`.

---

## 10. Criterios de Aceptación

🔒 **HEREDADO fijos**: `flutter test` + `flutter analyze` + `flutter build web` + `pytest` + `ruff` + `mypy` todo verde. Clean Architecture. Cero hardcodeado/duplicado/muerto.

>>> MODELO: 5+ criterios específicos del dominio de TU app. Ej:
>>> - [ ] El motor de análisis devuelve al menos 1 sugerencia por cada cláusula marcada como "riesgo alto".
>>> - [ ] El tiempo de análisis de un contrato <50 páginas es <30s.
>>> - [ ] La exportación del informe en PDF mantiene el formato de tabla y cumple WCAG AA de contraste.
>>> - [ ] Los 4 métodos de login funcionan y el usuario aterriza en la home con su nombre cargado de Supabase.

---

## 11. Restricciones técnicas

🔒 **HEREDADO**: stack completo pineado en `docs/base-app/BASEAPP_TECHNICAL_GUIDE.md §2`.

### 11.0 Library Discovery Pass — OBLIGATORIO antes de §11.1

> 🔗 **CABLEADO de §11.0** — cada decisión USAR / DEFERRED aquí debe estar simultáneamente en:
>
> 1. **Detalle técnico** → `*_TECHNICAL_GUIDE.md §2.0` (paquete + URL + frontend/backend + justificación + alternativa descartada + slice donde se introduce). Sin §2.0, el `developer` no sabe qué importar.
> 2. **Slice de introducción** → `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, una fila explícita que añade la lib en `pubspec.yaml` o `pyproject.toml` y refactoriza el primer consumidor. Sin este slice, la lib queda en el limbo: declarada pero nunca instalada.
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
> - El `official-docs-researcher` corre antes del developer en CADA slice y resuelve la versión exacta cuando se introduce la lib en `pubspec.yaml` / `pyproject.toml`. El lockfile fija la versión, no este documento.
>
> **Reglas no negociables** (extracto — completas en `PROMPT_SOURCE_OF_TRUTH_DAG.md §7`):
> - NO duplicar el stack heredado de base-app (Riverpod, GoRouter, supabase_flutter, flutter_secure_storage, freezed, FastAPI, SQLAlchemy 2 async, Pydantic v2, LangChain, LangGraph, pgvector, etc.).
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
| {Forms y validación} | {USAR \| CUSTOM \| NO APLICA \| DEFERRED} | {ej: form builder con validación tipada compatible con Riverpod} | {ej: 1-2} |
| {Procesamiento PDF backend} | {USAR \| ...} | {ej: parser de PDF nativo (texto, sin OCR)} | {ej: 1} |
| {...} | {...} | {...} | {...} |

>>> **Áreas a recorrer** (ver descripción de cada una en `PROMPT_SOURCE_OF_TRUTH_DAG.md §3`). Evalúa las que apliquen a TU app:
>>>
>>> Frontend Flutter: forms y validación · iconografía · componentes UI extra · cache de imágenes · file pickers · chat/streaming AI · charts · animations · layouts responsive · codegen · deep links · date/time avanzado · maps · pagos · push · crash reporting · permissions nativos · almacenamiento offline.
>>>
>>> Backend: procesamiento PDF · procesamiento Office · procesamiento imagen/video · HTTP a APIs externas · jobs/queues · email custom · scraping · validaciones específicas (phones, IDs, IBAN) · extensiones cripto · observabilidad backend · storage no-Supabase.
>>>
>>> BBDD: extensiones Postgres específicas (pg_trgm, unaccent, pgcrypto, PostGIS).
>>>
>>> AI/ML: structured outputs · constrained generation · prompt eval · RAG metrics · token counting · loaders/chunkers específicos.
>>>
>>> Si una de estas áreas NO aplica a tu app, omítela — basta evaluar las que sí (mínimo 6). Si descubres una que no está en la lista pero aplica a tu app, añádela.

### 11.1 Paquetes adicionales — detalle (referencia a §2.0 del TECHNICAL_GUIDE)

>>> MODELO: el detalle técnico (nombre exacto del paquete + URL oficial + justificación + alternativa descartada + slice donde se introduce) va en `*_TECHNICAL_GUIDE.md §2.0` — NO se duplica aquí.
>>>
>>> Aquí en §11.1 basta una **lista resumen** de las decisiones USAR / DEFERRED del §11.0, en formato:
>>>
>>> - **<Área>**: `<paquete>` (sin versión — la pinea el lockfile al implementar). Ver `*_TECHNICAL_GUIDE.md §2.0` para detalle.
>>>
>>> Si tu §11.0 declaró todas las áreas como CUSTOM o NO APLICA: "HEREDADO — sin adiciones; library discovery pass declaró todas las áreas como NO APLICA o cubiertas por base-app."

### 11.2 Paquetes prohibidos (HEREDADO)

- Cualquier alternativa al stack heredado (no traigas otro state manager, otro router, otro ORM, otro HTTP cliente).
- Librerías abandonadas (sin commits en últimos 6 meses; 2 meses para AI/ML).
- Tokens en `SharedPreferences` / `localStorage` directo.
- Dependencias síncronas en pipelines async (preferir async-first).
- Cualquier dependencia que requiera CORS `*` o CSP laxa.
- Librerías con license incompatible (GPL viral, comerciales con field-of-use restrictions) sin ADR explícito.

---

## 12. Plataforma

🔒 **HEREDADO**: Flutter Web primero, mobile después, mismo codebase. Responsive. Platform abstractions para storage + OAuth.

>>> MODELO: si tu app tiene funcionalidad que varía POR PLATAFORMA, documentar aquí:
>>> - Camera / photo capture: mobile nativo, web file picker.
>>> - Notificaciones push: FCM/APNs mobile, web push opcional.
>>> - Pagos: Stripe web, App Store / Play Store in-app purchases en mobile.
>>> - File system access: limitado en web, amplio en mobile con permisos.
>>> - Biometric auth: Face ID / fingerprint mobile, no web.
>>>
>>> Si nada varía: "HEREDADO — sin variación por plataforma".

---

## 13. Riesgos

>>> MODELO: 3+ riesgos específicos del dominio de TU app con mitigación concreta. Ej:
>>> - **Riesgo**: Los PDFs de contratos tienen formato muy variable → parsing inconsistente.
>>>   **Mitigación**: Pipeline de ingestion con fallback a OCR (tesseract) si pypdf falla. Dataset de validación con 50 PDFs diversos testeado antes de release.
>>> - **Riesgo**: LLM genera sugerencias legalmente incorrectas.
>>>   **Mitigación**: Banner "Esto no constituye asesoramiento legal" + feedback loop con validación profesional + sistema de reportes.
>>> - **Riesgo**: Costes de LLM escalan sin control.
>>>   **Mitigación**: Rate limit por user + cache de análisis recientes + alert de consumo en Admin AI.

---

## 14. Logging y Observabilidad

🔒 **HEREDADO**: structlog + flag verbose + request_id + audit_log + Prometheus.

>>> MODELO: si tu app necesita logs/métricas específicas (ej: métricas de negocio como "contratos analizados/hora"), listar aquí:
>>> - Métricas custom: nombre + tipo (counter/histogram/gauge) + labels.
>>> - Audit log actions nuevas: ej `contract_uploaded`, `analysis_completed`, `suggestion_accepted`.

---

## 15. Seed Data

🔒 **HEREDADO**: bootstrap_users + bootstrap_ai_providers.

>>> MODELO: tu app puede necesitar datos demo específicos para milestones:
>>> - Milestone N: X contratos de ejemplo, Y usuarios con historial.
>>> - Script: `api/seeds/bootstrap_{tu_feature}.py`.
>>> - Datos realistas, no Lorem ipsum. Idempotente.

---

## 16. Protocolo de Entrega

🔒 **HEREDADO**.

---

## 17. Visualización

📋 **SI APLICA**:
>>> MODELO: si diseñas mockups previos de las pantallas nuevas, guardarlos en `docs/visualization/{feature}/`. No obligatorio si usas el design system directamente.

---

## 18. Relación con base-app

🔒 **CONTRATO DE HERENCIA** (heredado, no modificable):

**Lo que la base provee** (y tu feature-app NO toca):
- `api/src/shared/*`
- `api/src/features/{auth, profile, admin_ai, ai}` (excepto subcarpetas de extensión: `features/ai/agents/`, `deep_agents/`, `graphs/`, `tools/`, `prompts/`, `rag/` donde TU app añade).
- Tablas `profiles`, `llm_providers`, `embedding_providers`, `audit_log`, `account_deletion_requests`, `conversations`, `messages`, `documents`, `doc_chunks`, checkpoints LangGraph.
- Endpoints `/auth/*`, `/api/v1/profile/*`, `/api/v1/admin/ai/*`, `/api/v1/ai/status`, `/health`, `/ready`, `/live`, `/metrics`.
- Pantallas Flutter: `LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`, `ProfilePage`, `AdminAIPage`, `ShowcasePage`.
- Design system (`core/theme/`, `shared/widgets/`).
- Middleware request_id + security headers + audit + rate limit.

**Lo que TU app añade**:
- Migraciones nuevas en `api/alembic/versions/` para las tablas del dominio.
- Features nuevas en `api/src/features/{tus-features}/`.
- Pantallas nuevas en `app/lib/features/{tus-features}/`.
- Rutas nuevas en `app_router.dart`.
- Agents / deep_agents / graphs / tools / prompts / RAG config específicos del motor en las subcarpetas de `api/src/features/ai/`.
- Keys de i18n nuevas en los 3 `.arb`.
- Endpoints nuevos bajo `/api/v1/{tu-feature}/`.

Mejoras a la base se propagan **upstream** (repo base-app) + cherry-pick. No fork de la base desde feature-apps.

---

## 19. Verificación de cableado pre-entrega — OBLIGATORIO

> 🔗 **Antes de devolverme este fichero, recorre TODA esta checklist mentalmente y verifica que cada wire está cerrado**. Si alguno falla, vuelves al template y arreglas ANTES de entregar. ChatGPT no entrega un `instrucciones.md` con cableado roto. El validador `scripts/check-journey-matrix.sh --strict` y el bootstrap fallarán si hay drift.

### 19.1 Wires desde §3.1 (MOTOR)

Para CADA componente declarado en §3.1, confirmar en orden:

- [ ] Tiene **entity** declarada en `*_TECHNICAL_GUIDE.md §6.3`.
- [ ] Tiene **tabla(s) DB** declarada(s) en `*_TECHNICAL_GUIDE.md §10.3` con SQL completo + FKs + índices.
- [ ] Tiene **endpoint(s)** declarado(s) en `*_TECHNICAL_GUIDE.md §6.2` con method + path + req + res + auth + errors.
- [ ] Si tiene AI: tiene **agent / graph / deep_agent** + **tools** + **prompts** + **RAG config** declarados en `*_TECHNICAL_GUIDE.md §10.4`.
- [ ] Tiene **1+ slice Phase 2** en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (db / api / ai).
- [ ] Las **reglas de negocio** declaradas aquí se cumplen como invariantes en `*_TECHNICAL_GUIDE.md §12` (Constraints & Invariants).

### 19.2 Wires desde §3.2 (FEATURES)

Para CADA feature declarada en §3.2, confirmar en orden:

- [ ] Tiene **pantalla(s)** declarada(s) en `*_TECHNICAL_GUIDE.md §6.1` con ruta + page + auth + descripción.
- [ ] Cada **endpoint que consume** existe en `*_TECHNICAL_GUIDE.md §6.2` (sale del motor §3.1).
- [ ] Declara los **6 estados marginales** (loading / empty / error_network / error_validation / permission_denied / success). Si alguno no aplica de verdad, está marcado `n/a` con razón.
- [ ] Declara su **Next action** tras success.
- [ ] Tiene **1+ slice Phase 3** en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (flutter o journey).

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
- [ ] Su **demo script** es ejecutable paso a paso usando endpoints / pantallas que YA existen en los otros 2 docs.

### 19.5 Wires desde §11.0 (LIBRARY DISCOVERY)

Para CADA decisión **USAR / DEFERRED** declarada en §11.0:

- [ ] Tiene **fila completa** en `*_TECHNICAL_GUIDE.md §2.0` con paquete + URL + frontend/backend + justificación + alternativa descartada + slice de introducción.
- [ ] **NINGUNA fila lleva versión pineada** (debe decir literal `pendiente — official-docs-researcher confirmará al implementar`).
- [ ] Tiene **slice de introducción** real en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (la slice que añade la lib en `pubspec.yaml` / `pyproject.toml` y refactoriza el primer consumidor).
- [ ] Aparece en el **resumen §11.1** de este doc.

### 19.6 Drift checks — cero tolerancia

- [ ] **Cero `>>> MODELO:`** restantes en el fichero filled.
- [ ] **Cero `📋 SI APLICA`** sin resolver (o rellenas o eliminas la sección).
- [ ] **Cero `🔒 HEREDADO`** modificados (los placeholders informativos se quedan tal cual).
- [ ] **Cero referencias** a IDs (rutas, endpoints, tablas, slices, JIDs) que no existan en su doc destino.
- [ ] Si hay AI/ML libs en §11.0: están declaradas como `pendiente — official-docs-researcher confirmará` (cambian cada semanas, no inventes versiones).

### 19.7 Última prueba mental antes de entregar

Hazte estas 3 preguntas:

1. **¿Si Claude Code lee §3.1, encuentra TODO el contrato técnico necesario en TECHNICAL_GUIDE para implementar el motor?** Si la respuesta es "necesita inferir algo", falta cableado.
2. **¿Si Claude Code lee §3.7 (Journey Matrix), puede expandir cada celda a un identifier que existe en otra sección?** Si una celda apunta al vacío, falta cableado.
3. **¿Si el `planner` selecciona el primer slice del Coverage Registry, encuentra origen claro en §3.1 / §3.2 / §3.7 + contrato técnico claro en §6.1 / §6.2 / §6.3 / §10.3 / §10.4?** Si tiene que adivinar, falta cableado.

Si las 3 son "sí", entrega. Si alguna es "no", arregla y vuelve a verificar.


## Production hardening actual

Usa source-of-truth acumulativo baseline+vN, `Risk level`, `Verify mode`, phases <=12 slices, steps <=10 slices, journeys reales multi-superficie y verify con datos reales/prod-like. Ejecuta bootstrap + check-task-dag + check-journey-matrix + check-wiring-contract antes de waves.
