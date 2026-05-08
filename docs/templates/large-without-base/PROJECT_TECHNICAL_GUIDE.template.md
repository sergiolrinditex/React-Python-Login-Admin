# {{APP_NAME}} — Technical Guide (large app sin base-app)

> **SIN BASEAPP**: define stack, estructura y patterns completos desde `STACK_PROFILE.yaml`.
> **TU TRABAJO**: describir el contrato técnico completo de esta app nueva. Nada se hereda de `docs/base-app/` salvo que el usuario lo pida explícitamente.
> Rellenar `>>> MODELO:`. Resolver secciones no aplicables como `NO APLICA` con motivo.

> Perfil: **large-without-base**. App grande nueva desde cero; AnyStack permitido vía `STACK_PROFILE.yaml`, sin asumir Flutter salvo que el perfil lo declare.

---

## 🔗 Contrato de Cableado — léelo ANTES de empezar a rellenar

> Este documento traduce el motor + features de `instrucciones.md` a contrato técnico ejecutable, y es la **fuente** que el `*_IMPLEMENTATION_CHECKLIST.md` consume para generar slices. Cada elemento aquí debe estar simultáneamente declarado en `instrucciones.md` (origen conceptual) y referenciado en el `CHECKLIST` (ejecución).
>
> **Wires ENTRANTES** (cada item de `instrucciones.md` debe convertirse en contrato aquí):
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
>>>  [ContractUploadPage] ──► POST /api/v1/contracts/analyze  ──► [ContractAnalyzer Graph]
>>>                                                                ├─ parse_node (pypdf)
>>>                                                                ├─ classify_node (LLM + prompt)
>>>                                                                └─ suggest_node (LLM + RAG)
>>>                                                                      │
>>>                                                                      ▼
>>>                                                                 [pgvector: legal_corpus]
>>> ```
>>>
>>> Sin este diagrama no queda claro qué construyes. Es obligatorio.

---

## 2. Stack — contrato completo

⚙️ **DEFINIR PARA ESTE STACK**: resume el stack declarado en `STACK_PROFILE.yaml` (frontend, backend, DB, auth, AI, test/lint/build). No inventes Flutter/FastAPI/Supabase si el perfil declara otro stack.

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
> - El **lockfile** (`pubspec.lock`, `package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock`, etc.) fija la versión real. Este documento solo declara intención, no contrato de versión.
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
>>> | {ej: PDF parsing backend} | `<paquete>` | {URL} | Backend | {ej: motor §3.1 parsea contratos PDF nativos; ahorra 1 slice de pdf-parsing custom} | {ej: alternativa con OCR — no aplica porque PDFs son nativos} | pendiente — official-docs-researcher confirmará | {ej: P02-S04-T002} |
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

⚙️ **DEFINIR PARA ESTE STACK**: install, run, migrate, seed, test, lint, build — todos derivados de `STACK_PROFILE.yaml` y scripts reales del repo.

>>> MODELO: comandos específicos de tu app. Ejemplos comunes:
>>> - `python -m api.seeds.bootstrap_{feature}`: seed de datos demo de tu dominio.
>>> - `python -m api.scripts.ingest_corpus`: cargar corpus RAG inicial.
>>> - `python -m api.scripts.retrain_classifier`: si entrenas modelos locales.
>>>
>>> Si nada extra: "Sin comandos adicionales".

---

## 4. Estructura del proyecto — adiciones

⚙️ **DEFINIR PARA ESTE STACK**: árbol completo propio usando los paths reales de `STACK_PROFILE.yaml`.

>>> MODELO: añade tu árbol NUEVO (solo carpetas que tu app crea). Ejemplo:
>>>
>>> ```
>>> # Frontend (ejemplo; ajusta a STACK_PROFILE.yaml)
>>> <frontend_module_root>/features/
>>> └── contracts/
>>>     ├── domain/
>>>     │   ├── entities/
>>>     │   │   ├── contract.dart
>>>     │   │   ├── clause.dart
>>>     │   │   └── risk.dart
>>>     │   ├── repositories/
>>>     │   └── use_cases/
>>>     ├── data/
>>>     │   ├── repositories/
>>>     │   ├── data_sources/
>>>     │   └── models/
>>>     └── presentation/
>>>         ├── pages/
>>>         │   ├── contract_upload_page.dart
>>>         │   ├── contract_list_page.dart
>>>         │   └── analysis_results_page.dart
>>>         ├── widgets/
>>>         └── providers/
>>>
>>> # Backend
>>> <backend_module_root>/features/
>>> └── contracts/
>>>     ├── domain/
>>>     │   ├── entities.py
>>>     │   ├── errors.py
>>>     │   └── repositories.py
>>>     ├── infrastructure/
>>>     │   ├── models.py
>>>     │   └── repositories.py
>>>     ├── application/
>>>     │   └── use_cases/
>>>     ├── api/
>>>     │   ├── router.py
>>>     │   └── schemas.py
>>>     └── tests/
>>>
>>> # Adiciones a AI stack (scaffolding ya existe en base)
>>> <backend_module_root>/features/ai/
>>> ├── agents/
>>> │   └── contract_analyst_agent.py
>>> ├── graphs/
>>> │   └── contract_analysis_graph.py
>>> ├── tools/
>>> │   ├── pdf_parser.py
>>> │   └── clause_extractor.py
>>> ├── prompts/
>>> │   └── system/
>>> │       └── contract_analyst.md
>>> └── rag/
>>>     └── loaders/
>>>         └── legal_corpus_loader.py
>>> ```

---

## 5. Arquitectura

### 5.1 Componentes nuevos

>>> MODELO: tabla de componentes que añades con responsabilidad + dependencias.
>>>
>>> | Módulo | Responsabilidad | Depende de |
>>> |--------|-----------------|-----------|
>>> | `features/contracts` | CRUD contratos + lanzar análisis | `features/ai`, `shared/auth` |
>>> | `features/ai/graphs/contract_analysis_graph` | StateGraph que orquesta parse → classify → suggest | `features/ai/tools`, `features/ai/llms` |
>>> | `features/ai/rag/loaders/legal_corpus_loader` | Loader de corpus legal para retrieval | `features/ai/rag/chunking`, `features/ai/embeddings` |

### 5.2 Flujo de datos específico

>>> MODELO: diagrama del flujo de una request clave end-to-end. Ejemplo:
>>>
>>> ```
>>> User upload PDF → ContractUploadPage
>>>   → POST /api/v1/contracts/upload (multipart)
>>>     → JWT verify + get_current_user
>>>     → UploadContract use case
>>>       → ContractRepository.save(file, user_id) → Supabase Storage + contracts table
>>>       → Enqueue background task: AnalyzeContract
>>>     ← 201 {contract_id}
>>>   → Frontend navega a /contracts/:id/analysis (polling o SSE)
>>> 
>>> [background]
>>> AnalyzeContract use case
>>>   → contract_analysis_graph.ainvoke(contract_id)
>>>     → parse_node (pypdf → text)
>>>     → classify_node (LLM con prompt system + clauses → [Risk])
>>>     → suggest_node (RAG: retrieve legal precedents + LLM → [Suggestion])
>>>     → persist results in DB
>>> ```

### 5.3 Decisiones de diseño

>>> MODELO: 3+ decisiones relevantes con alternativas y por qué elegiste una. Ej:
>>>
>>> | Decisión | Alternativas | Elegida | Razón |
>>> |---------|--------------|---------|-------|
>>> | Graph vs single agent para análisis | `create_agent` con tool de classify | `StateGraph` custom de 3 nodos | Control preciso del flow + checkpointing + debug |
>>> | Polling vs SSE para progreso | SSE streaming | Polling cada 2s | SSE añadiría complejidad; análisis dura 20-30s |
>>> | Almacenar PDFs en Supabase Storage vs re-subir | Re-subir cada análisis | Storage | Auditoría + coste UX + permite re-análisis |

---

## 6. Interfaces — adiciones

### 6.1 Rutas/pantallas frontend

> 🔗 **CABLEADO de §6.1** — cada fila aquí cierra el wire de la pantalla:
>
> 1. **Origen** → feature en `instrucciones.md §3.2` (la pantalla expone esa feature) y/o journey en `instrucciones.md §3.6` (la pantalla es paso del flujo).
> 2. **Destino** → slice en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (`flutter` con la `<Page>` o `journey` si la pantalla solo existe como integración).
> 3. **Cross-check** → si la ruta aparece en `instrucciones.md §3.7` (Journey Matrix), columna "Pantallas", debe figurar AQUÍ con el mismo nombre/ruta.
>
> Si declaras una ruta aquí que NO está en §3.2 ni §3.6 → drift (pantalla inventada). Si una pantalla aparece en §3.7 pero no aquí → la ruta no existirá y `/verify-journey` fallará.

>>> MODELO:
>>>
>>> | Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/provider | Estados UI obligatorios | Next action | Slice ID | Descripción |
>>> |------|------|------|--------------|----------------------|-------------------------|------------------------|-------------|----------|-------------|
>>> | /contracts | ContractListPage | Sí | J1 | GET /api/v1/contracts | ContractListProvider | loading, empty, error_network, success | abrir detalle o subir contrato | P03-S01-T001 | Lista de contratos del usuario |
>>> | /contracts/upload | ContractUploadPage | Sí | J1 | POST /api/v1/contracts/upload | ContractUploadFormProvider | idle, uploading, error_validation, error_network, success | navegar a análisis | P03-S01-T002 | Subida + lanzar análisis |
>>> | /contracts/:id | ContractDetailPage | Sí | J1 | GET /api/v1/contracts/:id | ContractDetailProvider | loading, not_found, permission_denied, success | ver análisis | P03-S01-T003 | Detalle con metadata |
>>> | /contracts/:id/analysis | AnalysisResultsPage | Sí | J1 | GET /api/v1/contracts/:id/analysis | AnalysisProvider | loading, empty, error_network, success | aceptar sugerencia o reanalizar | P03-S01-T004 | Resultados del motor con cláusulas + riesgos + sugerencias |

### 6.2 Endpoints API nuevos

⚙️ **DEFINIR PARA ESTE STACK**: formato envelope `{data, meta, errors}`, versioning `/api/v1/`, auth via `get_current_user`.

> 🔗 **CABLEADO de §6.2** — cada endpoint aquí cierra DOS wires:
>
> 1. **Origen** → componente del motor en `instrucciones.md §3.1` (el endpoint expone una capability del motor) o feature en `§3.2` (el endpoint sirve a una pantalla).
> 2. **Destino obligatorio** → slice `api` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, **uno por endpoint** (schema + use case + repository + integration test + curl + logs). Excepción única: agrupación explícita en un slice de integración con justificación documentada.
> 3. **Cross-check** → si el endpoint aparece en `instrucciones.md §3.7` columna "Endpoints", debe figurar AQUÍ con el mismo method + path.
> 4. **Cross-check con tablas** → si el endpoint persiste, las tablas tocadas existen en §10.3.
>
> Endpoint declarado aquí sin slice → el orquestador no lo implementa, queda en el contrato pero no en el código. Endpoint sin consumidor explícito → drift de producto: no queda claro quién lo usa ni cómo se verifica.

>>> MODELO: tabla COMPLETA. CADA endpoint aquí DEBE tener un `Slice ID` propio en el CHECKLIST Coverage Registry, salvo que esté documentado como parte de un slice de integración ya existente. Todo endpoint debe tener `Consumidor front/journey`; si no tiene frontend, escribe `internal/no-front`, `webhook`, `background-job` o `admin-only` y justifica en la descripción.
>>>
>>> | Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
>>> |--------|------|---------|----------|------|--------|--------------------------|---------------------|----------|
>>> | POST | /api/v1/contracts/upload | multipart file | `{data: {contract_id}}` | Sí | 400, 401, 413 | ContractUploadPage / J1 | `contracts`, Supabase Storage | P02-S02-T001 |
>>> | GET | /api/v1/contracts | query params (cursor, limit) | `{data: [Contract], meta: {pagination}}` | Sí | 401 | ContractListPage / J1 | `contracts` read | P02-S02-T002 |
>>> | GET | /api/v1/contracts/:id | — | `{data: Contract}` | Sí | 401, 404 | ContractDetailPage / J1 | `contracts` read | P02-S02-T003 |
>>> | POST | /api/v1/contracts/:id/analyze | — | `{data: {analysis_id, status: "queued"}}` | Sí | 401, 404, 409 | ContractDetailPage / J1 | enqueue analysis job | P02-S02-T004 |
>>> | GET | /api/v1/contracts/:id/analysis | — | `{data: Analysis\|null, meta: {status, progress}}` | Sí | 401, 404 | AnalysisResultsPage / J1 | `analyses`, `risks` read | P02-S02-T005 |
>>> | DELETE | /api/v1/contracts/:id | — | 204 | Sí | 401, 404 | ContractDetailPage / account cleanup | `contracts` delete cascade | P02-S02-T006 |
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
>>> **Contract** (domain)
>>> ```python
>>> class Contract(BaseModel):
>>>     id: UUID
>>>     user_id: UUID
>>>     title: str
>>>     pdf_url: str  # Supabase Storage URL
>>>     page_count: int
>>>     uploaded_at: datetime
>>>     analysis_status: Literal["pending", "analyzing", "done", "failed"]
>>> ```
>>>
>>> **Clause** (domain)
>>> ```python
>>> class Clause(BaseModel):
>>>     id: UUID
>>>     contract_id: UUID
>>>     order: int
>>>     text: str
>>>     risk_level: Literal["low", "medium", "high"]
>>>     risk_rationale: str | None
>>> ```
>>>
>>> **Dart equivalents** en `lib/features/contracts/domain/entities/` y sus DTOs con freezed en `data/models/`.

### 6.4 Formato de errores específico

⚙️ **DEFINIR PARA ESTE STACK**: sealed classes `DomainError` + envelope.

>>> MODELO: códigos específicos de tu dominio. Ej:
>>> ```
>>> CONTRACT_001_PDF_INVALID          (400)
>>> CONTRACT_002_PAGE_LIMIT_EXCEEDED  (413)
>>> CONTRACT_003_ANALYSIS_IN_PROGRESS (409)
>>> CONTRACT_004_ANALYSIS_FAILED      (502)
>>> ```

---

### 6.4 Navigation Contract

⚙️ **DEFINIR PARA ESTE STACK**: define routing, deep links, menú principal, estados marginales globales y next action para esta app nueva.

>>> MODELO: documenta el contrato de navegación completo. Si algo no aplica, marca `NO APLICA` con motivo:

>>> - Rutas nuevas de tu app que aceptan deep link → añade a §6.4.2.
>>> - Empty states o error states con contenido específico de tu dominio (ej: "Sin contratos analizados, sube tu primer PDF" en lugar del genérico).
>>> - Next actions específicas que enlazan tus journeys entre sí.
>>> - Si tu app introduce un nuevo tipo de menú (ej: tabs adicionales por rol), descríbelo aquí.

>>> Patrón de adición:

>>> ```markdown
>>> #### 6.4.7 Deep links propios

>>> | Ruta                        | Auth req | Schema mobile        | Schema web                  |
>>> |-----------------------------|----------|----------------------|-----------------------------|
>>> | /analysis/:id               | sí       | tuapp://analysis/:id | https://app.dominio/analysis/:id |
>>> | /share/:token               | no       | tuapp://share/:token | https://app.dominio/share/:token |

>>> #### 6.4.8 Empty states de tu dominio

>>> - DashboardPage sin análisis → ilustración custom + CTA "Sube tu primer contrato" → /upload
>>> - AnalysisListPage sin filtros aplicados → render genérico
>>> ```

>>> Si no aplica navegación especial, escribe "NO APLICA — navegación simple cubierta por rutas de §6.1".


### 6.5 Verification Data Contract

> 🔗 **CABLEADO de datos reales para verify-slice / verify-journey** — cada journey o flujo verificable debe declarar de dónde salen los datos reales/prod-like. El orquestador NO debe verificar con mocks ni seed decorativo. Los datos sintéticos solo se permiten para estados marginales imposibles de obtener con datos reales y deben marcarse como `synthetic-edge-case`.

>>> MODELO: una fila por journey o flujo crítico.
>>>
>>> | Flow/Journey | Persona/Rol | Datos reales/prod-like requeridos | Seed/fixture permitido | Reset/Cleanup | Slices/Journeys |
>>> |--------------|-------------|-----------------------------------|------------------------|---------------|-----------------|
>>> | J1 upload-analysis | user real de prueba + contrato PDF realista | usuario confirmado, PDF válido, análisis persistido, errores 400/413 reales | `python -m seeds.contracts_demo --profile prod_like`; fixture SQL transaccional para edge cases | `scripts/dev-restart.sh --reset` + truncate tablas del feature | J1, P02-S02-T001, P03-S01-T001 |
>>>
>>> Reglas:
>>> - `verify-slice` debe usar estas filas para preparar datos.
>>> - No insertar datos vía el endpoint que se está verificando; usa seed/fixture externo y luego verifica el endpoint/UI.
>>> - Para servicios externos, usa sandbox oficial o credenciales test documentadas; nunca inventes respuestas mock en producción MVP.

## 7. Theme & Design System

⚙️ **DEFINIR PARA ESTE STACK**: ThemeData + tokens + shared widgets. CERO inline.

>>> MODELO: override si necesitas (logo, color primario):
>>> - Logo/assets: `<frontend_module_root>/assets/logo/` o path equivalente.
>>> - Override colores en `AppColors` si hay branding: "AppColors.primary = Color(0xFF...)".
>>> - Shared widgets nuevos ESPECÍFICOS de tu dominio (ej: `RiskBadge(low|medium|high)`, `ClauseCard`): documentar aquí con props.
>>>
>>> Si nada custom: "Sin customización visual adicional".

---

## 8. Logging y Observabilidad

⚙️ **DEFINIR PARA ESTE STACK**: structlog + request_id + Prometheus base.

>>> MODELO: métricas custom específicas de tu motor:
>>> ```python
>>> contract_analysis_duration = Histogram(
>>>     "contract_analysis_duration_seconds",
>>>     "Duration of contract analysis",
>>>     ["outcome"],  # success|failed|timeout
>>> )
>>> ```
>>>
>>> Audit log actions nuevas: `contract_uploaded`, `contract_analyzed`, `suggestion_accepted`, `suggestion_rejected`.

---

## 9. Testing

⚙️ **DEFINIR PARA ESTE STACK**: comandos y frameworks de test reales desde `STACK_PROFILE.yaml`; tests contra DB real/prod-like y E2E/visual cuando `Verify mode=human`.

### 9.1 Convenciones específicas

>>> MODELO: si tu motor requiere fixtures especiales (corpus de documentos de prueba, PDFs sample, datasets de validación), documentarlos:
>>> - Fixtures en `api/tests/fixtures/contracts/` con X PDFs variados.
>>> - Dataset de validación para clasificador: `api/tests/fixtures/classification_dataset.json` con 50 cláusulas anotadas.

---

## 10. Backend / API — adiciones

### 10.1 Módulos del backend

>>> MODELO: tabla de módulos propios del dominio (ya enumerados en §5.1, referenciar ahí).

### 10.2 Auth strategy

⚙️ **DEFINIR PARA ESTE STACK**: auth real de esta app (JWT/session/cookies/API keys), dependency/middleware y roles/claims si aplica.

>>> MODELO: SOLO si tu app requiere roles/permisos específicos del dominio más allá de admin/user. Ej: "Cliente premium" (claim custom en JWT vía Supabase). Justificar y aceptar la complejidad añadida. Si no: "NO APLICA".

### 10.3 DB Schema — tablas nuevas

> 🔗 **CABLEADO de §10.3** — cada tabla aquí cierra DOS wires:
>
> 1. **Origen** → entity en `§6.3` (misma columna por campo) y componente del motor en `instrucciones.md §3.1`.
> 2. **Destino obligatorio** → slice `db` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry: una migración Alembic `000N_<feature>.py` con up + down probados, FKs cascade, índices. Tablas que nacen juntas y se verifican juntas pueden agruparse en una migración.
> 3. **Cross-check con journey matrix** → si la tabla aparece en `instrucciones.md §3.7` columna "Tablas DB", debe figurar AQUÍ con el mismo nombre.
>
> Tabla declarada sin migración en CHECKLIST → no se crea, los endpoints que dependen fallan en runtime.

>>> MODELO: SQL completo de cada tabla nueva. TODAS con FK a `auth.users(id) ON DELETE CASCADE` donde aplique para GDPR.
>>>
>>> ```sql
>>> CREATE TABLE contracts (
>>>     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>>>     user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
>>>     title TEXT NOT NULL,
>>>     pdf_url TEXT NOT NULL,
>>>     page_count INT NOT NULL,
>>>     analysis_status VARCHAR(20) NOT NULL DEFAULT 'pending',
>>>     uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
>>>     metadata JSONB NOT NULL DEFAULT '{}'::jsonb
>>> );
>>>
>>> CREATE INDEX contracts_user_id ON contracts (user_id);
>>> CREATE INDEX contracts_analysis_status ON contracts (analysis_status) WHERE analysis_status != 'done';
>>> ```
>>>
>>> Repetir por cada tabla. Migración reversible (up + down).

### 10.4 AI stack — motor específico

> 🔗 **CABLEADO de §10.4** — cada pieza AI aquí cierra DOS wires:
>
> 1. **Origen** → componente del motor con AI en `instrucciones.md §3.1` ("Componente AI" del bloque). Si declaras un graph aquí que no aparece como componente AI en §3.1, drift.
> 2. **Destino obligatorio** → slice `ai` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry, con **smoke test** ejecutable (cada agent / graph / deep_agent / tool / prompt / RAG loader independiente verificable). El `official-docs-researcher` valida versión + imports antes del developer.
> 3. **Cross-check con prompts versionados** → si declaras `prompts/system/{name}.md`, ese fichero existe en repo con versión + fecha en su cabecera.
>
> Tool/agent/graph aquí sin slice + smoke test en CHECKLIST → no se construye y los endpoints que dependen fallan o retornan datos fake.

>>> MODELO: el corazón técnico. Detallar:
>>>
>>> #### Agents
>>> >>> MODELO:
>>> - `contract_analyst_agent.py`: `create_agent(model=..., tools=[pdf_parse, clause_classify], system_prompt="...")`. Cuándo se usa: consultas directas sobre un contrato ya analizado.
>>>
>>> #### Deep Agents
>>> >>> MODELO:
>>> - `legal_research_agent.py`: `create_deep_agent(model=..., subagents=[retriever_subagent, writer_subagent], ...)`. Cuándo se usa: preguntas complejas que requieren buscar jurisprudencia + redactar informe.
>>>
>>> #### Graphs
>>> >>> MODELO:
>>> - `contract_analysis_graph.py`: `StateGraph[ContractAnalysisState]` con nodos `parse → classify → suggest`. Checkpointer: `AsyncPostgresSaver`. State:
>>>   ```python
>>>   class ContractAnalysisState(TypedDict):
>>>       contract_id: UUID
>>>       raw_text: str
>>>       clauses: list[Clause]
>>>       risks: list[Risk]
>>>       suggestions: list[Suggestion]
>>>   ```
>>>
>>> #### Tools
>>> >>> MODELO:
>>> - `pdf_parser.py`: `@tool def parse_pdf(file_path: str) -> str` (texto plano) o `@tool def parse_pdf_to_clauses(file_path: str) -> list[str]`.
>>> - `clause_extractor.py`: tool que extrae cláusulas individuales de texto bruto.
>>> - (Cualquier API externa que llames: incluirlo como tool).
>>>
>>> #### Prompts
>>> >>> MODELO:
>>> - `prompts/system/contract_analyst.md`: system prompt base. Versionar explícitamente (incluir fecha + versión en el fichero).
>>> - Describir brevemente el prompt (NO pegar el contenido completo aquí).
>>>
>>> #### RAG
>>> >>> MODELO:
>>> - Qué ingesta: corpus legal con X documentos (sentencias, artículos, ...).
>>> - Loader: `rag/loaders/legal_corpus_loader.py` (custom si aplica).
>>> - Splitter: `RecursiveCharacterTextSplitter` u otro splitter declarado, con overrides (ej: chunk_size=2000 para cláusulas legales).
>>> - Rerank: sí/no. Si sí, librería (Cohere rerank, cross-encoder).
>>> - Dimensión embedding: heredada 1536.

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
>>> | `LEGAL_API_KEY` | test-key | staging-key | prod-key | API externa de jurisprudencia |
>>> | `MAX_PDF_PAGES` | 100 | 100 | 50 | Límite de páginas por PDF |

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
>>> - Un `Contract` siempre pertenece a un único `user_id`.
>>> - Una `Clause` no puede existir sin su `Contract` (FK cascade).
>>> - Un `Risk` level nunca se auto-modifica — solo se asigna durante análisis o manualmente por el user.
>>> - Un PDF >100 páginas se rechaza en upload (no se trocea).
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
> | P02-S02-T001 | api | `POST /api/v1/contracts` | Step 2.2 | P02-S01-T001 | J1 | — | `POST /api/v1/contracts` | contracts | §3.1, §3.7 | §6.2, §10.3 | schema + use case + repo + integration test + curl + logs | `pytest ...` + curl |

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
>>> | M1 Upload básico | Subir + listar | ContractUpload, ContractList | /contracts, /contracts/upload | POST /contracts/upload, GET /contracts | contracts | — |
>>> | M2 Análisis motor | Análisis automático | AnalysisResultsPage | /contracts/:id/analysis | POST /contracts/:id/analyze, GET .../analysis | clauses, risks, suggestions | contract_analysis_graph + tools |
>>> | M3 RAG sugerencias | Sugerencias fundamentadas | (misma AnalysisResultsPage) | — | — | — | RAG ingestion + retrieval + rerank |

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
- [ ] Tiene slice `flutter` (o `journey` para rutas de integración) en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry.
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
- [ ] Su DTO Dart está previsto en la estructura de §4.

### 16.5 Wires desde §10.3 (TABLAS DB)

Para CADA tabla:

- [ ] Tiene entity correspondiente en §6.3.
- [ ] Tiene migración con slice `db` en `*_IMPLEMENTATION_CHECKLIST.md` Coverage Registry (o agrupada con justificación).
- [ ] FKs cascade declaradas donde GDPR aplica.
- [ ] Índices declarados en columnas usadas en WHERE / JOIN / ORDER BY.
- [ ] Si aparece en `instrucciones.md §3.7` columna "Tablas DB", nombre coincide.

### 16.6 Wires desde §10.4 (AI STACK)

Para CADA pieza AI (agent / graph / deep_agent / tool / prompt / RAG):

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
- [ ] **Cero referencias a BaseApp/herencia** salvo que estén marcadas explícitamente como `NO APLICA` para este perfil sin base.
- [ ] **Cero versiones pineadas** en §2.0 ni §2.1.
- [ ] **`scripts/dev-restart.sh`** documentado en §3 con `--soft` / `--check` / `--reset` (lo invocan `/next-slice` y `/verify-slice`).

### 16.9 Última prueba mental antes de entregar

1. **¿Si el `developer` lee §6.2 endpoint X, encuentra suficiente contrato técnico (schema, errors, auth) para implementarlo sin volver a `instrucciones.md`?** Si tiene que adivinar, falta detalle.
2. **¿Si el `planner` lee el primer slice del Coverage Registry y busca su contrato aquí, encuentra exactamente UNA fuente (un endpoint, una tabla, una pieza AI)?** Si encuentra ambigüedad o nada, falta cableado.
3. **¿Cada componente del motor de `instrucciones.md §3.1` tiene cobertura completa aquí (entity + tabla + endpoint + AI si aplica)?** Si falta una pata, el motor queda cojo.

Si las 3 son "sí", entrega. Si alguna es "no", arregla y vuelve a verificar.


## Production hardening actual

Usa source-of-truth acumulativo baseline+vN, `Risk level`, `Verify mode`, phases <=12 slices, steps <=10 slices, journeys reales multi-superficie y verify con datos reales/prod-like. Ejecuta bootstrap + check-task-dag + check-journey-matrix + check-wiring-contract antes de waves.
