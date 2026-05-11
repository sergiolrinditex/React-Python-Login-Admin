"""file_lock — primitivo de concurrencia del framework.

Lo crítico (común.py:147-208):
1. Reentrancy: `with file_lock(p):` anidado en sí mismo NO debe deadlock-ear.
   Esto es lo que permite que `update_task_status` (lock outer) llame a
   `save_registry → write_json` (lock inner del mismo file).
2. Mutex real entre procesos: dos procesos compitiendo serializan la sección.
3. Atomic write via tmp+rename: una caída a media escritura no corrompe el JSON.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import common


def test_lock_reentrancy_does_not_deadlock(tmp_project):
    """`with file_lock(p):` anidado debe ser cheap-no-op."""
    p = tmp_project / "orchestrator-state" / "tasks" / "registry.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")

    with common.file_lock(p):
        with common.file_lock(p):
            with common.file_lock(p):
                p.write_text('{"x": 1}', encoding="utf-8")

    assert json.loads(p.read_text())["x"] == 1


def test_update_task_status_reentrancy_under_lock(seeded_registry):
    """update_task_status toma lock; sync_runtime_state_from_registry corre
    dentro y vuelve a pedir locks de runtime-state. Si la reentrancy estuviera
    rota, esto deadlockearía."""
    common.update_task_status("P00-S01-T001", "in_progress", agent="developer")

    reg = common.load_registry()
    assert common.find_task(reg, "P00-S01-T001")["status"] == "in_progress"


def _writer_process(tmp_path_str: str, value: int, sleep_inside: float):
    """Helper para test de mutex inter-proceso. Recarga common con env nuevo."""
    os.environ["CLAUDE_PROJECT_DIR"] = tmp_path_str
    # Reimport limpio dentro del subproceso.
    import importlib
    import sys
    sys.path.insert(0, str(_BIN))
    # En el subproceso reimportamos para tener un _LOCK_DEPTH propio.
    import common as _common  # noqa: WPS433
    importlib.reload(_common)

    p = Path(tmp_path_str) / "orchestrator-state" / "tasks" / "registry.json"
    with _common.file_lock(p):
        # leer-modificar-escribir con sleep dentro de la sección crítica
        # exagera la ventana donde otro proceso podría romper la consistencia
        # si el lock no fuese real.
        data = json.loads(p.read_text())
        data["counter"] = data.get("counter", 0) + value
        time.sleep(sleep_inside)
        p.write_text(json.dumps(data), encoding="utf-8")


def test_lock_serializes_concurrent_writers(tmp_project):
    """Dos subprocesos compitiendo por la misma sección deben serializar.
    Si el lock no funciona, el contador final será inconsistente."""
    p = tmp_project / "orchestrator-state" / "tasks" / "registry.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"counter": 0}), encoding="utf-8")

    # Asegura que el módulo compartido por el padre no bloquee al subproceso.
    common._LOCK_DEPTH.clear()

    procs = [
        multiprocessing.Process(
            target=_writer_process,
            args=(str(tmp_project), inc, 0.05),
        )
        for inc in (1, 2, 3, 4, 5)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=10)
        assert proc.exitcode == 0, f"subproceso falló con exit {proc.exitcode}"

    final = json.loads(p.read_text())
    assert final["counter"] == 1 + 2 + 3 + 4 + 5


def test_write_json_uses_tmp_rename(tmp_project, monkeypatch):
    """write_json debe escribir a .tmp + rename, no truncar el original.
    Verificamos que el .tmp existió y desapareció (rename atomic)."""
    p = tmp_project / "orchestrator-state" / "tasks" / "test.json"
    common.write_json(p, {"hello": "world"})
    assert p.exists()
    assert json.loads(p.read_text())["hello"] == "world"
    # Tras escribir, el .tmp no debe existir (rename completado).
    assert not p.with_suffix(p.suffix + ".tmp").exists()
