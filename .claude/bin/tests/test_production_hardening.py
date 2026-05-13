from __future__ import annotations


def test_journey_matrix_header_inserted_column():
    from check_journey_matrix import find_matrix_table
    text = """## Journey Coverage Matrix

| ID | Extra | Milestone | Pantallas (en orden) | Acciones clave | Endpoints | Tablas DB | Estado cliente | Slices | Verificación |
|----|-------|-----------|----------------------|----------------|-----------|-----------|----------------|--------|--------------|
| J1 | note | M1 | A → B | click | GET /x | table_x | provider | P00-S01-T001 | /verify-journey J1 |
"""
    _line, rows, errors = find_matrix_table(text)
    assert not errors
    assert rows[0]["slices"] == "P00-S01-T001"
    assert rows[0]["verification"] == "/verify-journey J1"


def test_hook_rejects_invalid_outcome_enum():
    from hook_capture_subagent_stop import trailer_value_errors
    assert trailer_value_errors({"outcome": "approved"}, "tester")
    assert not trailer_value_errors({"outcome": "pass", "next_status": "ready_for_close"}, "tester")


def test_auto_verify_requires_low_auto():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "auto_verify_slice.py").read_text(encoding="utf-8")
    assert "risk !=" in text and "mode !=" in text


def test_bootstrap_journey_matrix_header_inserted_column_not_positional():
    import bootstrap_source_of_truth as boot
    text = """## Journey Coverage Matrix

| ID | Extra | Milestone | Pantallas (en orden) | Acciones clave | Endpoints | Tablas DB | Estado cliente | Slices | Verificación |
|----|-------|-----------|----------------------|----------------|-----------|-----------|----------------|--------|--------------|
| J1 | note | M1 | A → B | click | GET /x | table_x | provider | P00-S01-T001 | /verify-journey J1 |
"""
    journeys = boot.extract_journey_matrix(text, [{"id": "P00-S01-T001", "phase_id": "P00", "step_id": "P00-S01"}])
    assert journeys[0]["task_ids"] == ["P00-S01-T001"]
    assert journeys[0]["verification"] == "/verify-journey J1"


def test_bootstrap_verify_mode_is_not_verification_command():
    import bootstrap_source_of_truth as boot
    text = """| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | api | GET /health | Step 0.1 | v1 | planned | low | auto | — | api:health | api/** | — | — | GET /health | — | §3.1 | §6.2 | ok | curl /health |
"""
    rows = boot.parse_coverage_registry(text)
    assert rows[0]["verify_mode"] == "auto"
    assert rows[0]["verification_commands"] == ["curl /health"]


def test_wiring_contract_rejects_auto_verify_placeholder():
    from check_wiring_contract import looks_like_auto_verify_command
    assert not looks_like_auto_verify_command("auto")
    assert looks_like_auto_verify_command("pytest tests/test_health.py")


def test_bootstrap_registry_carries_front_back_db_wiring_metadata():
    import bootstrap_source_of_truth as boot
    text = """| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P03-S01-T001 | flutter | TasksPage | Step 3.1 | v1 | planned | medium | human | P02-S01-T001 | front:tasks, router | app/lib/features/tasks/**; app/lib/core/router.dart | J101 | TasksPage /tasks | GET /api/v1/tasks | tasks | §3.7#J101 | §6.1#/tasks | UI wired | /verify-slice con backend real |
"""
    row = boot.parse_coverage_registry(text)[0]
    assert row["kind"] == "flutter"
    assert row["target"] == "TasksPage"
    assert row["journey_refs"] == ["J101"]
    assert row["route"] == "TasksPage /tasks"
    assert row["endpoint"] == "GET /api/v1/tasks"
    assert row["tables"] == ["tasks"]
    assert row["origin_instr"] == "§3.7#J101"
    assert row["origin_techguide"] == "§6.1#/tasks"
    assert row["verification_commands"] == ["/verify-slice con backend real"]


def test_wiring_parser_ignores_unrelated_id_tables_outside_journey_section():
    from check_wiring_contract import parse_journeys
    text = """# Instructions

## Business rules

| ID | Rule | Owner |
|---|---|---|
| R1 | This is not a journey | product |

## Journey Coverage Matrix

| ID | Milestone | Pantallas/Screens | Acciones/Actions | Endpoints | Tablas/Tables | Estado cliente/Client state | Slices | Verificación/Verification |
|---|---|---|---|---|---|---|---|---|
| J1 | M1 | LoginPage → TasksPage | login, list | POST /auth/login, GET /tasks | users, tasks | authProvider, tasksProvider | P01-S01-T001, P02-S01-T001 | /verify-journey J1 |
"""
    journeys, errors = parse_journeys(text)
    assert errors == []
    assert [j["id"] for j in journeys] == ["J1"]



def test_orchestrator_contract_has_role_trailer_schema():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    contract = json.loads((root / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    roles = contract["trailer_schema"]["roles"]

    assert roles["tester"]["outcome_values"] == ["pass", "fail", "blocked"]
    assert roles["tester"]["next_status_values"] == ["ready_for_close", "needs_debug", "blocked"]
    assert roles["closer"]["outcome_values"] == ["committed", "blocked"]
    assert roles["closer"]["next_status_values"] == ["done", "blocked"]
    assert "outcome" + "_enums" not in contract
    assert "next_status" + "_enums" not in contract


def test_hook_loads_enums_from_trailer_schema_contract():
    from hook_capture_subagent_stop import load_enum_contracts

    outcomes, statuses = load_enum_contracts()
    assert outcomes["tester"] == {"pass", "fail", "blocked"}
    assert statuses["tester"] == {"ready_for_close", "needs_debug", "blocked"}
    assert outcomes["closer"] == {"committed", "blocked"}
    assert statuses["closer"] == {"done", "blocked"}
