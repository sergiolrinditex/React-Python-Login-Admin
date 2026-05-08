# {{APP_NAME}} Implementation Checklist — minimal DAG

> Perfil: **minimal**. El `Canonical Coverage Registry` es la fuente del DAG. Mantén 3-8 tasks, phases pequeñas y dependencias reales. El bootstrap debe terminar en `mode=explicit_dag`, nunca `legacy_linear`.

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | db | {{MIGRATION_OR_SCHEMA_CHANGE}} | Step 0.1 | v1 | planned | low | auto | — | db:migrations | {{db_migration_write_set}}; {{backend_test_write_set}} | — | — | — | {{TABLE_1}} | §2.1 | §2.3#{{TABLE_1}} | migración/schema y constraints | {{db.migrate_cmd}} && {{backend.test_cmd}} |
| P01-S01-T001 | api | {{ENDPOINT_1}} | Step 1.1 | v1 | planned | medium | human | P00-S01-T001 | api:{{DOMAIN}} | {{backend.module_root}}/**/{{DOMAIN}}*; {{backend_test_write_set}} | J1 | {{PAGE_1}} {{ROUTE_1}} | {{ENDPOINT_1}} | {{TABLE_1}} | §3#J1 | §2.2#{{ENDPOINT_1}} | endpoint real con DB y auth | {{backend.test_cmd}} |
| P02-S01-T001 | frontend | {{PAGE_1}} | Step 2.1 | v1 | planned | medium | human | P01-S01-T001 | front:{{DOMAIN}}, navigation | {{frontend.module_root}}/**/{{DOMAIN}}*; {{frontend_test_write_set}}; {{frontend_navigation_write_set}} | J1 | {{PAGE_1}} {{ROUTE_1}} | {{ENDPOINT_1}} | — | §3#J1 | §2.1#{{ROUTE_1}} | estados UI y provider conectados | /verify-slice con datos reales/prod-like |
| P03-S01-T001 | journey | J1 e2e | Step 3.1 | v1 | planned | high | human | P02-S01-T001 | journey:{{DOMAIN}} | orchestrator-state/tasks/journey-handoffs/** | J1 | {{PAGE_SEQUENCE}} | {{ENDPOINT_SEQUENCE}} | {{TABLES}} | §3#J1 | §3 Verification Data Contract | J1 verificado de punta a punta | /verify-journey J1 |

## Phase 0 — Data foundation
### Step 0.1 — Schema
- [ ] P00-S01-T001

## Phase 1 — API lane
### Step 1.1 — Endpoint principal
- [ ] P01-S01-T001

## Phase 2 — UI lane
### Step 2.1 — Pantalla principal
- [ ] P02-S01-T001

## Phase 3 — Journey gate
### Step 3.1 — Verify e2e
- [ ] P03-S01-T001

## Runtime Follow-up Coverage Registry

> Append-only. ChatGPT lo deja vacío. El orquestador añade filas aquí si QA descubre trabajo nuevo.
