"""Parsing de la Journey Coverage Matrix (§3.5 de instrucciones.md).

El bootstrap genera `registry.journeys[]` desde esta matriz. Si el parsing
silenciosamente ignora una fila, el journey gate del planner nunca se activará
para ese journey y se cerrarán slices sin verificación end-to-end.

Cubrimos:
- Parsing canónico (8-9 columnas).
- Pipes escapados con `\\|` dentro de celdas (caso real OAuth en baseline snapshot).
- Expansión de slice refs: TASK_ID directo, range T001..T003, step ref P00-S05,
  phase ref P00, texto descriptivo (verbatim, marcado como drift).
- Sección ausente devuelve [] (back-compat con proyectos pre-matriz).
"""
from __future__ import annotations

import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import bootstrap_source_of_truth as boot


def _all_tasks() -> list[dict]:
    """Tasks de juguete para resolver step/phase refs."""
    return [
        {"id": "P00-S05-T001", "phase_id": "P00", "step_id": "P00-S05"},
        {"id": "P00-S05-T002", "phase_id": "P00", "step_id": "P00-S05"},
        {"id": "P00-S05-T003", "phase_id": "P00", "step_id": "P00-S05"},
        {"id": "P01-S01-T001", "phase_id": "P01", "step_id": "P01-S01"},
        {"id": "P01-S01-T002", "phase_id": "P01", "step_id": "P01-S01"},
    ]


def test_no_section_returns_empty():
    text = "# Instrucciones\n\nNo hay matriz aquí.\n"
    assert boot.extract_journey_matrix(text, _all_tasks()) == []


def test_minimal_matrix_one_row():
    text = """# Instrucciones

## 3.5 Journey Coverage Matrix

| ID | Milestone | Pantallas | Acciones | Endpoints | Tablas DB | Estado cliente | Slices | Verificación |
|----|-----------|-----------|----------|-----------|-----------|----------------|--------|--------------|
| J101 | M1 | /login → /home | tap login, redirect | POST /auth/login | users, sessions | authState | P00-S05-T001 | login devuelve home |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert len(journeys) == 1
    j = journeys[0]
    assert j["id"] == "J101"
    assert j["milestone"] == "M1"
    assert j["screens"] == ["/login", "/home"]
    assert j["actions"] == ["tap login", "redirect"]
    assert j["endpoints"] == ["POST /auth/login"]
    assert j["tables"] == ["users", "sessions"]
    assert j["client_state"] == ["authState"]
    assert j["task_ids"] == ["P00-S05-T001"]
    assert j["verification_status"] == "pending"
    assert j["verified_at"] is None
    assert j["verify_handoff"] == "orchestrator-state/tasks/journey-handoffs/J101.md"


def test_slice_range_expansion():
    text = """## 3.5 Journey Coverage Matrix

| ID | M | Pantallas | Acciones | EP | Tablas | Estado | Slices | Verif |
|----|---|-----------|----------|----|--------|--------|--------|-------|
| J102 | M1 | /a → /b | x | POST /x | users | s | P00-S05-T001..T003 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert journeys[0]["task_ids"] == ["P00-S05-T001", "P00-S05-T002", "P00-S05-T003"]


def test_step_ref_expansion():
    text = """## 3.5 Journey Coverage Matrix

| ID | M | P | A | EP | T | S | Slices | V |
|----|---|---|---|----|----|----|--------|---|
| J103 | M1 | /a | x | POST /x | users | s | P00-S05 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert journeys[0]["task_ids"] == ["P00-S05-T001", "P00-S05-T002", "P00-S05-T003"]


def test_phase_ref_expansion():
    text = """## 3.5 Journey Coverage Matrix

| ID | M | P | A | EP | T | S | Slices | V |
|----|---|---|---|----|----|----|--------|---|
| J104 | M2 | /a | x | POST /x | users | s | P01 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert journeys[0]["task_ids"] == ["P01-S01-T001", "P01-S01-T002"]


def test_descriptive_slice_kept_verbatim_for_drift_detection():
    """Si la celda es texto en lugar de TASK_ID, se preserva para que el
    validator lo flagee como drift más tarde — no se descarta silenciosamente."""
    text = """## 3.5 Journey Coverage Matrix

| ID | M | P | A | EP | T | S | Slices | V |
|----|---|---|---|----|----|----|--------|---|
| J105 | M1 | /a | x | POST /x | users | s | TODO definir slices | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert journeys[0]["task_ids"] == ["TODO definir slices"]


def test_escaped_pipes_in_cells_do_not_break_columns():
    """Caso real: la celda OAuth en la baseline snapshot contiene 'tap "Continue \\| Google"'.
    El split debe respetar el escape y no contar el `|` como separador."""
    text = """## 3.5 Journey Coverage Matrix

| ID | M | Pantallas | Acciones | EP | Tablas | Estado | Slices | Verif |
|----|---|-----------|----------|----|--------|--------|--------|-------|
| J106 | M1 | /login | tap "Continue \\| Google", redirect | POST /auth/oauth | users | s | P00-S05-T001 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert len(journeys) == 1
    # 'Continue | Google' debe haber sobrevivido como parte de una sola acción.
    assert any('Continue | Google' in a for a in journeys[0]["actions"])
    # El último campo (verificación) no se ha desplazado por el escape.
    assert journeys[0]["verification"] == "ok"


def test_multiple_rows_parsed_in_order():
    text = """## 3.5 Journey Coverage Matrix

| ID | M | P | A | EP | T | S | Slices | V |
|----|---|---|---|----|----|----|--------|---|
| J201 | M1 | /a | x | POST /x | t | s | P00-S05-T001 | ok |
| J202 | M1 | /b | y | POST /y | t | s | P00-S05-T002 | ok |
| J203 | M2 | /c | z | POST /z | t | s | P01-S01-T001 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert [j["id"] for j in journeys] == ["J201", "J202", "J203"]


def test_table_separator_row_is_skipped():
    """La fila '|---|---|' no debe ser parseada como journey."""
    text = """## 3.5 Journey Coverage Matrix

| ID | M | P | A | EP | T | S | Slices | V |
|----|---|---|---|----|----|----|--------|---|
| J999 | M1 | /a | x | POST /x | t | s | P00-S05-T001 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert len(journeys) == 1
    assert journeys[0]["id"] == "J999"


def test_malformed_header_is_not_silently_accepted():
    """Una matriz con header incompleto debe fallar explícitamente.

    Este es el guardrail de producción: si se añade/borra una columna y el
    parser no puede mapear cabeceras semánticas, no debe seguir con datos
    desplazados ni inventar journeys válidos.
    """
    text = """## 3.5 Journey Coverage Matrix

| ID | M | P | A |
|----|---|---|---|
| J404 | M1 | /a | x |
| J200 | M1 | /a | x | POST /x | t | s | P00-S05-T001 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert journeys[0]["id"] == "__JOURNEY_MATRIX_PARSE_ERROR__"
    assert "missing required header" in journeys[0]["errors"][0]


def test_title_built_from_first_3_screens():
    text = """## 3.5 Journey Coverage Matrix

| ID | M | Pantallas | A | EP | T | S | Slices | V |
|----|---|-----------|---|----|----|----|--------|---|
| J301 | M1 | /a → /b → /c → /d → /e | x | POST /x | t | s | P00-S05-T001 | ok |
"""
    journeys = boot.extract_journey_matrix(text, _all_tasks())
    assert journeys[0]["title"] == "/a → /b → /c → ..."
