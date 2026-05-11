# {{APP_NAME}} Technical Guide — minimal DAG

## Screen/Journey Lane Redactor Contract

- No modeles la app como `backend/API primero`, luego `frontend`, y `UX polish` al final. Esa separación rompe la pantalla aunque los tests pasen.
- Cada pantalla importante debe nacer de una **screen/journey lane**: contrato de pantalla + contrato API/datos + implementación conectada + estados UX obligatorios + verificación del journey.
- Las slices de API/backend pueden existir separadas sólo si son foundation real o contrato técnico que alimenta una pantalla/journey nombrado en `Journey refs`.
- Criterio de cierre de pantalla: datos reales/proporcionados conectados front -> back -> DB, estados `loading`, `empty`, `error_network`, `error_validation`, `permission_denied` cuando aplique, `success`, navegación/next action, responsive básico y accesibilidad básica.
- Tamaño recomendado: pantalla crítica 3-6 slices; módulo/journey lane 8-15 slices. No hagas una slice por botón/componente pequeño; tampoco cierres una pantalla sólo porque compila.
- Defectos dentro de la pantalla actual van por `validator/tester -> debugger -> retest`. Sólo crea FU si falta trabajo nuevo fuera de scope: pantalla, endpoint, tabla, journey, contrato de datos reales o decisión humana no declarada.

> Perfil: **minimal**. Guía técnica suficiente para que planner/developer/tester no adivinen contratos.

## 1. Stack

La fuente única del stack es `STACK_PROFILE.yaml`. Resume aquí solo las decisiones de arquitectura que derivan de ese perfil:

- Frontend: `{{frontend.framework}}` en `{{frontend.module_root}}`.
- Backend: `{{backend.framework}}` en `{{backend.module_root}}`.
- DB: `{{db.engine}}`.
- Auth: {{AUTH_MODE}}.
- Comandos: frontend `{{frontend.test_cmd}}`, backend `{{backend.test_cmd}}`, migración `{{db.migrate_cmd}}`.

## 2. Contrato front -> back -> DB

### 2.1 Rutas/pantallas nuevas

| Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/provider | Estados UI obligatorios | Next action | Slice ID | Descripción |
|---|---|---|---|---|---|---|---|---|---|
| {{ROUTE_1}} | {{PAGE_1}} | {{AUTH}} | J1 | {{ENDPOINT_1}} | {{PROVIDER_1}} | loading, empty, error_network, error_validation, success | {{NEXT_ACTION_1}} | {{SLICE_UI_1}} | {{DESC_1}} |
| {{ROUTE_2_OPCIONAL}} | {{PAGE_2}} | {{AUTH}} | J1 | {{ENDPOINT_2}} | {{PROVIDER_2}} | loading, empty, error_network, success | {{NEXT_ACTION_2}} | {{SLICE_UI_2}} | {{DESC_2}} |

### 2.2 Endpoints API nuevos

| Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
|---|---|---|---|---|---|---|---|---|
| {{METHOD_1}} | {{PATH_1}} | {{REQUEST_1}} | {{RESPONSE_1}} | {{AUTH}} | 400, 401, 500 | {{PAGE_1}} / J1 | {{TABLE_1}} | {{SLICE_API_1}} |
| {{METHOD_2_OPCIONAL}} | {{PATH_2}} | {{REQUEST_2}} | {{RESPONSE_2}} | {{AUTH}} | 400, 401, 404, 500 | {{PAGE_2}} / J1 | {{TABLE_2}} | {{SLICE_API_2}} |

### 2.3 Modelos / tablas

| Tabla | Campos mínimos | Índices / constraints | Slices |
|---|---|---|---|
| {{TABLE_1}} | {{FIELDS_1}} | {{CONSTRAINTS_1}} | {{SLICE_DB_1}} |

## 3. Verification Data Contract

| Flow/Journey | Persona/Rol | Datos reales/proporcionados requeridos | Fuente de datos reales proporcionados | Reset/Cleanup | Slices/Journeys |
|---|---|---|---|---|---|
| J1 | {{PERSONA}} | {{REAL_DATA}} | {{FIXTURE_CMD}} | {{RESET_CMD}} | {{SLICE_IDS}} / J1 |

## 4. Testing mínimo

| Capa | Comando | Evidencia esperada |
|---|---|---|
| API | {{API_TEST_CMD}} | tests verdes con DB real con datos proporcionados |
| Frontend | {{frontend.test_cmd}} | UI states y provider conectados |
| Verify | /verify-slice + /verify-journey J1 | front -> back -> DB observado |