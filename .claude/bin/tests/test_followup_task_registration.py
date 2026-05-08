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
        title="Missing real-data fixture for upload error state",
        description="Verify found that the error state uses decorative data instead of persisted sandbox data.",
        kind="data",
        severity="high",
        phase=None,
        step=None,
        depends_on=None,
        conflict_group=["front:upload"],
        write_set=["app/lib/features/upload/**"],
        journey_ref=["J1"],
        screen_route="UploadPage /upload",
        endpoint="POST /api/v1/upload",
        table=["uploads"],
        acceptance=["Fixture real/prod-like persisted and documented"],
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
    result = fut.propose(_args(severity="medium"))
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
    assert (tmp_project / "orchestrator-state" / "tasks" / "work-items" / f"{tid}.yaml").exists()
    checklist = (docs / "TEST_IMPLEMENTATION_CHECKLIST.md").read_text(encoding="utf-8")
    assert "Runtime Follow-up Coverage Registry" in checklist
    assert tid in checklist
    runtime = common.load_runtime_state()
    item = [x for x in runtime["open_followups"] if x["id"] == fid][0]
    assert item["status"] == "promoted"
    assert item["promoted_task_id"] == tid


def test_closer_done_is_blocked_by_unpromoted_blocker_followup(seeded_registry, monkeypatch):
    fut.propose(_args(severity="blocker"))
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
        "WORKTREES_CLEANED: yes",
    ])
    monkeypatch.setattr("sys.stdin", type("In", (), {"read": lambda self: payload})())
    assert hook_capture_subagent_stop.main() == 0
    task = common.find_task(common.load_registry(), "P00-S01-T001")
    assert task["status"] == "blocked"
    runtime = common.load_runtime_state()
    assert runtime["last_trailer"]["closer_guardrail"] == "blocked_false_done"
    assert "blocking_followups" in runtime["last_trailer"]


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
