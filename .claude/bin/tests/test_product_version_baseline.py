from __future__ import annotations

import argparse
import json
from pathlib import Path


def test_coverage_registry_product_increment_and_build_state_drive_initial_status(tmp_project):
    import bootstrap_source_of_truth as boot

    checklist = tmp_project / "docs" / "source-of-truth" / "APP_IMPLEMENTATION_CHECKLIST.md"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    text = """# Phase 0 — Base

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | setup | built base | Step 0.1 | v0 | done | low | auto | — | setup | scripts/** | — | — | GET /health | — | §1 | §6 | built | smoke |
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
    assert by_id["P00-S01-T001"]["product_increment"] == "v0"
    assert by_id["P00-S02-T001"]["status"] == "blocked"
    assert by_id["P00-S02-T001"]["product_increment"] == "v1"
    assert phases[0]["status"] == "done" or phases[0]["status"] == "ready"


def _write_complete_source_pack(root):
    sot = root / "docs" / "source-of-truth"
    sot.mkdir(parents=True, exist_ok=True)
    (sot / "instrucciones.md").write_text("# Instrucciones\n\nContenido real.\n", encoding="utf-8")
    (sot / "APP_TECHNICAL_GUIDE.md").write_text("# Technical Guide\n\n## Stack\n", encoding="utf-8")
    (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text("# Phase 0 — Base\n\n## Step 0.1 — One\n", encoding="utf-8")
    (sot / "UX_CONTRACT.md").write_text("# UX Contract\n", encoding="utf-8")
    (sot / "STACK_PROFILE.yaml").write_text("project:\n  profile: large-without-base\n", encoding="utf-8")
    return sot


def _write_verified_handoff(root, task_id="P00-S01-T001"):
    handoff = root / "orchestrator-state" / "tasks" / "handoffs" / f"{task_id}.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "## Validator review\n"
        f"- TASK_ID: {task_id}\n"
        "- OUTCOME: approved\n"
        "## Tester run\n"
        f"- TASK_ID: {task_id}\n"
        "- OUTCOME: pass\n"
        "## verify-slice\n"
        f"- TASK_ID: {task_id}\n"
        "- AGENT: slice-verifier\n"
        "- MODE: pre-closer\n"
        "- MCP_BROWSER: chrome-devtools\n"
        "- VERIFY_OUTCOME: verified\n"
        "- DATA_CONTRACT_ROWS: VDC-001\n"
        "- DATA_SETUP: sandbox-user-1 + seeded record A\n"
        "- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active\n"
        "- FLOWS_TESTED: login happy path\n"
        f"- EVIDENCE: orchestrator-state/tasks/evidence/{task_id}/verify-*\n",
        encoding="utf-8",
    )
    return handoff


def test_sync_product_baseline_copies_five_file_source_pack_and_writes_manifest(tmp_project):
    import sync_product_baseline as spb

    _write_complete_source_pack(tmp_project)
    _write_verified_handoff(tmp_project)

    result = spb.sync(argparse.Namespace(version="v1", task="P00-S01-T001", phase="P00", reason="test", allow_unverified=False))
    assert result["ok"]
    baseline = tmp_project / "docs" / "product-baseline"
    assert (baseline / "instrucciones.md").exists()
    assert (baseline / "APP_TECHNICAL_GUIDE.md").exists()
    assert (baseline / "APP_IMPLEMENTATION_CHECKLIST.md").exists()
    assert (baseline / "UX_CONTRACT.md").exists()
    assert (baseline / "STACK_PROFILE.yaml").exists()
    manifest = json.loads((baseline / "BASELINE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["latest_version"] == "v1"
    assert manifest["latest_task_id"] == "P00-S01-T001"
    assert manifest["snapshots"][-1]["source_pack"] == "five-file"
    assert not list(baseline.glob("*.lock"))
    assert (tmp_project / "orchestrator-state" / "tasks" / "locks" / "product-baseline.json.lock").exists()


def test_sync_product_baseline_status_reports_incomplete_source_pack_without_crashing(tmp_project):
    import sync_product_baseline as spb

    sot = tmp_project / "docs" / "source-of-truth"
    sot.mkdir(parents=True, exist_ok=True)
    (sot / "instrucciones.md").write_text("# Instrucciones\n", encoding="utf-8")
    (sot / "APP_TECHNICAL_GUIDE.md").write_text("# Technical Guide\n", encoding="utf-8")
    (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text("# Checklist\n", encoding="utf-8")

    status = spb.status(argparse.Namespace())
    assert status["ok"]
    assert status["source_pack_ready"] is False
    assert "five-file" in status["source_pack_error"]
    assert "ux" in status["source_pack_error"] and "stack_profile" in status["source_pack_error"]


def test_sync_product_baseline_rejects_incomplete_source_pack(tmp_project):
    import sync_product_baseline as spb

    sot = tmp_project / "docs" / "source-of-truth"
    sot.mkdir(parents=True, exist_ok=True)
    (sot / "instrucciones.md").write_text("# Instrucciones\n", encoding="utf-8")
    (sot / "APP_TECHNICAL_GUIDE.md").write_text("# Technical Guide\n", encoding="utf-8")
    (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text("# Checklist\n", encoding="utf-8")

    try:
        spb.sync(argparse.Namespace(version="v1", task=None, phase=None, reason="manual", allow_unverified=True))
    except SystemExit as exc:
        assert "five-file source-of-truth" in str(exc)
        assert "ux" in str(exc) and "stack_profile" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("sync without UX_CONTRACT/STACK_PROFILE should fail")


def test_sync_product_baseline_refuses_unverified_task(tmp_project):
    import sync_product_baseline as spb

    _write_complete_source_pack(tmp_project)

    try:
        spb.sync(argparse.Namespace(version="v1", task="P00-S01-T001", phase="P00", reason="test", allow_unverified=False))
    except SystemExit as exc:
        assert "verified close" in str(exc) or "handoff" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unverified product-baseline sync should fail")


def test_runtime_followup_registry_phase_without_heading_is_executable(tmp_project):
    import bootstrap_source_of_truth as boot
    from common import promote_ready_tasks

    checklist = tmp_project / "docs" / "source-of-truth" / "APP_IMPLEMENTATION_CHECKLIST.md"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    text = """# Phase 0 — Base

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | setup | built base | Step 0.1 | v0 | done | low | auto | — | setup | scripts/** | — | — | GET /health | — | §1 | §6 | built | smoke |

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


def test_sync_product_baseline_status_handles_empty_source_pack(tmp_project):
    import sync_product_baseline as spb

    result = spb.status(argparse.Namespace())
    assert result["ok"] is True
    assert result["source_pack_ready"] is False
    assert "five-file source-of-truth" in result["source_pack_error"]


def test_sync_product_baseline_manifest_records_writer_and_written_paths(tmp_project):
    import sync_product_baseline as spb

    sot = tmp_project / "docs" / "source-of-truth"
    sot.mkdir(parents=True, exist_ok=True)
    (sot / "instrucciones.md").write_text("# Instrucciones\n", encoding="utf-8")
    (sot / "APP_TECHNICAL_GUIDE.md").write_text("# Technical Guide\n", encoding="utf-8")
    (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text("# Checklist\n", encoding="utf-8")
    (sot / "UX_CONTRACT.md").write_text("# UX\n", encoding="utf-8")
    (sot / "STACK_PROFILE.yaml").write_text("project:\n  profile: large-without-base\n", encoding="utf-8")
    handoff = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / "P00-S01-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "## Validator review\n- TASK_ID: P00-S01-T001\n- OUTCOME: approved\n"
        "## Tester run\n- TASK_ID: P00-S01-T001\n- OUTCOME: pass\n"
        "## verify-slice\n"
        "- TASK_ID: P00-S01-T001\n"
        "- AGENT: slice-verifier\n"
        "- MODE: pre-closer\n"
        "- MCP_BROWSER: chrome-devtools\n"
        "- VERIFY_OUTCOME: verified\n"
        "- DATA_CONTRACT_ROWS: VDC-001\n"
        "- DATA_SETUP: sandbox-user-1 + seeded record A\n"
        "- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active\n"
        "- FLOWS_TESTED: login happy path\n"
        "- EVIDENCE: orchestrator-state/tasks/evidence/P00-S01-T001/verify-*\n",
        encoding="utf-8",
    )

    spb.sync(argparse.Namespace(version="v1", task="P00-S01-T001", phase="P00", reason="test", allow_unverified=False))
    manifest = json.loads((tmp_project / "docs" / "product-baseline" / "BASELINE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["writer"] == "sync_product_baseline.py"
    assert manifest["source_pack_contract"] == "five-file source-of-truth pack"
    assert sorted(manifest["last_written_paths"]) == sorted([
        "docs/product-baseline/APP_IMPLEMENTATION_CHECKLIST.md",
        "docs/product-baseline/APP_TECHNICAL_GUIDE.md",
        "docs/product-baseline/STACK_PROFILE.yaml",
        "docs/product-baseline/UX_CONTRACT.md",
        "docs/product-baseline/instrucciones.md",
    ])
