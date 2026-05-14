from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BIN = ROOT / ".claude" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))


def test_sync_lifecycle_events_rehydrates_registry_without_hook_error(tmp_project, monkeypatch) -> None:
    import common
    from sync_lifecycle_events import apply_events

    registry = {
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "task_ids": ["P00-S01-T001", "P00-S01-T002"], "status": "in_progress"}],
        "tasks": [
            {"id": "P00-S01-T001", "phase_id": "P00", "status": "verified_pending_close", "depends_on": []},
            {"id": "P00-S01-T002", "phase_id": "P00", "status": "blocked", "depends_on": ["P00-S01-T001"]},
        ],
    }
    common.save_registry(registry)
    common.save_runtime_state({"pending_journey_verifications": []})
    events = tmp_project / "orchestrator-state" / "tasks" / "lifecycle-events"
    events.mkdir(parents=True)
    (events / "P00-S01-T001.json").write_text(json.dumps({
        "schema": "orquestador.lifecycle-event.v1",
        "task_id": "P00-S01-T001",
        "agent_type": "closer",
        "outcome": "committed",
        "next_status": "done",
        "created_at": "2026-05-14T00:00:00Z",
        "paths": {
            "handoff": "orchestrator-state/tasks/handoffs/P00-S01-T001.md",
            "evidence": "orchestrator-state/tasks/evidence/P00-S01-T001",
            "report": "orchestrator-state/tasks/reports/P00-S01-T001.md",
        },
    }), encoding="utf-8")

    result = apply_events(dry_run=False)

    assert result["applied"] == ["P00-S01-T001"]
    updated = common.load_registry()
    tasks = {task["id"]: task for task in updated["tasks"]}
    assert tasks["P00-S01-T001"]["status"] == "done"
    assert tasks["P00-S01-T001"]["last_updated_by"] == "closer"
    assert tasks["P00-S01-T002"]["status"] == "ready"
    assert common.load_runtime_state()["last_event"] == "lifecycle_events_synced"
    assert (tmp_project / "orchestrator-state" / "hook-info.log").exists()
    assert not (tmp_project / "orchestrator-state" / "hook-errors.log").exists()


def test_runtime_git_guard_backups_and_restores_tracked_runtime_without_dirty_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True)
    reg = repo / "orchestrator-state" / "tasks" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text('{"tasks":[{"id":"P00-S01-T001","status":"ready"}]}\n', encoding="utf-8")
    subprocess.run(["git", "add", "orchestrator-state/tasks/registry.json"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "track old runtime"], cwd=repo, check=True)
    reg.write_text('{"tasks":[{"id":"P00-S01-T001","status":"done"}]}\n', encoding="utf-8")

    backup = subprocess.run(
        ["python3", "-B", "-S", str(BIN / "runtime_git_guard.py"), "backup", "--root", str(repo), "--json"],
        cwd=repo,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    backup_json = json.loads(backup.stdout)
    assert backup_json["ok"] is True
    assert "orchestrator-state/tasks/registry.json" in backup_json["paths"]
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, timeout=30).stdout.strip() == ""

    restore = subprocess.run(
        ["python3", "-B", "-S", str(BIN / "runtime_git_guard.py"), "restore", "--root", str(repo), "--backup-dir", backup_json["backup_dir"], "--json"],
        cwd=repo,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    restore_json = json.loads(restore.stdout)
    assert "orchestrator-state/tasks/registry.json" in restore_json["restored"]
    assert json.loads(reg.read_text(encoding="utf-8"))["tasks"][0]["status"] == "done"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, timeout=30).stdout.strip() == ""


def test_runtime_git_guard_blocks_non_runtime_dirty_before_sync(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "app.py").write_text("dirty\n", encoding="utf-8")

    result = subprocess.run(
        ["python3", "-B", "-S", str(BIN / "runtime_git_guard.py"), "backup", "--root", str(repo)],
        cwd=repo,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 3
    assert "RUNTIME_GIT_GUARD_READY: no" in result.stdout
    assert "DIRTY_NON_RUNTIME" in result.stdout
    assert "app.py" in result.stdout
