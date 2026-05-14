# {{APP_NAME}} Implementation Checklist — minimal DAG

## Screen/Journey Lane Redactor Contract

- No modeles la app como `backend/API primero`, luego `frontend`, y `UX polish` al final. Esa separación rompe la pantalla aunque los tests pasen.
- Cada pantalla importante debe nacer de una **screen/journey lane**: contrato de pantalla + contrato API/datos + implementación conectada + estados UX obligatorios + verificación del journey.
- Las slices de API/backend pueden existir separadas sólo si son foundation real o contrato técnico que alimenta una pantalla/journey nombrado en `Journey refs`.
- Criterio de cierre de pantalla: datos reales/proporcionados conectados front -> back -> DB, estados `loading`, `empty`, `error_network`, `error_validation`, `permission_denied` cuando aplique, `success`, navegación/next action, responsive básico y accesibilidad básica.
- Tamaño recomendado: pantalla crítica 3-6 slices; módulo/journey lane 8-15 slices. No hagas una slice por botón/componente pequeño; tampoco cierres una pantalla sólo porque compila.
- Defectos dentro de la pantalla actual van por `validator/tester -> debugger -> retest`. Sólo crea FU si falta trabajo nuevo fuera de scope: pantalla, endpoint, tabla, journey, contrato de datos reales o decisión humana no declarada.

> Perfil: **minimal**. El `Canonical Coverage Registry` es la fuente del DAG. Mantén 3-8 tasks, phases pequeñas y dependencias reales. El bootstrap debe terminar en `mode=explicit_dag`, siempre `explicit_dag`.


## Modelo Phase / Step / Slice para generar una app completa

- **Phase** = milestone o módulo de producto con sentido para la visión global; no es un lote arbitrario de tareas.
- **Step** = lane coherente dentro de la phase: pantalla/journey lane, módulo de dominio, foundation lane o contrato API que alimenta una pantalla nombrada.
- **Slice/Task** = unidad ejecutable y verificable por un worker, con `Depends on`, `Write set`, `Conflict group`, `Journey refs` y `Verify mínimo` claros.
- Objetivo sano: phase <=20 slices, step 6-12 slices recomendado y <=15 máximo. No dividas un step coherente sólo por tener 11-12 slices; divide cuando mezcle lanes no relacionadas o pierda trazabilidad.
- Mantén visión de app: cada slice debe conectar con una feature, endpoint, tabla, journey o foundation real; nada de slices decorativas.
- Sustituye todos los ejemplos por el dominio real de la app. Si falta un dato real para verificar, bloquea o registra follow-up; no inventes cargas no proporcionadas ni datos de relleno.

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | db | {{MIGRATION_OR_SCHEMA_CHANGE}} | Step 0.1 | v1 | planned | low | auto | — | db:migrations | {{db_migration_write_set}}; {{backend_test_write_set}} | — | — | — | {{TABLE_1}} | §2.1 | §2.3#{{TABLE_1}} | migración/schema y constraints | {{db.migrate_cmd}} && {{backend.test_cmd}} |
| P01-S01-T001 | api | {{ENDPOINT_1}} | Step 1.1 | v1 | planned | medium | human | P00-S01-T001 | api:{{DOMAIN}} | {{backend.module_root}}/**/{{DOMAIN}}*; {{backend_test_write_set}} | J1 | {{PAGE_1}} {{ROUTE_1}} | {{ENDPOINT_1}} | {{TABLE_1}} | §3#J1 | §2.2#{{ENDPOINT_1}} | endpoint real con DB y auth | {{backend.test_cmd}} |
| P02-S01-T001 | frontend | {{PAGE_1}} | Step 2.1 | v1 | planned | medium | human | P01-S01-T001 | front:{{DOMAIN}}, navigation | {{frontend.module_root}}/**/{{DOMAIN}}*; {{frontend_test_write_set}}; {{frontend_navigation_write_set}} | J1 | {{PAGE_1}} {{ROUTE_1}} | {{ENDPOINT_1}} | — | §3#J1 | §2.1#{{ROUTE_1}} | estados UI y provider conectados | /verify-slice con datos reales/proporcionados |
| P03-S01-T001 | journey | J1 e2e | Step 3.1 | v1 | planned | high | human | P02-S01-T001 | journey:{{DOMAIN}} | orchestrator-state/tasks/journey-handoffs/** | J1 | {{PAGE_SEQUENCE}} | {{ENDPOINT_SEQUENCE}} | {{TABLES}} | §3#J1 | §3 Verification Data Contract | J1 verificado de punta a punta | /verify-journey J1 |

## Phase 0 — Data foundation
### Step 0.1 — Schema
- [ ] P00-S01-T001

## Phase 1 — J1 screen/journey lane
### Step 1.1 — Contrato API que alimenta la pantalla J1
- [ ] P01-S01-T001

## Phase 2 — J1 connected screen lane
### Step 2.1 — Pantalla conectada + estados UX
- [ ] P02-S01-T001

## Phase 3 — J1 journey verification gate
### Step 3.1 — Verify e2e
- [ ] P03-S01-T001

## Runtime Follow-up Coverage Registry

> Append-only. ChatGPT lo deja vacío. El orquestador añade filas aquí si QA descubre trabajo nuevo.