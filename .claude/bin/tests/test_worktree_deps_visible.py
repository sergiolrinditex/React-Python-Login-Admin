from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check-worktree-deps-visible.sh"


def run(cmd: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=30, **kwargs)


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)


def test_check_worktree_deps_visible_blocks_when_origin_has_done_dep_event_missing_from_worktree(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    wt = tmp_path / "wt"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    init_repo(repo)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    tasks_dir = repo / "orchestrator-state/tasks"
    (tasks_dir / "lifecycle-events").mkdir(parents=True)
    registry = {
        "tasks": [
            {"id": "P00-S01-T001", "status": "done", "depends_on": []},
            {"id": "P00-S01-T002", "status": "ready", "depends_on": ["P00-S01-T001"]},
        ]
    }
    (tasks_dir / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md", "orchestrator-state/tasks/registry.json"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, stdout=subprocess.DEVNULL)

    subprocess.run(["git", "branch", "dev/P00-S01-T002"], cwd=repo, check=True)
    subprocess.run(["git", "worktree", "add", str(wt), "dev/P00-S01-T002"], cwd=repo, check=True, stdout=subprocess.DEVNULL)

    (tasks_dir / "lifecycle-events/P00-S01-T001.json").write_text('{"task_id":"P00-S01-T001","next_status":"done","outcome":"committed"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "orchestrator-state/tasks/lifecycle-events/P00-S01-T001.json"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "chore: close P00-S01-T001"], cwd=repo, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "fetch", "origin", "main"], cwd=wt, check=True, stdout=subprocess.DEVNULL)

    env = {**os.environ, "CLAUDE_ORCHESTRATOR_ROOT": str(repo)}
    result = run(["bash", str(SCRIPT), "P00-S01-T002", "--json"], cwd=wt, env=env)

    assert result.returncode == 2, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["reason"] == "stale_worktree_dep_missing"
    assert payload["missing_dependency_visibility"][0]["dependency"] == "P00-S01-T001"


def test_check_worktree_deps_visible_ok_when_dep_event_is_visible(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    tasks_dir = repo / "orchestrator-state/tasks"
    (tasks_dir / "lifecycle-events").mkdir(parents=True)
    registry = {
        "tasks": [
            {"id": "P00-S01-T001", "status": "done", "depends_on": []},
            {"id": "P00-S01-T002", "status": "ready", "depends_on": ["P00-S01-T001"]},
        ]
    }
    (tasks_dir / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (tasks_dir / "lifecycle-events/P00-S01-T001.json").write_text('{"task_id":"P00-S01-T001"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base P00-S01-T001"], cwd=repo, check=True)

    result = run(["bash", str(SCRIPT), "P00-S01-T002", "--json"], cwd=repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True
