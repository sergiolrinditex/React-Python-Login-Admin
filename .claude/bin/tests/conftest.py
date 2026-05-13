"""Test fixtures for .claude/bin tests.

Goal: aislar cada test en un repo de proyecto temporal sin tocar el real.
Se basa en la variable `CLAUDE_PROJECT_DIR` que `common.project_root()` lee
dinámicamente (no la cachea), por lo que el monkey-patch via env var basta.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Asegura que `.claude/bin/` está en sys.path para `import common, hook_*`,
# y `.claude/bin/tests/` para `import _helpers`.
_BIN_DIR = Path(__file__).resolve().parent.parent
_TESTS_DIR = Path(__file__).resolve().parent
for _p in (_BIN_DIR, _TESTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """Repo temporal con la estructura mínima esperada por los hooks.

    Setea `CLAUDE_PROJECT_DIR` para que `common.project_root()` apunte aquí.
    Recarga los módulos `common` + `hook_capture_subagent_stop` para que los
    contadores de lock (`_LOCK_DEPTH`) empiecen limpios entre tests.
    """
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    (tmp_path / "orchestrator-state" / "tasks").mkdir(parents=True)
    (tmp_path / "orchestrator-state" / "memory").mkdir(parents=True)
    (tmp_path / ".claude").mkdir(parents=True)
    contract_src = _BIN_DIR.parent / "orchestrator-contract.json"
    if contract_src.exists():
        (tmp_path / ".claude" / "orchestrator-contract.json").write_text(contract_src.read_text(encoding="utf-8"), encoding="utf-8")

    # Limpiar el counter de lock entre tests (estado de módulo).
    import common  # noqa: WPS433 (intencional)
    common._LOCK_DEPTH.clear()

    return tmp_path


@pytest.fixture
def seeded_registry(tmp_project):
    """Registry de juguete con 3 phases × 2 tasks cada una. Útil para tests
    de race condition y de promote_ready_tasks."""
    import common

    tasks = []
    phases = []
    phase_order = []
    for p in range(3):
        phase_id = f"P{p:02d}"
        phase_order.append(phase_id)
        phase_tasks = []
        for t in range(1, 3):
            tid = f"{phase_id}-S01-T{t:03d}"
            phase_tasks.append(tid)
            depends_on = []
            if p > 0 and t == 1:
                # primera task de cada phase >0 depende de la última de la phase anterior
                depends_on = [f"P{p-1:02d}-S01-T002"]
            elif t > 1:
                depends_on = [f"{phase_id}-S01-T001"]
            tasks.append({
                "id": tid,
                "title": f"Task {tid}",
                "phase_id": phase_id,
                "step_id": f"{phase_id}-S01",
                "status": "ready" if (p == 0 and t == 1) else "blocked",
                "depends_on": depends_on,
            })
        phases.append({
            "id": phase_id,
            "title": f"Phase {p}",
            "status": "ready" if p == 0 else "blocked",
            "task_ids": phase_tasks,
        })

    registry = {
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": phase_order,
        "phases": phases,
        "tasks": tasks,
        "journeys": [],
    }
    common.save_registry(registry)
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "last_worker": None,
        "last_event": None,
        "pending_journey_verifications": [],
        "last_journey_verified": None,
    })
    return registry


# Re-export para tests que prefieran importar desde `conftest` (poco común,
# pero compatible). El helper canónico vive en `_helpers.py`.
from _helpers import make_subagent_stop_payload  # noqa: F401, E402
