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
