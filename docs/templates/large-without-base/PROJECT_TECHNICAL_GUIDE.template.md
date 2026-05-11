# {{APP_NAME}} — Technical Guide (large app sin baseline snapshot)

## Screen/Journey Lane Redactor Contract

- No modeles la app como `backend/API primero`, luego `frontend`, y `UX polish` al final. Esa separación rompe la pantalla aunque los tests pasen.
- Cada pantalla importante debe nacer de una **screen/journey lane**: contrato de pantalla + contrato API/datos + implementación conectada + estados UX obligatorios + verificación del journey.
- Las slices de API/backend pueden existir separadas sólo si son foundation real o contrato técnico que alimenta una pantalla/journey nombrado en `Journey refs`.
- Criterio de cierre de pantalla: datos reales/proporcionados conectados front -> back -> DB, estados `loading`, `empty`, `error_network`, `error_validation`, `permission_denied` cuando aplique, `success`, navegación/next action, responsive básico y accesibilidad básica.
- Tamaño recomendado: pantalla crítica 3-6 slices; módulo/journey lane 8-15 slices. No hagas una slice por botón/componente pequeño; tampoco cierres una pantalla sólo porque compila.
- Defectos dentro de la pantalla actual van por `validator/tester -> debugger -> retest`. Sólo crea FU si falta trabajo nuevo fuera de scope: pantalla, endpoint, tabla, journey, contrato de datos reales o decisión humana no declarada.

> **SIN BASELINE**: define stack, estructura y patterns completos desde `STACK_PROFILE.yaml`.
> **TU TRABAJO**: describir el recurso técnico completo de esta app nueva. Nada se hereda de `docs/product-baseline/` salvo que el usuario lo pida explícitamente.
> Rellenar `>>> MODELO:`. Resolver secciones no aplicables como `NO APLICA` con motivo.

> Perfil: **large-without-base**. App grande nueva desde cero; AnyStack permitido vía `STACK_PROFILE.yaml`, sin asumir ningún framework salvo que el perfil lo declare.

---

## 🔗 Contrato de Cableado — léelo ANTES de empezar a rellenar

> Este documento traduce el motor + features de `instrucciones.md` a recurso técnico ejecutable, y es la **fuente** que el `*_IMPLEMENTATION_CHECKLIST.md` consume para generar slices. Cada elemento aquí debe estar simultáneamente declarado en `instrucciones.md` (origen conceptual) y referenciado en el `CHECKLIST` (ejecución).
>
> **Wires ENTRANTES** (cada item de `instrucciones.md` debe convertirse en recurso aquí):
>
> | Sección de `*_TECHNICAL_GUIDE.md`        | Espera de `instrucciones.md`                        | Genera en `*_IMPLEMENTATION_CHECKLIST.md`                  |
> |------------------------------------------|------------------------------------------------------|------------------------------------------------------------|
> | §2.0 cada lib **USAR / DEFERRED**         | §11.0 mismo área funcional                          | slice que añade la lib en el manifiesto de dependencias real |
> | §6.1 cada **ruta/pantalla frontend**       | §3.2 (feature) o §3.6 (journey)                     | slice frontend o journey en Phase 3                       |
> | §6.2 cada **endpoint API**                | §3.1 (motor) o §3.2 (feature consume)               | slice api en Phase 2                                       |
> | §6.3 cada **entity**                      | §3.1 (componente del motor)                         | slice domain Phase 2 + slice migration §10.3 paralela      |
> | §10.3 cada **tabla DB**                   | §3.1 (entities del motor) + §10.4 si AI persistente | slice migration Phase 2 (`000N_<feature>.py`)              |
> | §10.4 cada **agent / graph / tool**       | §3.1 (componente del motor con AI)                  | slice ai Phase 2 + smoke test                              |
> | §13 cada **milestone técnico**            | §4 (milestones de instrucciones)                    | grupo de slices Phase 2 + Phase 3                          |
>
> **Regla de oro del cableado**: este doc **NO inventa** identifiers. Si declaras aquí algo que NO está en `instrucciones.md`, hay drift (probablemente una feature inventada). Si declaras aquí algo que NO tiene slice en `CHECKLIST`, queda sin implementar (probablemente un endpoint olvidado).
>
> **Cómo saber si está bien cableado**: ejecuta mentalmente la verificación final en §16 antes de entregar. Si fallas alguna casilla, vuelves al template y arreglas antes de mandarme el fichero.

---

## 1. Overview específico

>>> MODELO: diagrama ASCII de TU motor + features desde cero. Mostrar cómo interactúan frontend, API, DB y componentes AI si aplica. Ejemplo:
>>>
>>> ```
>>>  Usuario
>>>    │
>>>    ▼
>>>  [{{PrimaryActionPage}}] ──► {{primary_endpoint}} ──► [{{DomainEngine}}]
>>>                                                                ├─ normalize_input_node (input real proporcionado)
>>>                                                                ├─ classify_or_validate_node (reglas/AI si aplica)
>>>                                                                └─ recommend_or_result_node (reglas/AI si aplica)
>>>                                                                      │
>>>                                                                      ▼
>>>                                                                 [optional reference store: {{provided_reference_data}}]
>>> ```
>>>
>>> Sin este diagrama no queda claro qué construyes. Es obligatorio.

---

## 2. Stack — recurso completo

⚙️ **DEFINIR PARA ESTE STACK**: resume el stack declarado en `STACK_PROFILE.yaml` (frontend, backend, DB, auth, AI, test/lint/build). No inventes frameworks, rutas ni comandos si el perfil declara otro stack.

### 2.0 Library Discovery Pass — formaliza decisiones de `instrucciones §11.0`

> 🔗 **CABLEADO de §2.0** — cada fila aquí cierra el wire de la lib:
>
> 1. **Origen** → fila correspondiente USAR/DEFERRED en `instrucciones.md §11.0` (misma "Área funcional"). Si no aparece allí, hay drift.
> 2. **Destino** → slice en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, columna "Introducida en slice". Esa slice añade la lib al dependency manager y refactoriza el primer consumidor real.
> 3. **Resumen ligero** → mención simple en `instrucciones.md §11.1` (sin versión, referencia a este §2.0).
>
> Si una fila aquí NO tiene slice de introducción real → la lib se queda en el limbo. Si tiene slice pero no aparece en §11.0 → drift de criterio (no pasaste por Library Discovery Pass).

> **Por qué existe**: cada decisión USAR/DEFERRED de `instrucciones.md §11.0` se documenta aquí con detalle técnico (paquete, URL oficial, justificación, slices ahorrados, alternativa descartada, slice de introducción). Esta es la fuente que el `planner` lee para que el `developer` no reescriba código ya empaquetado.
>
> **Política de versiones — IMPORTANTE**:
> - **NO pinees versión específica en este documento**. Las versiones cambian cada semanas; lo que escribas aquí puede no existir o estar deprecated cuando se implemente la slice.
> - El `official-docs-researcher` corre antes del `developer` en CADA slice. Es quien resuelve la versión exacta al introducir la lib en el manifiesto de dependencias correcto.
> - El **lockfile** (el lockfile declarado por el stack) fija la versión real. Este documento solo declara intención, no recurso de versión.
> - Si dudas de que el paquete existe o está mantenido, déjalo como `<librería candidata, official-docs-researcher confirmará>` y escribe en "Frontend / Backend" + "Justificación" para guiar al researcher.
>
> **Reglas estructurales**:
> - Una fila por decisión USAR / DEFERRED. Las CUSTOM y NO APLICA no se replican aquí (van solo en §11.0).
> - Cada librería USAR debe tener un `Slice ID` mencionado en el CHECKLIST Coverage Registry — la slice que añade la lib al dependency manager (ej: la slice `P03-S01-T001` que introduce el form builder y refactoriza `LoginForm`).
> - Si la decisión NO es obvia (≥2 alternativas reales evaluadas con criterio) → añadir ADR-001+ en §15.

>>> MODELO: completa la tabla con TODAS las decisiones USAR / DEFERRED de `instrucciones §11.0`. Recuerda: **sin versiones**.
>>>
>>> | Área (ref §11.0) | Paquete propuesto | URL oficial | Frontend / Backend | Justificación + slice ahorrado | Alternativa descartada | Versión | Introducida en slice |
>>> |---|---|---|---|---|---|---|---|
>>> | {ej: Forms} | `<paquete>` | {pub.dev/PyPI/...} | Frontend / Backend | {qué problema resuelve, cuántas slices ahorra} | {alternativa real considerada y motivo de rechazo} | pendiente — official-docs-researcher confirmará al implementar | {ej: P03-S01-T002} |
>>> | {ej: parsing/validación de entrada backend} | `<paquete>` | {URL} | Backend | {ej: motor §3.1 procesa el formato real proporcionado; ahorra 1 slice custom} | {ej: alternativa más compleja — no aplica si los datos proporcionados ya vienen normalizados} | pendiente — official-docs-researcher confirmará | {ej: P02-S04-T002} |
>>> | ... | ... | ... | ... | ... | ... | ... | ... |
>>>
>>> Si tu app no añade ninguna lib (todas las áreas resueltas con CUSTOM o NO APLICA):
>>>
>>> > "Sin librerías adicionales — Library Discovery Pass declaró todas las áreas relevantes como NO APLICA o resueltas con código <20 líneas custom. Detalle: ver `instrucciones.md §11.0`."
>>>
>>> Si dudas del nombre exacto del paquete, marca el campo "Paquete propuesto" como `<librería candidata: tipo de lib buscada>` y deja que el `official-docs-researcher` la cierre al implementar.

### 2.1 Stack — paquetes auxiliares (devDeps, plugins, codegen)

>>> MODELO: si tienes paquetes auxiliares NO cubiertos por §2.0 (lint plugins, codegen runners, dev tools que no afectan a runtime), lístalos aquí. Mismo principio: SIN versión específica.
>>>
>>> | Componente | Paquete | URL oficial | Por qué |
>>> |---|---|---|---|
>>> | {ej: Lint extra} | `<paquete de lint>` | {URL} | {ej: reglas más estrictas que el linter base del stack} |
>>> | {ej: Codegen runner} | `<paquete de build runner>` | {URL} | {ej: necesario para el codegen declarado en el stack} |
>>>
>>> Si no añades nada: "Ver §2.0 — sin paquetes auxiliares adicionales".

---

## 3. Comandos — adiciones

⚙️ **DEFINIR PARA ESTE STACK**: install, run, migrate, load-provided-data, test, lint, build — todos derivados de `STACK_PROFILE.yaml` y scripts reales del repo.

>>> MODELO: comandos específicos de tu app. Ejemplos comunes:
>>> - `{{provided_data_load_cmd}}`: cargar datos reales proporcionados para verificación.
>>> - `{{data_import_cmd}}`: cargar datos/referencias reales proporcionados, si aplica.
>>> - `{{model_training_cmd}}`: si entrenas modelos locales.
>>>
>>> Si nada extra: "Sin comandos adicionales".

---

## 4. Estructura del proyecto — adiciones

⚙️ **DEFINIR PARA ESTE STACK**: árbol completo propio usando los paths reales de `STACK_PROFILE.yaml`. No copies extensiones ni carpetas de otro stack. Usa `{{frontend.module_root}}`, `{{backend.module_root}}`, `{{frontend.test_root}}`, `{{backend.test_root}}`, `{{db.migrations_root}}` y nombres de dominio reales.

>>> MODELO: añade tu árbol NUEVO, solo carpetas/ficheros que tu app crea. Ejemplo agnóstico:
>>>
>>> ```text
>>> {{frontend.module_root}}/features/{{resource}}/
>>> ├── domain/
>>> │   ├── {{PrimaryEntityFile}}
>>> │   ├── {{DomainValueObjectFile}}
>>> │   └── {{DomainPolicyFile}}
>>> ├── data/
>>> │   ├── {{ResourceRepositoryFile}}
>>> │   ├── {{ResourceApiClientFile}}
>>> │   └── {{ResourceDtoFile}}
>>> └── presentation/
>>>     ├── {{PrimaryActionPageFile}}
>>>     ├── {{ListPageFile}}
>>>     ├── {{ResultPageFile}}
>>>     └── {{StateManagementFiles}}
>>>
>>> {{backend.module_root}}/{{resource}}/
>>> ├── domain/{{DomainFiles}}
>>> ├── application/{{UseCaseFiles}}
>>> ├── infrastructure/{{PersistenceFiles}}
>>> ├── api/{{RouteAndSchemaFiles}}
>>> └── tests/{{IntegrationTestFiles}}
>>>
>>> {{db.migrations_root}}/{{migration_file}}
>>> ```
>>>
>>> Si tu stack no tiene frontend o backend, marca el área como `none` en `STACK_PROFILE.yaml` y no inventes carpetas.

---

## 5. Arquitectura

### 5.1 Componentes nuevos

>>> MODELO: tabla de componentes que añades con responsabilidad + dependencias.
>>>
>>> | Módulo | Responsabilidad | Depende de |
>>> |--------|-----------------|-----------|
>>> | `features/{{resource}}` | operaciones del recurso + lanzar proceso principal | `features/ai`, `shared/auth` |
>>> | `features/ai/graphs/{{domain_process_graph}}` | <graph_or_workflow_lib_declarada> que orquesta parse/validación → decisión → resultado | `features/ai/tools`, `features/ai/llms` |
>>> | `{{backend.module_root}}/{{domain}}/{{provided_data_loader}}` | Loader de datos/referencias proporcionados para la capability declarada | `{{domain_processing_module}}`, `{{optional_reference_index}}` |

### 5.2 Flujo de datos específico

>>> MODELO: diagrama del flujo de una request clave end-to-end. Ejemplo:
>>>
>>> ```
>>> Usuario ejecuta acción principal → {{PrimaryActionPage}}
>>>   → {{primary_endpoint}}
>>>     → JWT verify + get_current_user
>>>     → {{MainUseCase}} use case
>>>       → {{ResourceRepository}}.save(input, user_id) → persistencia declarada + {{table}}
>>>       → Enqueue background task: {{DomainProcess}}
>>>     ← respuesta success con id persistido
>>>   → Frontend navega a la ruta de resultado declarada (polling, SSE o patrón equivalente)
>>> 
>>> [background]
>>> {{DomainProcess}} use case
>>>   → {{domain_process_graph}}.ainvoke(resource_id)
>>>     → parse_node (input real proporcionado → estructura interna)
>>>     → decision_node (servicio/AI si aplica → resultado de dominio)
>>>     → result_node (servicio/reglas/AI si aplica → resultado verificable)
>>>     → persist results in DB
>>> ```

### 5.3 Decisiones de diseño

>>> MODELO: 3+ decisiones relevantes con alternativas y por qué elegiste una. Ej:
>>>
>>> | Decisión | Alternativas | Elegida | Razón |
>>> |---------|--------------|---------|-------|
>>> | Graph vs single agent para análisis | `create_agent` con tool de classify | `<graph_or_workflow_lib_declarada>` custom de 3 nodos | Control preciso del flow + checkpointing + debug |
>>> | Polling vs SSE para progreso | SSE streaming | Polling cada 2s | SSE añadiría complejidad; análisis dura 20-30s |
>>> | Persistir entradas reales en storage declarado vs re-cargar cada ejecución | Re-cargar cada ejecución | Storage | Auditoría + coste UX + permite reprocesar |

---

## 6. Interfaces — adiciones

### 6.1 Rutas/pantallas frontend

> 🔗 **CABLEADO de §6.1** — cada fila aquí cierra el wire de la pantalla:
>
> 1. **Origen** → feature en `instrucciones.md §3.2` (la pantalla expone esa feature) y/o journey en `instrucciones.md §3.6` (la pantalla es paso del flujo).
> 2. **Destino** → slice en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (`frontend` con la `<Page>` o `journey` si la pantalla solo existe como integración).
> 3. **Cross-check** → si la ruta aparece en `instrucciones.md §3.7` (Journey Matrix), columna "Pantallas", debe figurar AQUÍ con el mismo nombre/ruta.
>
> Si declaras una ruta aquí que NO está en §3.2 ni §3.6 → drift (pantalla inventada). Si una pantalla aparece en §3.7 pero no aquí → la ruta no existirá y `/verify-journey` fallará.

>>> MODELO:
>>>
>>> | Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/state handler | Estados UI obligatorios | Next action | Slice ID | Descripción |
>>> |------|------|------|--------------|----------------------|-------------------------|------------------------|-------------|----------|-------------|
>>> | /{{resource}} | {{Resource}}ListPage | Sí | J1 | GET /api/v1/{{resource}} | {{Resource}}ListState | loading, empty, error_network, success | abrir detalle o crear recurso | P03-S01-T001 | Lista de recursos del usuario |
>>> | /{{resource}}/new | {{Resource}}CreatePage | Sí | J1 | POST /api/v1/{{resource}} | {{Resource}}FormState | idle, uploading, error_validation, error_network, success | navegar a análisis | P03-S01-T002 | Subida + lanzar análisis |
>>> | /{{resource}}/{id} | {{Resource}}DetailPage | Sí | J1 | GET /api/v1/{{resource}}/{id} | {{Resource}}DetailState | loading, not_found, permission_denied, success | ver análisis | P03-S01-T003 | Detalle con metadata |
>>> | /{{resource}}/{id}/result | {{ResultPage}} | Sí | J1 | GET /api/v1/{{resource}}/{id}/result | {{ResultState}} | loading, empty, error_network, success | aceptar sugerencia o reanalizar | P03-S01-T004 | Resultados del motor con estados, explicación y acciones recomendadas |

### 6.2 Endpoints API nuevos

⚙️ **DEFINIR PARA ESTE STACK**: formato envelope `{data, meta, errors}`, versioning `/api/v1/`, auth via `get_current_user`.

> 🔗 **CABLEADO de §6.2** — cada endpoint aquí cierra DOS wires:
>
> 1. **Origen** → componente del motor en `instrucciones.md §3.1` (el endpoint expone una capability del motor) o feature en `§3.2` (el endpoint sirve a una pantalla).
> 2. **Destino obligatorio** → slice `api` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, **uno por endpoint** (schema + use case + repository + integration test + curl + logs). Excepción única: agrupación explícita en un slice de integración con justificación documentada.
> 3. **Cross-check** → si el endpoint aparece en `instrucciones.md §3.7` columna "Endpoints", debe figurar AQUÍ con el mismo method + path.
> 4. **Cross-check con tablas** → si el endpoint persiste, las tablas tocadas existen en §10.3.
>
> Endpoint declarado aquí sin slice → el orquestador no lo implementa, queda en el recurso pero no en el código. Endpoint sin consumidor explícito → drift de producto: no queda claro quién lo usa ni cómo se verifica.

>>> MODELO: tabla COMPLETA. CADA endpoint aquí DEBE tener un `Slice ID` propio en el CHECKLIST Coverage Registry, salvo que esté documentado como parte de un slice de integración ya existente. Todo endpoint debe tener `Consumidor front/journey`; si no tiene frontend, escribe `internal/no-front`, `webhook`, `background-job` o `admin-only` y justifica en la descripción.
>>>
>>> | Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
>>> |--------|------|---------|----------|------|--------|--------------------------|---------------------|----------|
>>> | POST | /api/v1/{{resource}} | multipart file | `{data: {resource_id}}` | Sí | 400, 401, 413 | {{Resource}}CreatePage / J1 | `{{table}}`, object storage declarado si aplica | P02-S02-T001 |
>>> | GET | /api/v1/{{resource}} | query params (cursor, limit) | `{data: [{{Resource}}], meta: {pagination}}` | Sí | 401 | {{Resource}}ListPage / J1 | `{{table}}` read | P02-S02-T002 |
>>> | GET | /api/v1/{{resource}}/{id} | — | `{data: {{Resource}}}` | Sí | 401, 404 | {{Resource}}DetailPage / J1 | `{{table}}` read | P02-S02-T003 |
>>> | POST | /api/v1/{{resource}}/{id}/process | — | `{data: {process_id, status: "queued"}}` | Sí | 401, 404, 409 | {{Resource}}DetailPage / J1 | enqueue domain process job | P02-S02-T004 |
>>> | GET | /api/v1/{{resource}}/{id}/result | — | `{data: {{ResultDto}}\|null, meta: {status, progress}}` | Sí | 401, 404 | {{ResultPage}} / J1 | `{{result_table}}` read | P02-S02-T005 |
>>> | DELETE | /api/v1/{{resource}}/{id} | — | 204 | Sí | 401, 404 | {{Resource}}DetailPage / account cleanup | `{{table}}` delete cascade | P02-S02-T006 |
>>>
>>> Formato errors: define un envelope único, por ejemplo `{code, message, field?, details}`.

### 6.3 Modelos de datos nuevos

> 🔗 **CABLEADO de §6.3** — cada entity aquí cierra TRES wires:
>
> 1. **Origen** → componente del motor en `instrucciones.md §3.1` (mismo nombre de entity).
> 2. **Persistencia** → tabla correspondiente en `§10.3` con SQL. Si la entity no se persiste, lo declaras explícitamente.
> 3. **Frontend** → DTO/model/adapter en el path real declarado en §4 y `STACK_PROFILE.yaml`.
>
> Entity declarada aquí sin tabla en §10.3 ni invariante en §12 → modelo huérfano. Entity declarada sin componente del motor en `instrucciones.md §3.1` → drift conceptual.

>>> MODELO: por cada entity de dominio nueva:
>>>
>>> **{{PrimaryEntity}}** (domain)
>>> ```python
>>> class {{PrimaryEntity}}(<schema_base>):
>>>     id: UUID
>>>     user_id: UUID
>>>     title: str
>>>     provided_input_ref: str  # object storage declarado URL
>>>     page_count: int
>>>     uploaded_at: datetime
>>>     process_status: Literal["pending", "processing", "done", "failed"]
>>> ```
>>>
>>> **{{SecondaryEntity}}** (domain)
>>> ```python
>>> class {{SecondaryEntity}}(<schema_base>):
>>>     id: UUID
>>>     resource_id: <id_type>
>>>     order: int
>>>     text: str
>>>     risk_level: Literal["low", "medium", "high"]
>>>     risk_rationale: str | None
>>> ```
>>>
>>> **Frontend equivalents** en `lib/features/{{resource}}/domain/entities/` y sus DTOs con generador/modelado declarado en `data/models/`.

### 6.4 Formato de errores específico

⚙️ **DEFINIR PARA ESTE STACK**: sealed classes `DomainError` + envelope.

>>> MODELO: códigos específicos de tu dominio. Ej:
>>> ```
>>> DOMAIN_001_INPUT_INVALID          (400)
>>> CONTRACT_002_PAGE_LIMIT_EXCEEDED  (413)
>>> CONTRACT_003_ANALYSIS_IN_PROGRESS (409)
>>> CONTRACT_004_ANALYSIS_FAILED      (502)
>>> ```

---

### 6.4 Navigation Contract

⚙️ **DEFINIR PARA ESTE STACK**: define routing, deep links, menú principal, estados marginales globales y next action para esta app nueva.

>>> MODELO: documenta el recurso de navegación completo. Si algo no aplica, marca `NO APLICA` con motivo:

>>> - Rutas nuevas de tu app que aceptan deep link → añade a §6.4.2.
>>> - Empty states o error states con contenido específico de tu dominio (ej: "Sin registros/resultados, carga el primer dato real proporcionado" en lugar del genérico).
>>> - Next actions específicas que enlazan tus journeys entre sí.
>>> - Si tu app introduce un nuevo tipo de menú (ej: tabs adicionales por rol), descríbelo aquí.

>>> Patrón de adición:

>>> ```markdown
>>> #### 6.4.7 Deep links propios

>>> | Ruta                        | Auth req | Schema superficie primaria | Schema superficie secundaria |
>>> |-----------------------------|----------|----------------------|-----------------------------|
>>> | /{{resource}}/:id/result               | sí       | tuapp://{{resource}}/:id/result | https://app.dominio/{{resource}}/:id/result |
>>> | /share/:token               | no       | tuapp://share/:token | https://app.dominio/share/:token |

>>> #### 6.4.8 Empty states de tu dominio

>>> - {{DashboardScreen}} sin resultados → ilustración custom + CTA de acción principal → ruta declarada
>>> - {{ListPage}} sin filtros aplicados → render del estado base
>>> ```

>>> Si no aplica navegación especial, escribe "NO APLICA — navegación simple cubierta por rutas de §6.1".


### 6.5 Verification Data Contract

> 🔗 **CABLEADO de datos reales para verify-slice / verify-journey** — cada journey o flujo verificable debe declarar de dónde salen los datos reales/proporcionados. El orquestador NO debe verificar con mocks, datos decorativos, datos inventados ni cargas no proporcionadas. Si faltan datos, el usuario los irá proporcionando y la slice debe bloquear o registrar follow-up hasta tenerlos.

>>> MODELO: una fila por journey o flujo crítico.
>>>
>>> | Flow/Journey | Persona/Rol | Datos reales/proporcionados requeridos | Fuente de datos reales proporcionados | Reset/Cleanup | Slices/Journeys |
>>> |--------------|-------------|-----------------------------------|------------------------|---------------|-----------------|
>>> | J1 primary-action-result | usuario real de prueba + dato/documento real proporcionado | usuario confirmado, entrada válida, resultado persistido, errores 400/413 reales | datos/documentos proporcionados por el usuario + carga SQL transaccional controlada | `scripts/dev-restart.sh --reset` + cleanup tablas del feature | J1, P02-S02-T001, P03-S01-T001 |
>>>
>>> Reglas:
>>> - `verify-slice` debe usar estas filas para preparar datos.
>>> - No insertar datos vía el endpoint que se está verificando; usa una carga externa de datos reales proporcionados y luego verifica el endpoint/UI.
>>> - Para servicios externos, usa sandbox oficial o credenciales test documentadas; nunca inventes respuestas mock en producción MVP.

## 7. Theme & Design System

⚙️ **DEFINIR PARA ESTE STACK**: tokens + componentes compartidos del framework declarado. CERO inline fuera del sistema de diseño.

>>> MODELO: override si necesitas (logo, color primario):
>>> - Logo/assets: `<frontend_module_root>/assets/logo/` o path equivalente.
>>> - Override colores en `AppColors` si hay branding: "AppColors.primary = Color(0xFF...)".
>>> - Componentes compartidos nuevos ESPECÍFICOS de tu dominio (ej: `DomainStatusIndicator(state)`, `DomainCard`): documentar aquí con props.
>>>
>>> Si nada custom: "Sin customización visual adicional".

---

## 8. Logging y Observabilidad

⚙️ **DEFINIR PARA ESTE STACK**: structlog + request_id + Prometheus base.

>>> MODELO: métricas custom específicas de tu motor:
>>> ```python
>>> domain_process_duration = Histogram(
>>>     "domain_process_duration_seconds",
>>>     "Duration of domain process",
>>>     ["outcome"],  # success|failed|timeout
>>> )
>>> ```
>>>
>>> Audit log actions nuevas: `resource_created`, `process_completed`, `recommendation_accepted`, `recommendation_rejected`.

---

## 9. Testing

⚙️ **DEFINIR PARA ESTE STACK**: comandos y frameworks de test reales desde `STACK_PROFILE.yaml`; tests contra DB real con datos proporcionados y E2E/visual cuando `Verify mode=human`.

### 9.1 Convenciones específicas

>>> MODELO: si tu motor requiere datos reales especiales proporcionados (datos/documentos/referencias reales proporcionados para validación), documenta cómo se reciben y cargan sin inventarlos:
>>> - Carpeta/ruta de entrada para datos/documentos reales proporcionados: `<data/provided/{{resource}}/>` o equivalente del stack.
>>> - Dataset de validación real proporcionado para el motor: `<data/provided/{{domain}}_validation.json>` con casos anotados por el usuario/equipo.

---

## 10. Backend / API — adiciones

### 10.1 Módulos del backend

>>> MODELO: tabla de módulos propios del dominio (ya enumerados en §5.1, referenciar ahí).

### 10.2 Identity/access strategy

⚙️ **DEFINIR PARA ESTE STACK**: identidad/acceso real de esta app (sesión/token/API keys u otro mecanismo declarado), middleware/dependency y roles/claims si aplica.

>>> MODELO: SOLO si tu app requiere roles/permisos específicos del dominio más allá de los roles base declarados. Ej: "Cliente premium" (claim custom en el proveedor auth declarado). Justificar y aceptar la complejidad añadida. Si no: "NO APLICA".

### 10.3 DB Schema — tablas nuevas

> 🔗 **CABLEADO de §10.3** — cada tabla aquí cierra DOS wires:
>
> 1. **Origen** → entity en `§6.3` (misma columna por campo) y componente del motor en `instrucciones.md §3.1`.
> 2. **Destino obligatorio** → slice `db` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry: una migración del stack declarado `000N_<feature>.py` con up + down probados, FKs cascade, índices. Tablas que nacen juntas y se verifican juntas pueden agruparse en una migración.
> 3. **Cross-check con journey matrix** → si la tabla aparece en `instrucciones.md §3.7` columna "Tablas DB", debe figurar AQUÍ con el mismo nombre.
>
> Tabla declarada sin migración en CHECKLIST → no se crea, los endpoints que dependen fallan en runtime.

>>> MODELO: SQL completo de cada tabla nueva. TODAS con FK al usuario/tenant real declarado por el stack, cuando aplique donde aplique para GDPR.
>>>
>>> ```sql
>>> CREATE TABLE {{resource_table}} (
>>>     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>>>     user_id UUID NOT NULL REFERENCES {{user_table}}(id) ON DELETE CASCADE,
>>>     title TEXT NOT NULL,
>>>     provided_input_ref TEXT NOT NULL,
>>>     input_size INT NULL,
>>>     process_status VARCHAR(20) NOT NULL DEFAULT 'pending',
>>>     uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
>>>     metadata JSONB NOT NULL DEFAULT '{}'::jsonb
>>> );
>>>
>>> CREATE INDEX {{resource_table}}_user_id ON {{resource_table}} (user_id);
>>> CREATE INDEX resources_process_status ON resources (process_status) WHERE process_status != 'done';
>>> ```
>>>
>>> Repetir por cada tabla. Migración reversible (up + down).

### 10.4 AI stack — motor específico

> 🔗 **CABLEADO de §10.4** — cada pieza AI aquí cierra DOS wires:
>
> 1. **Origen** → componente del motor con AI en `instrucciones.md §3.1` ("Componente AI" del bloque). Si declaras un graph aquí que no aparece como componente AI en §3.1, drift.
> 2. **Destino obligatorio** → slice `ai` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, con **smoke test** ejecutable (cada agent / graph / deep_agent / tool / prompt / reference-data loader independiente verificable). El `official-docs-researcher` valida versión + imports antes del developer.
> 3. **Cross-check con prompts versionados** → si declaras `prompts/system/{name}.md`, ese fichero existe en repo con versión + fecha en su cabecera.
>
> Tool/agent/graph aquí sin slice + smoke test en CHECKLIST → no se construye y los endpoints que dependen fallan o retornan respuestas no verificadas.

>>> MODELO: el corazón técnico. Detallar:
>>>
>>> #### Agents
>>> >>> MODELO:
>>> - `{{domain_agent}}.py`: `create_agent(model=..., tools=[input_parse, domain_classify], system_prompt="...")`. Cuándo se usa: consultas directas sobre un recurso ya procesado.
>>>
>>> #### Deep Agents
>>> >>> MODELO:
>>> - `{{domain_research_agent}}.py`: `create_deep_agent(model=..., subagents=[retriever_subagent, writer_subagent], ...)`. Cuándo se usa: preguntas complejas que requieren recuperar conocimiento de dominio + redactar resultado.
>>>
>>> #### Graphs
>>> >>> MODELO:
>>> - `{{domain_process_graph}}.py`: `<graph_or_workflow_lib_declarada>[{{DomainProcessState}}]` con nodos `parse → classify → suggest`. Checkpointer: `checkpointer declarado por el stack`. State:
>>>   ```python
>>>   class {{DomainProcessState}}(<state_type_declarado>):
>>>       resource_id: <id_type>
>>>       raw_text: str
>>>       items: list[{{SecondaryEntity}}]
>>>       results: list[{{ResultEntity}}]
>>>       recommendations: list[{{RecommendationEntity}}]
>>>   ```
>>>
>>> #### Tools
>>> >>> MODELO:
>>> - `{{input_parser}}.py`: `@tool def parse_provided_input(input_ref: str) -> str` (texto plano) o `@tool def parse_provided_input_to_segments(input_ref: str) -> list[str]`.
>>> - `{{domain_extractor}}.py`: tool que extrae unidades de dominio desde la entrada normalizada.
>>> - (Cualquier API externa que llames: incluirlo como tool).
>>>
>>> #### Prompts
>>> >>> MODELO:
>>> - `prompts/system/{{domain_agent}}.md`: system prompt base. Versionar explícitamente (incluir fecha + versión en el fichero).
>>> - Describir brevemente el prompt (NO pegar el contenido completo aquí).
>>>
>>> #### Referencias/knowledge base opcional
>>> >>> MODELO:
>>> - Qué ingesta: datos/referencias de dominio proporcionados por el usuario/equipo.
>>> - Loader: `{{provided_data_loader}}` en el módulo declarado por `STACK_PROFILE.yaml` (custom si aplica).
>>> - Splitter: `RecursiveCharacterTextSplitter` u otro splitter declarado, con overrides (ej: chunk_size adaptado al dominio).
>>> - Rerank: sí/no. Si sí, librería (Cohere rerank, cross-encoder).
>>> - Dimensión embedding: declarar desde el proveedor/modelo real elegido; no heredar valores por costumbre.

### 10.5 Backend logging

⚙️ **DEFINIR PARA ESTE STACK**.

---

## 11. Deploy

⚙️ **DEFINIR PARA ESTE STACK**: Docker multi-stage + docker-compose + CI/CD GitHub Actions + runbooks ops.

### 11.1 Variables de entorno adicionales

⚙️ **DEFINIR PARA ESTE STACK**: ver base guide §12.1.

>>> MODELO: variables ADICIONALES específicas de tu app:
>>>
>>> | Variable | Dev | Staging | Prod | Descripción |
>>> |----------|-----|---------|------|-------------|
>>> | `DOMAIN_API_KEY` | test-key | staging-key | prod-key | API externa de dominio |
>>> | `MAX_INPUT_SIZE` | 100 | 100 | 50 | Límite de tamaño/complejidad de entrada |

### 11.2 Build targets

⚙️ **DEFINIR PARA ESTE STACK**.

>>> MODELO: si tu app requiere builds especiales (signing específico para App Store con entitlements de dominio, deploy a hosting específico), documentar aquí.

### 11.3 Rollback strategy

⚙️ **DEFINIR PARA ESTE STACK** + añadir rollback específico si hay operaciones destructivas.

>>> MODELO: si tu motor hace operaciones irreversibles (borra datos del usuario, llama a APIs pagadas), documentar cómo manejar rollback.

---

## 12. Constraints & Invariants

⚙️ **DEFINIR PARA ESTE STACK**: Clean Architecture + file size + cero hardcoding + máx 1 proveedor AI activo + tokens secure + claves cifradas + audit log.

>>> MODELO: invariantes ESPECÍFICOS del dominio. Ej:
>>> - Una `{{PrimaryEntity}}` siempre pertenece a un único owner/tenant si aplica.
>>> - Una `{{SecondaryEntity}}` no puede existir sin su entidad padre si aplica (FK cascade).
>>> - Un resultado calculado no se auto-modifica fuera del flujo declarado; toda corrección queda auditada.
>>> - Una entrada que supera el límite declarado se rechaza con error trazable.
>>> - Ninguna sugerencia del AI se persiste sin campo `rationale` no-vacío.

---

## 12.1 Slice Traceability Contract

> Esta sección existe para que ChatGPT genere un CHECKLIST que el orquestador pueda ejecutar sin ambigüedad.
>
> Reglas:
> - Cada endpoint de §6.2 debe mapear a exactamente un `Slice ID` del CHECKLIST Coverage Registry.
> - Cada ruta/pantalla frontend de §6.1 debe mapear a un `Slice ID`, o a un journey slice si la ruta solo existe como paso de integración.
> - Cada tabla/migración de §10.3 debe mapear a un `Slice ID`.
> - Cada AI tool/agent/graph/deep_agent de §10.4 debe tener smoke test y `Slice ID` si añade comportamiento nuevo.
> - Los IDs se escriben en el CHECKLIST, no aquí. Aquí solo se mantiene la trazabilidad conceptual.
>
> Ejemplo esperado en el CHECKLIST:
>
> | Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
> |---|---|---|---|---|---|---|---|---|---|---|---|---|
> | P02-S02-T001 | api | `POST /api/v1/{{resource}}` | Step 2.2 | P02-S01-T001 | J1 | — | `POST /api/v1/{{resource}}` | {{resource_table}} | §3.1, §3.7 | §6.2, §10.3 | schema + use case + repo + integration test + curl + logs | `{{backend_test_cmd}}` + curl |

## 13. Milestones técnicos

> 🔗 **CABLEADO de §13** — cada fila aquí cierra el wire del milestone:
>
> 1. **Origen** → milestone con mismo ID en `instrucciones.md §4`. Si declaras M2 aquí que no está en §4, drift.
> 2. **Destino** → grupo de slices reales del `*_IMPLEMENTATION_CHECKLIST.md` (los slices Phase 2 y Phase 3 que componen el milestone). Sin slices reales, milestone decorativo.
> 3. **Cross-check denso** → cada celda (Features, Pantallas, Rutas, Endpoints, Tablas, AI) debe referenciar identifiers que ya existen en sus secciones canónicas (§6.1, §6.2, §10.3, §10.4). Cero referencias inventadas.

>>> MODELO: mapeo técnico de los milestones de instrucciones.md. Ej:
>>>
>>> | Milestone | Features | Pantallas frontend | Rutas nuevas | Endpoints nuevos | Tablas nuevas | AI nuevo |
>>> |-----------|----------|-------------------|--------------|------------------|---------------|----------|
>>> | M1 Captura/listado principal | Crear/capturar + listar | {{Resource}}Create, {{Resource}}List | /{{resource}}, /{{resource}}/new | POST /{{resource}}/new, GET /{{resource}} | {{resource_table}} | — |
>>> | M2 Proceso de dominio | Proceso de dominio verificable | {{ResultPage}} | /{{resource}}/{id}/result | POST /{{resource}}/{id}/analyze, GET .../result | {{secondary_table}}, {{result_table}}, {{recommendation_table}} | {{domain_process_graph}} + tools |
>>> | M3 Referencias/recomendaciones | Recomendaciones o resultados fundamentados | (misma {{ResultPage}}) | — | — | — | ingesta de datos/referencias proporcionados + recuperación si aplica |

---

## 14. Visualización

📋 **SI APLICA**: mockups pixel-perfect en `docs/visualization/{feature}/`.

---

## 15. Architectural Decision Records (ADR) — específicos de la app

> No hay ADRs heredados. Esta sección recoge ADRs de esta app nueva, numerados desde **ADR-001**. Append-only. Cuando un ADR queda obsoleto se marca `SUPERSEDED por ADR-N (YYYY-MM-DD)` y se añade el nuevo bloque al final — nunca se borra.
>
> Formato canónico: fecha, estado, contexto, decisión, alternativas descartadas y consecuencias.

>>> MODELO: **DEJAR VACÍO en el momento de generar la app.**
>>> Los ADRs se añaden DURANTE la implementación, no antes — sólo cuando aparece una decisión
>>> arquitectónica real con alternativas reales que se consideraron de verdad.
>>>
>>> Cuando aparezca una, el `developer` (o tú) edita esta sección y añade el bloque con el
>>> siguiente número libre desde ADR-001. NUNCA inventes ADRs para "rellenar el documento" —
>>> un ADR sin alternativas descartadas reales es ruido y el validator lo rechazará.
>>>
>>> Si al cerrar Phase 5 no ha habido decisiones no obvias específicas de la app,
>>> esta sección queda con la línea final `(sin ADRs específicos — todas las decisiones
>>> arquitectónicas fueron triviales o ya estaban justificadas por `STACK_PROFILE.yaml`)` y eso es perfectamente válido.
>>>
>>> **Plantilla a completar** (sólo cuando aparezca decisión real):
>>>
>>> ```
>>> ### ADR-001 — <título corto>
>>> - **Fecha**: YYYY-MM-DD
>>> - **Estado**: accepted
>>> - **Contexto**: <1 frase con el problema o la fuerza que dispara la decisión>
>>> - **Decisión**: <1-2 frases con lo que se elige>
>>> - **Alternativas descartadas**:
>>>   - <Alt A> — <motivo del rechazo>
>>>   - <Alt B> — <motivo del rechazo>
>>> - **Consecuencias**: <tradeoffs aceptados (positivos y negativos)>
>>> ```

(sin ADRs específicos todavía)

---

## 16. Verificación de cableado pre-entrega — OBLIGATORIO

> 🔗 **Antes de devolverme este TECHNICAL_GUIDE, recorre TODA esta checklist mentalmente** y verifica que cada wire está cerrado en los 5 docs. Si alguno falla, vuelves al template y arreglas ANTES de entregar.

### 16.1 Wires desde §2.0 (LIBRARY DISCOVERY técnico)

Para CADA fila de §2.0:

- [ ] Tiene fila correspondiente USAR/DEFERRED en `instrucciones.md §11.0` con la misma "Área funcional".
- [ ] La columna "Versión" dice literal `pendiente — official-docs-researcher confirmará al implementar` (cero versiones pineadas en este doc).
- [ ] La columna "Introducida en slice" referencia un `Slice ID` que existe en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry.
- [ ] Aparece como mención corta en `instrucciones.md §11.1`.

### 16.2 Wires desde §6.1 (RUTAS FLUTTER)

Para CADA ruta:

- [ ] Origen identificable en `instrucciones.md §3.2` (feature) o `§3.6` (journey).
- [ ] Tiene slice `frontend` (o `journey` para rutas de integración) en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry.
- [ ] Si aparece en `instrucciones.md §3.7` columna "Pantallas", coincide ruta + nombre.

### 16.3 Wires desde §6.2 (ENDPOINTS)

Para CADA endpoint:

- [ ] Origen identificable en `instrucciones.md §3.1` (motor) o `§3.2` (feature consume).
- [ ] Tiene slice `api` propio en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (excepción documentada para agrupaciones de integración).
- [ ] Si aparece en `instrucciones.md §3.7` columna "Endpoints", method + path coinciden.
- [ ] Si persiste, las tablas tocadas existen en §10.3.

### 16.4 Wires desde §6.3 (ENTITIES)

Para CADA entity:

- [ ] Mismo nombre que componente en `instrucciones.md §3.1`.
- [ ] Tiene tabla en §10.3 (o declara explícitamente "no se persiste").
- [ ] Aparece como invariante en §12 si tiene reglas de dominio.
- [ ] Su DTO/modelo frontend está previsto en la estructura de §4.

### 16.5 Wires desde §10.3 (TABLAS DB)

Para CADA tabla:

- [ ] Tiene entity correspondiente en §6.3.
- [ ] Tiene migración con slice `db` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (o agrupada con justificación).
- [ ] FKs cascade declaradas donde GDPR aplica.
- [ ] Índices declarados en columnas usadas en WHERE / JOIN / ORDER BY.
- [ ] Si aparece en `instrucciones.md §3.7` columna "Tablas DB", nombre coincide.

### 16.6 Wires desde §10.4 (AI STACK)

Para CADA pieza AI (agent / graph / deep_agent / tool / prompt / reference retrieval):

- [ ] Origen en `instrucciones.md §3.1` ("Componente AI" del bloque).
- [ ] Tiene slice `ai` con smoke test en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry.
- [ ] Cualquier prompt referenciado tiene fichero `prompts/{...}.md` con versión + fecha.
- [ ] La librería AI implícita (LangChain / LangGraph / DeepAgents / LiteLLM) está pineada como `pendiente` en §2.0 si requiere extras.

### 16.7 Wires desde §13 (MILESTONES TÉCNICOS)

Para CADA milestone:

- [ ] Mismo ID que en `instrucciones.md §4`.
- [ ] Cada celda referencia identifiers que existen en §6.1 / §6.2 / §10.3 / §10.4.
- [ ] Agrupa slices reales del CHECKLIST.

### 16.8 Drift checks — cero tolerancia

- [ ] **Cero `>>> MODELO:`** restantes en el fichero filled.
- [ ] **Cero `📋 SI APLICA`** sin resolver.
- [ ] **Cero referencias a existing baseline/herencia** salvo que estén marcadas explícitamente como `NO APLICA` para este perfil sin base.
- [ ] **Cero versiones pineadas** en §2.0 ni §2.1.
- [ ] **`scripts/dev-restart.sh`** documentado en §3 con `--soft` / `--check` / `--reset` (lo invocan `/next-slice` y `/verify-slice`).

### 16.9 Última prueba mental antes de entregar

1. **¿Si el `developer` lee §6.2 endpoint X, encuentra suficiente recurso técnico (schema, errors, auth) para implementarlo sin volver a `instrucciones.md`?** Si tiene que adivinar, falta detalle.
2. **¿Si el `planner` lee el primer slice del Coverage Registry y busca su recurso aquí, encuentra exactamente UNA fuente (un endpoint, una tabla, una pieza AI)?** Si encuentra ambigüedad o nada, falta cableado.
3. **¿Cada componente del motor de `instrucciones.md §3.1` tiene cobertura completa aquí (entity + tabla + endpoint + AI si aplica)?** Si falta una pata, el motor queda cojo.

Si las 3 son "sí", entrega. Si alguna es "no", arregla y vuelve a verificar.


## Production hardening actual

Usa source-of-truth acumulativo de app nueva (`v1`, luego `v2`, ...), `Risk level`, `Verify mode`, phases <=20 slices, steps <=15 slices, journeys reales multi-superficie y verify con datos reales/proporcionados. Ejecuta bootstrap + check-task-dag + check-journey-matrix + check-wiring-contract antes de waves.