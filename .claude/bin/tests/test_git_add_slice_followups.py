from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_git_add_slice_stages_only_origin_followup_from_canonical_root(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    (canonical / "orchestrator-state/tasks/follow-ups").mkdir(parents=True)
    (canonical / "orchestrator-state/tasks").mkdir(parents=True, exist_ok=True)
    registry = {
        "tasks": [
            {"id": "P00-S01-T001", "write_set": ["app/foo.txt"]},
            {"id": "P00-S01-T002", "write_set": ["app/bar.txt"]},
        ]
    }
    (canonical / "orchestrator-state/tasks/registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (canonical / "orchestrator-state/tasks/follow-ups/FU-own.yaml").write_text(
        "id: FU-own\nstatus: proposed\norigin_task_id: P00-S01-T001\nseverity: high\ntitle: Own\n",
        encoding="utf-8",
    )
    (canonical / "orchestrator-state/tasks/follow-ups/FU-other.yaml").write_text(
        "id: FU-other\nstatus: proposed\norigin_task_id: P00-S01-T002\nseverity: high\ntitle: Other\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    (workspace / "app").mkdir()
    (workspace / "app/foo.txt").write_text("hello\n", encoding="utf-8")
    env = {**os.environ, "CLAUDE_ORCHESTRATOR_ROOT": str(canonical)}

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/git-add-slice.sh"), "P00-S01-T001"],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (workspace / "orchestrator-state/tasks/follow-ups/FU-own.yaml").exists()
    assert not (workspace / "orchestrator-state/tasks/follow-ups/FU-other.yaml").exists()
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout.splitlines()
    assert staged == [
        "app/foo.txt",
        "orchestrator-state/tasks/follow-ups/FU-own.yaml",
        "orchestrator-state/tasks/lifecycle-events/P00-S01-T001.json",
    ]
    event = json.loads((workspace / "orchestrator-state/tasks/lifecycle-events/P00-S01-T001.json").read_text(encoding="utf-8"))
    assert event["schema"] == "orquestador.lifecycle-event.v1"
    assert event["task_id"] == "P00-S01-T001"
    assert event["next_status"] == "done"
    assert event["outcome"] == "committed"
