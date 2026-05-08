from __future__ import annotations

import argparse
import json
from pathlib import Path


def test_coverage_registry_product_increment_and_build_state_drive_initial_status(tmp_project):
    import bootstrap_three_docs as boot

    checklist = tmp_project / "docs" / "source-of-truth" / "APP_IMPLEMENTATION_CHECKLIST.md"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    text = """# Phase 0 — Base

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | setup | built base | Step 0.1 | baseapp | done | low | auto | — | setup | scripts/** | — | — | GET /health | — | §1 | §6 | built | smoke |
| P00-S02-T001 | api | new v1 endpoint | Step 0.2 | v1 | planned | medium | human | P00-S01-T001 | api:v1 | api/src/**/v1*.py | — | — | GET /v1 | — | §1 | §6 | endpoint | curl |

## Step 0.1 — Base
- [ ] built base

## Step 0.2 — v1
- [ ] new endpoint
"""
    checklist.write_text(text, encoding="utf-8")
    phases, tasks = boot.build_phases_and_tasks(checklist, text)
    by_id = {t["id"]: t for t in tasks}
    assert by_id["P00-S01-T001"]["status"] == "done"
    assert by_id["P00-S01-T001"]["product_increment"] == "baseapp"
    assert by_id["P00-S02-T001"]["status"] == "blocked"
    assert by_id["P00-S02-T001"]["product_increment"] == "v1"
    assert phases[0]["status"] == "done" or phases[0]["status"] == "ready"


def test_sync_product_baseline_copies_three_docs_and_writes_manifest(tmp_project):
    import sync_product_baseline as spb

    sot = tmp_project / "docs" / "source-of-truth"
    sot.mkdir(parents=True, exist_ok=True)
    (sot / "instrucciones.md").write_text("# Instrucciones\n\nContenido real.\n", encoding="utf-8")
    (sot / "APP_TECHNICAL_GUIDE.md").write_text("# Technical Guide\n\n## Stack\n", encoding="utf-8")
    (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text("# Phase 0 — Base\n\n## Step 0.1 — One\n", encoding="utf-8")

    result = spb.sync(argparse.Namespace(version="v1", task="P00-S01-T001", phase="P00", reason="test"))
    assert result["ok"]
    assert (tmp_project / "docs" / "base-app" / "instrucciones.md").exists()
    assert (tmp_project / "docs" / "base-app" / "APP_TECHNICAL_GUIDE.md").exists()
    manifest = json.loads((tmp_project / "docs" / "base-app" / "BASELINE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["latest_version"] == "v1"
    assert manifest["latest_task_id"] == "P00-S01-T001"


def test_runtime_followup_registry_phase_without_heading_is_executable(tmp_project):
    import bootstrap_three_docs as boot
    from common import promote_ready_tasks

    checklist = tmp_project / "docs" / "source-of-truth" / "APP_IMPLEMENTATION_CHECKLIST.md"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    text = """# Phase 0 — Base

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | setup | built base | Step 0.1 | baseapp | done | low | auto | — | setup | scripts/** | — | — | GET /health | — | §1 | §6 | built | smoke |

## Step 0.1 — Base
- [ ] built base

## Runtime Follow-up Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P06-S99-T001 | ux | v1 smoke | Runtime follow-up P00-S01-T001 | v1 | planned | medium | human | P00-S01-T001 | front:v1 | app/lib/features/v1/** | J1 | /v1 | GET /health | — | runtime | runtime | screen wired | Chrome real |
"""
    checklist.write_text(text, encoding="utf-8")
    phases, tasks = boot.build_phases_and_tasks(checklist, text)
    by_id = {t["id"]: t for t in tasks}
    assert "P06-S99-T001" in by_id
    assert any(p["id"] == "P06" for p in phases)
    assert by_id["P06-S99-T001"]["product_increment"] == "v1"
    promoted = promote_ready_tasks({"phases": phases, "tasks": tasks})
    promoted_task = next(t for t in promoted["tasks"] if t["id"] == "P06-S99-T001")
    assert promoted_task["status"] == "ready"
