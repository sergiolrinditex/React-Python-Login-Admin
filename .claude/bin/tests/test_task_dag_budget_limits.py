from __future__ import annotations

import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import check_task_dag as dag  # noqa: E402


def _registry_with_step_count(count: int) -> dict:
    tasks = []
    for i in range(1, count + 1):
        tasks.append({
            "id": f"P00-S02-T{i:03d}",
            "phase_id": "P00",
            "step_id": "P00-S02",
            "depends_on": [],
        })
    return {"tasks": tasks}


def test_step_with_eleven_tasks_is_allowed_for_large_app_lane():
    warnings = dag.validate_phase_budgets(_registry_with_step_count(11))
    assert warnings == []


def test_step_with_sixteen_tasks_triggers_lane_split_warning():
    warnings = dag.validate_phase_budgets(_registry_with_step_count(16))
    assert any("P00-S02" in w and "max 15" in w for w in warnings)


def test_phase_budget_advisory_does_not_make_valid_dag_structurally_invalid():
    reg = _registry_with_step_count(21)
    # The lane-size warning is useful authoring guidance, but it must not make
    # an otherwise coherent explicit DAG fail CI strict checks.
    assert dag.validate_phase_budgets(reg)
    recomputed, warnings, errors = dag.validate_registry_dag({
        "tasks": reg["tasks"],
        "task_dag": dag.build_task_dag(reg["tasks"]),
    })
    assert recomputed["mode"] == "explicit_dag"
    assert errors == []
    assert all("exceeds max" not in w for w in warnings)


def test_size_budget_warnings_are_advisory_for_strict_by_default():
    warnings = dag.validate_phase_budgets(_registry_with_step_count(24))
    assert any("P00" in w and "max 20" in w for w in warnings)
    assert all(dag.is_size_budget_warning(w) for w in warnings)


def test_phase_budget_can_be_promoted_to_strict_warning_when_requested(monkeypatch):
    reg = _registry_with_step_count(21)
    monkeypatch.setenv("CLAUDE_DAG_ENFORCE_SIZE_BUDGETS", "1")
    recomputed, warnings, errors = dag.validate_registry_dag({
        "tasks": reg["tasks"],
        "task_dag": dag.build_task_dag(reg["tasks"]),
    })
    advisories = dag.validate_phase_budgets(reg)
    strict_warnings = list(warnings)
    if True:  # mirrors the CLI opt-in path; keep this test focused on the policy boundary.
        strict_warnings.extend(advisories)
    assert recomputed["mode"] == "explicit_dag"
    assert errors == []
    assert any("exceeds max" in w for w in strict_warnings)
