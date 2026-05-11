"""promote_ready_tasks + choose_next_scheduler_task — núcleo de la selección
del planner. Si esto se rompe, el planner elegiría tasks con dependencias
sin resolver o se quedaría bloqueado eligiéndose la misma siempre.
"""
from __future__ import annotations

import common


def test_initial_state_only_first_task_ready(seeded_registry):
    reg = common.load_registry()
    statuses = {t["id"]: t["status"] for t in reg["tasks"]}
    assert statuses["P00-S01-T001"] == "ready"
    # El resto debe estar blocked (depende de T001 o de tasks de otra phase).
    for tid, st in statuses.items():
        if tid != "P00-S01-T001":
            assert st == "blocked"


def test_promote_after_done_unblocks_next(seeded_registry):
    reg = common.load_registry()
    common.find_task(reg, "P00-S01-T001")["status"] = "done"
    reg = common.promote_ready_tasks(reg)

    statuses = {t["id"]: t["status"] for t in reg["tasks"]}
    assert statuses["P00-S01-T001"] == "done"
    assert statuses["P00-S01-T002"] == "ready"
    # Las de phase siguiente siguen bloqueadas (esperan a P00-S01-T002).
    assert statuses["P01-S01-T001"] == "blocked"


def test_full_chain_of_promotions(seeded_registry):
    """Marca todas las tasks como done en cadena y comprueba que cada
    promote desbloquea exactamente la siguiente."""
    reg = common.load_registry()
    chain = [
        "P00-S01-T001", "P00-S01-T002",
        "P01-S01-T001", "P01-S01-T002",
        "P02-S01-T001", "P02-S01-T002",
    ]
    for i, tid in enumerate(chain):
        common.find_task(reg, tid)["status"] = "done"
        reg = common.promote_ready_tasks(reg)
        if i + 1 < len(chain):
            next_tid = chain[i + 1]
            assert common.find_task(reg, next_tid)["status"] == "ready", (
                f"tras done {tid}, esperaba {next_tid} ready, vi "
                f"{common.find_task(reg, next_tid)['status']}"
            )


def test_test_choose_next_scheduler_picks_first_ready_in_phase_order(seeded_registry):
    """choose_next_scheduler_task respeta phase_order y elige la primera ready."""
    phase, task = common.choose_next_scheduler_task(common.load_registry())
    assert phase["id"] == "P00"
    assert task["id"] == "P00-S01-T001"


def test_choose_next_skips_done_phases(seeded_registry):
    """Una phase con todas sus tasks done no debe ser elegida."""
    reg = common.load_registry()
    for tid in ("P00-S01-T001", "P00-S01-T002"):
        common.find_task(reg, tid)["status"] = "done"
    reg = common.promote_ready_tasks(reg)
    common.save_registry(reg)

    phase, task = common.choose_next_scheduler_task(common.load_registry())
    assert phase["id"] == "P01"
    assert task["id"] == "P01-S01-T001"


def test_choose_next_returns_none_when_all_done(seeded_registry):
    reg = common.load_registry()
    for t in reg["tasks"]:
        t["status"] = "done"
    common.save_registry(reg)

    phase, task = common.choose_next_scheduler_task(common.load_registry())
    assert phase is None
    assert task is None


def test_task_in_progress_takes_priority_over_ready_in_later_phase(seeded_registry):
    """Si hay una task in_progress en una phase anterior, se elige esa
    aunque haya readys en otra phase."""
    reg = common.load_registry()
    # Marca T001 como in_progress (ej. developer trabajando).
    common.find_task(reg, "P00-S01-T001")["status"] = "in_progress"
    common.save_registry(reg)

    _, task = common.choose_next_scheduler_task(common.load_registry())
    assert task["id"] == "P00-S01-T001"
    assert task["status"] == "in_progress"


def test_phase_status_refresh(seeded_registry):
    """refresh_phase_statuses marca la phase como complete cuando todas
    sus tasks están done."""
    reg = common.load_registry()
    for tid in ("P00-S01-T001", "P00-S01-T002"):
        common.find_task(reg, tid)["status"] = "done"
    reg = common.refresh_phase_statuses(reg)

    p00 = common.find_phase(reg, "P00")
    assert p00["status"] == "complete"
    p01 = common.find_phase(reg, "P01")
    # P01-S01-T001 sigue blocked porque T001 hasta hace nada estaba ready en P00.
    # Después del refresh, P01-T001 sigue blocked (no hemos llamado promote).
    # Su phase se marcará blocked o ready según task_is_ready.
    assert p01["status"] in {"ready", "blocked"}


def test_task_is_ready_with_dep_chain(seeded_registry):
    reg = common.load_registry()
    t002 = common.find_task(reg, "P00-S01-T002")
    # Depende de T001 que está ready (no done) → no es ready aún.
    assert not common.task_is_ready(reg, t002)

    common.find_task(reg, "P00-S01-T001")["status"] = "done"
    assert common.task_is_ready(reg, t002)
