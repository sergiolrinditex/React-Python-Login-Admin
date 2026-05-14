"""Mechanical /next-wave script contract.

The slash command is narrative, but the scheduler must have a deterministic,
read-only implementation that can be copied into multiple terminals safely.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


def _seed_dag(tmp_project):
    import bootstrap_source_of_truth as boot
    import common

    tasks = [
        {"id": "P00-S01-T001", "title": "GET /health", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": [], "dependency_mode": "explicit_dag"},
        {"id": "P00-S01-T002", "title": "GET /live", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": [], "dependency_mode": "explicit_dag"},
        {"id": "P00-S02-T001", "title": "GET /ready", "phase_id": "P00", "step_id": "P00-S02", "status": "blocked", "depends_on": ["P00-S01-T001", "P00-S01-T002"], "dependency_mode": "explicit_dag"},
    ]
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "ready", "task_ids": [t["id"] for t in tasks]}],
        "tasks": tasks,
        "journeys": [],
        "task_dag": boot.build_task_dag(tasks),
    })
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "last_worker": None,
        "last_event": None,
        "pending_journey_verifications": [],
        "spawns_in_current_slice": {},
    })


def test_next_wave_lists_all_ready_roots_and_does_not_mutate_registry(tmp_project):
    import common
    import next_wave

    _seed_dag(tmp_project)
    before = common.load_registry()
    result = next_wave.compute_wave(before)
    after = common.load_registry()

    assert result["ok"] is True
    assert result["dag_mode"] == "explicit_dag"
    assert [t["id"] for t in result["ready"]] == ["P00-S01-T001", "P00-S01-T002"]
    assert [t["status"] for t in after["tasks"]] == ["ready", "ready", "blocked"]


def test_next_wave_frontier_only_defers_tasks_referencing_pending_journey(tmp_project):
    import common
    import next_wave

    _seed_dag(tmp_project)
    registry = common.load_registry()
    registry["tasks"][0]["journey_refs"] = ["J101"]
    common.save_registry(registry)

    runtime = common.load_runtime_state()
    runtime["pending_journey_verifications"] = ["J101"]
    common.save_runtime_state(runtime)

    result = next_wave.compute_wave(common.load_registry())
    assert result["ok"] is True
    assert [t["id"] for t in result["ready"]] == ["P00-S01-T002"]
    assert [t["id"] for t in result["deferred_due_journey_gate"]] == ["P00-S01-T001"]
    assert result["pending_journey_verifications"] == ["J101"]


def test_next_wave_pending_journey_without_matching_refs_does_not_global_block(tmp_project):
    import common
    import next_wave

    _seed_dag(tmp_project)
    runtime = common.load_runtime_state()
    runtime["pending_journey_verifications"] = ["J101"]
    common.save_runtime_state(runtime)

    result = next_wave.compute_wave(common.load_registry())
    assert result["ok"] is True
    assert [t["id"] for t in result["ready"]] == ["P00-S01-T001", "P00-S01-T002"]
    assert result["pending_journey_verifications"] == ["J101"]


def test_next_wave_can_print_more_than_two_terminal_commands(tmp_project):
    import bootstrap_source_of_truth as boot
    import common
    import next_wave

    tasks = []
    for i in range(1, 5):
        tasks.append({
            "id": f"P00-S01-T{i:03d}",
            "title": f"Independent node {i}",
            "phase_id": "P00",
            "step_id": "P00-S01",
            "status": "ready",
            "depends_on": [],
            "dependency_mode": "explicit_dag",
        })
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "ready", "task_ids": [t["id"] for t in tasks]}],
        "tasks": tasks,
        "journeys": [],
        "task_dag": boot.build_task_dag(tasks),
    })
    common.save_runtime_state({"pending_journey_verifications": [], "spawns_in_current_slice": {}})

    result = next_wave.compute_wave(common.load_registry())
    assert result["ready_count"] == 4
    assert result["recommended_parallel_terminals"] == 4


def test_next_wave_terminal_command_exports_task_pack_and_does_not_preclaim():
    import next_wave

    cmd = next_wave._terminal_command("P00-S01-T001")
    assert "CLAUDE_ACTIVE_TASK_ID=P00-S01-T001" in cmd
    assert "CLAUDE_TASK_PACK=" in cmd
    assert "orchestrator-state/tasks/task-packs/P00-S01-T001.md" in cmd
    assert 'claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P00-S01-T001"' in cmd
    assert "claim_task.py" not in cmd


def test_next_wave_rejects_missing_dag_dependencies_registry_drift(tmp_project):
    import bootstrap_source_of_truth as boot
    import common
    import next_wave

    tasks = [
        {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": []},
        {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "step_id": "P00-S01", "status": "blocked", "depends_on": ["P00-S01-T001"]},
    ]
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "ready", "task_ids": [t["id"] for t in tasks]}],
        "tasks": tasks,
        "journeys": [],
        "task_dag": {"mode": "not_explicit_dag", "nodes": ["P00-S01-T001", "P00-S01-T002"], "edges": []},
    })
    common.save_runtime_state({"pending_journey_verifications": [], "spawns_in_current_slice": {}})
    registry = common.load_registry()
    registry["task_dag"]["mode"] = "not_explicit_dag"
    common.save_registry(registry)

    result = next_wave.compute_wave(common.load_registry())
    assert result["dag_mode"] == "explicit_dag"
    assert result["ok"] is False
    assert result["ready"] == []
    assert any("mode drift" in e for e in result["errors"])

def test_next_wave_pr_flow_terminal_command_enters_task_worktree(tmp_project):
    import next_wave

    stack = tmp_project / "docs" / "source-of-truth" / "STACK_PROFILE.yaml"
    stack.parent.mkdir(parents=True, exist_ok=True)
    stack.write_text("profile_version: stack-profile-v1\ngit_workflow: pr-flow\n", encoding="utf-8")

    cmd = next_wave._terminal_command("P00-S01-T001")
    assert "ensure-task-worktree.sh" in cmd
    assert "--print-root" in cmd
    assert "P00-S01-T001" in cmd
    assert "cd \"$WT\"" in cmd
    assert "CLAUDE_ORCHESTRATOR_ROOT=\"$ROOT\"" in cmd
    assert "CLAUDE_WORKTREE_ROOT=\"$WT\"" in cmd
    assert "PACK=\"$WT/orchestrator-state/tasks/task-packs/P00-S01-T001.md\"" in cmd
    assert "PACK=\"$ROOT/orchestrator-state/tasks/task-packs/P00-S01-T001.md\"" in cmd
    assert "CLAUDE_TASK_PACK=\"$PACK\"" in cmd
    parsed = subprocess.run(["bash", "-n", "-c", cmd], text=True, capture_output=True, timeout=10)
    assert parsed.returncode == 0, parsed.stderr
    assert 'claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P00-S01-T001"' in cmd
