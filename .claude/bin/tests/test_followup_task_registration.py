from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import common
import hook_capture_subagent_stop
import register_followup_task as fut
from claim_task import claim_task
from next_wave import compute_wave
from _helpers import make_subagent_stop_payload


def _args(**kwargs):
    defaults = dict(
        id=None,
        origin_task="P00-S01-T001",
        title="Missing real provided data for upload error state",
        description="Verify found that the error state uses decorative data instead of persisted sandbox data.",
        kind="data",
        severity="high",
        scope_classification="missing_coverage",
        why_not_debugger="requires new coverage registry row outside current TASK_ID",
        phase=None,
        step=None,
        depends_on=None,
        conflict_group=["front:upload"],
        write_set=["app/lib/features/upload/**"],
        journey_ref=["J1"],
        screen_route="UploadPage /upload",
        endpoint="POST /api/v1/upload",
        table=["uploads"],
        acceptance=["Real/provided data persisted and documented"],
        verify=["/verify-slice observes persisted upload row"],
        note=None,
    )
    defaults.update(kwargs)
    return Namespace(**defaults)


def test_propose_followup_writes_yaml_and_blocks_claim_and_wave(seeded_registry):
    result = fut.propose(_args())
    assert result["ok"] is True
    fid = result["followup_id"]
    path = common.project_root() / "orchestrator-state" / "tasks" / "follow-ups" / f"{fid}.yaml"
    assert path.exists()
    runtime = common.load_runtime_state()
    assert runtime["open_followups"][0]["id"] == fid

    ok, denied = claim_task("P00-S01-T001")
    assert ok is False
    assert "blocking follow-up" in denied["error"]

    wave = compute_wave(common.load_registry())
    assert wave["ok"] is False
    assert wave["blocking_followups"][0]["id"] == fid


def test_promote_followup_adds_registry_work_item_source_doc_and_dag(seeded_registry, tmp_project):
    docs = tmp_project / "docs" / "source-of-truth"
    docs.mkdir(parents=True)
    (docs / "TEST_IMPLEMENTATION_CHECKLIST.md").write_text("# TEST Checklist\n\n# Phase 0 — Base\n\n## Step 0.1 — Existing\n\n- [ ] existing\n", encoding="utf-8")
    result = fut.propose(_args(severity="medium", journey_ref=[]))
    fid = result["followup_id"]

    promoted = fut.promote(Namespace(followup_id=fid, task_id=None, origin_task=None, phase=None, step=None, depends_on=None, no_source_doc_update=False))
    assert promoted["ok"] is True
    tid = promoted["task_id"]
    assert tid.startswith("P00-S01-T")
    reg = common.load_registry()
    task = common.find_task(reg, tid)
    assert task is not None
    assert task["origin"]["followup_id"] == fid
    assert "task_dag" in reg and tid in reg["task_dag"]["nodes"]
    work_item_path = tmp_project / "orchestrator-state" / "tasks" / "work-items" / f"{tid}.yaml"
    assert work_item_path.exists()
    work_item_text = work_item_path.read_text(encoding="utf-8")
    assert 'kind: "data"' in work_item_text
    assert 'target: "Missing real provided data for upload error state"' in work_item_text
    assert 'route: "UploadPage /upload"' in work_item_text
    assert 'endpoint: "POST /api/v1/upload"' in work_item_text
    assert 'tables:\n  - "uploads"' in work_item_text
    assert 'allowed_paths:\n  - "app/lib/features/upload/**"' in work_item_text
    assert 'write_set:\n  - "app/lib/features/upload/**"' in work_item_text
    assert (tmp_project / "orchestrator-state" / "tasks" / "phases" / "P00.yaml").exists()
    checklist = (docs / "TEST_IMPLEMENTATION_CHECKLIST.md").read_text(encoding="utf-8")
    assert "Runtime Follow-up Coverage Registry" in checklist
    assert tid in checklist
    runtime = common.load_runtime_state()
    item = [x for x in runtime["open_followups"] if x["id"] == fid][0]
    assert item["status"] == "promoted"
    assert item["promoted_task_id"] == tid




def test_promote_rejects_unknown_journey_refs_before_mutating_source_doc(seeded_registry, tmp_project):
    import pytest

    docs = tmp_project / "docs" / "source-of-truth"
    docs.mkdir(parents=True)
    checklist = docs / "TEST_IMPLEMENTATION_CHECKLIST.md"
    checklist.write_text("# TEST Checklist\n\n# Phase 0 — Base\n\n## Step 0.1 — Existing\n\n- [ ] existing\n", encoding="utf-8")

    result = fut.propose(_args(severity="medium", journey_ref=["J404"]))
    with pytest.raises(SystemExit) as exc:
        fut.promote(Namespace(followup_id=result["followup_id"], task_id=None, origin_task=None, phase=None, step=None, depends_on=None, no_source_doc_update=False))
    assert "unknown journey_refs" in str(exc.value)
    assert "J404" in str(exc.value)
    assert "Runtime Follow-up Coverage Registry" not in checklist.read_text(encoding="utf-8")


def test_promote_normalizes_short_step_id_and_writes_phase_yaml(seeded_registry, tmp_project):
    docs = tmp_project / "docs" / "source-of-truth"
    docs.mkdir(parents=True)
    (docs / "TEST_IMPLEMENTATION_CHECKLIST.md").write_text("# TEST Checklist\n\n# Phase 0 — Base\n\n## Step 0.1 — Existing\n\n- [ ] existing\n", encoding="utf-8")

    result = fut.propose(_args(severity="medium", phase="P04", step="S01", journey_ref=[]))
    promoted = fut.promote(Namespace(followup_id=result["followup_id"], task_id=None, origin_task=None, phase=None, step=None, depends_on=None, no_source_doc_update=False))
    assert promoted["ok"] is True
    assert promoted["task_id"].startswith("P04-S01-T")
    phase_yaml = tmp_project / "orchestrator-state" / "tasks" / "phases" / "P04.yaml"
    assert phase_yaml.exists()
    assert promoted["task_id"] in phase_yaml.read_text(encoding="utf-8")


def test_promoted_followup_blocks_when_it_conflicts_with_worker_task(seeded_registry, tmp_project):
    docs = tmp_project / "docs" / "source-of-truth"
    docs.mkdir(parents=True)
    (docs / "TEST_IMPLEMENTATION_CHECKLIST.md").write_text("# TEST Checklist\n\n# Phase 0 — Base\n\n## Step 0.1 — Existing\n\n- [ ] existing\n", encoding="utf-8")

    registry = common.load_registry()
    origin = common.find_task(registry, "P00-S01-T001")
    active = common.find_task(registry, "P00-S01-T002")
    origin["status"] = "done"
    active["status"] = "claimed"
    active["conflict_groups"] = ["front:upload"]
    active["write_set"] = ["app/lib/features/upload/**"]
    common.save_registry(registry)

    result = fut.propose(_args(severity="medium", journey_ref=[]))
    promoted = fut.promote(Namespace(followup_id=result["followup_id"], task_id=None, origin_task=None, phase=None, step=None, depends_on=None, no_source_doc_update=False))
    assert promoted["ok"] is True
    assert promoted["status"] == "blocked"

    reg = common.load_registry()
    task = common.find_task(reg, promoted["task_id"])
    assert task["status"] == "blocked"
    assert task["blocked_reason"] == "conflict_with_worker_task"
    assert task["blocked_by"] == ["P00-S01-T002"]
    assert task["last_blocker"]["type"] == "conflict_with_worker_task"

    active = common.find_task(reg, "P00-S01-T002")
    active["status"] = "done"
    reg = common.promote_ready_tasks(reg)
    task = common.find_task(reg, promoted["task_id"])
    assert task["status"] == "ready"
    assert "blocked_reason" not in task
    assert "last_blocker" not in task


def test_closer_done_allows_formal_proposed_blocker_followup_for_pr(seeded_registry, monkeypatch):
    result = fut.propose(_args(severity="blocker"))
    handoff = common.project_root() / "orchestrator-state" / "tasks" / "handoffs" / "P00-S01-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "# Handoff P00-S01-T001\n\n"
        "## Validator review\n- TASK_ID: P00-S01-T001\n- OUTCOME: approved\n\n"
        "## Tester run\n- TASK_ID: P00-S01-T001\n- OUTCOME: pass\n\n"
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
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    payload = make_subagent_stop_payload("closer", [
        "TASK_ID: P00-S01-T001",
        "OUTCOME: committed",
        "NEXT_STATUS: done",
        "HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md",
        "REPORT: orchestrator-state/tasks/reports/P00-S01-T001.md",
        "REPORT_READY: yes",
        "BASELINE_SYNC_READY: yes",
        "GIT_READY: yes",
        "PUSH_READY: yes",
        "GIT_WORKFLOW_READY: yes",
        "WORKTREES_CLEANED: yes",
    ])
    monkeypatch.setattr("sys.stdin", type("In", (), {"read": lambda self: payload})())
    assert hook_capture_subagent_stop.main() == 0
    task = common.find_task(common.load_registry(), "P00-S01-T001")
    assert task["status"] == "done"
    runtime = common.load_runtime_state()
    assert runtime["last_trailer"]["next_status"] == "done"
    assert runtime["open_followups"][0]["id"] == result["followup_id"]
    assert runtime["open_followups"][0]["status"] == "proposed"


def test_rejects_in_scope_defect_followup_spam(seeded_registry):
    import pytest
    with pytest.raises(SystemExit) as exc:
        fut.propose(_args(
            severity="medium",
            scope_classification="in_scope_defect",
            why_not_debugger="should not matter",
        ))
    assert "debugger" in str(exc.value)
    assert "same TASK_ID" in str(exc.value)


def test_blocking_followup_requires_triage_reason(seeded_registry):
    import pytest
    args = _args(
        severity="high",
        scope_classification="missing_coverage",
        why_not_debugger="",
    )
    with pytest.raises(SystemExit) as exc:
        fut.propose(args)
    assert "--why-not-debugger" in str(exc.value)


def test_nonblocking_untriaged_followup_is_marked_with_warning(seeded_registry):
    result = fut.propose(_args(
        severity="medium",
        scope_classification="unspecified",
        why_not_debugger="",
    ))
    assert result["ok"] is True
    assert result["scope_classification"] == "unspecified"
    assert result["triage_warnings"]
    proposal_path = common.project_root() / result["proposal_path"]
    text = proposal_path.read_text(encoding="utf-8")
    assert "follow-up triage is unspecified" in text


def test_cli_json_flag_is_accepted_after_subcommand(seeded_registry, capsys):
    # Exercise the argparse path directly because users naturally type
    # `register-followup-task.sh list --json` after the subcommand.
    import sys
    old_argv = sys.argv
    try:
        sys.argv = ["register_followup_task.py", "list", "--json"]
        assert fut.main() == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["ok"] is True
        assert "followups" in data
    finally:
        sys.argv = old_argv


def test_reconciler_restores_open_followups_from_yaml_if_runtime_was_reset(seeded_registry):
    result = fut.propose(_args(severity="blocker"))
    fid = result["followup_id"]
    runtime = common.load_runtime_state()
    runtime["open_followups"] = []
    common.save_runtime_state(runtime)

    repaired, repairs = common.reconcile_runtime_state(common.load_registry(), apply=True)

    assert any(r.get("field") == "open_followups" and r.get("added") == fid for r in repairs)
    assert repaired["open_followups"][0]["id"] == fid
    assert common.load_runtime_state()["open_followups"][0]["id"] == fid


def test_promote_blocks_likely_duplicate_followup_without_override(seeded_registry):
    import pytest
    import register_followup_task as fut

    first = fut.propose(_args(title="Fix auth response code", kind="bug", scope_classification="out_of_scope", why_not_debugger="outside write_set", journey_ref=[]))
    promoted = fut.promote(type("Args", (), {"followup_id": first["followup_id"], "task_id": None, "origin_task": None, "phase": None, "step": None, "depends_on": None, "no_source_doc_update": True, "allow_duplicate": False})())
    assert promoted["ok"] is True

    second = fut.propose(_args(title="Fix auth response code", kind="bug", scope_classification="out_of_scope", why_not_debugger="outside write_set", journey_ref=[]))
    with pytest.raises(SystemExit) as exc:
        fut.promote(type("Args", (), {"followup_id": second["followup_id"], "task_id": None, "origin_task": None, "phase": None, "step": None, "depends_on": None, "no_source_doc_update": True, "allow_duplicate": False})())
    assert "possible duplicate follow-up" in str(exc.value)
