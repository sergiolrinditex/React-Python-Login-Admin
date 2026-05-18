from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SYNC = ROOT / "scripts" / "sync_main_before_wave.py"
ZOMBIE = ROOT / "scripts" / "cleanup_zombie_task_worktrees.py"
RUNTIME_GUARD_SH = ROOT / "scripts" / "runtime-git-guard.sh"
RUNTIME_GUARD_PY = ROOT / ".claude" / "bin" / "runtime_git_guard.py"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-b", "main"], path)
    run(["git", "config", "user.email", "test@example.com"], path)
    run(["git", "config", "user.name", "Test User"], path)
    (path / "README.md").write_text("init\n", encoding="utf-8")
    run(["git", "add", "README.md"], path)
    run(["git", "commit", "-m", "init"], path)


def install_runtime_guard(repo: Path) -> None:
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "bin").mkdir(parents=True, exist_ok=True)
    (repo / "scripts" / "runtime-git-guard.sh").write_text(RUNTIME_GUARD_SH.read_text(encoding="utf-8"), encoding="utf-8")
    (repo / ".claude" / "bin" / "runtime_git_guard.py").write_text(RUNTIME_GUARD_PY.read_text(encoding="utf-8"), encoding="utf-8")


def test_sync_main_before_wave_fast_forwards_to_origin_main(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    run(["git", "init", "--bare", str(remote)], tmp_path)
    run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], remote)
    repo = tmp_path / "repo"
    init_repo(repo)
    install_runtime_guard(repo)
    run(["git", "add", "scripts", ".claude"], repo)
    run(["git", "commit", "-m", "add runtime guard"], repo)
    run(["git", "remote", "add", "origin", str(remote)], repo)
    run(["git", "push", "-u", "origin", "main"], repo)

    other = tmp_path / "other"
    run(["git", "clone", str(remote), str(other)], tmp_path)
    run(["git", "config", "user.email", "test@example.com"], other)
    run(["git", "config", "user.name", "Test User"], other)
    (other / "remote.txt").write_text("remote\n", encoding="utf-8")
    run(["git", "add", "remote.txt"], other)
    run(["git", "commit", "-m", "remote"], other)
    run(["git", "push", "origin", "main"], other)

    result = run(["python3", "-B", "-S", str(SYNC), "--apply"], repo)
    assert "fast-forwarded" in result.stdout
    assert (repo / "remote.txt").exists()
    assert run(["git", "rev-parse", "main"], repo).stdout == run(["git", "rev-parse", "origin/main"], repo).stdout


def test_sync_main_before_wave_blocks_non_runtime_dirty(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    run(["git", "init", "--bare", str(remote)], tmp_path)
    run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], remote)
    repo = tmp_path / "repo"
    init_repo(repo)
    install_runtime_guard(repo)
    run(["git", "add", "scripts", ".claude"], repo)
    run(["git", "commit", "-m", "add runtime guard"], repo)
    run(["git", "remote", "add", "origin", str(remote)], repo)
    run(["git", "push", "-u", "origin", "main"], repo)
    (repo / "docs").mkdir()
    (repo / "docs" / "source.txt").write_text("dirty\n", encoding="utf-8")

    result = run(["python3", "-B", "-S", str(SYNC), "--apply"], repo, check=False)
    assert result.returncode == 3
    assert "DIRTY_NON_RUNTIME" in result.stderr


def test_cleanup_zombie_removes_clean_patch_equivalent_task_worktree_and_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    wt = tmp_path / "repo-worktrees" / "P00-S01-T001"
    run(["git", "branch", "dev/P00-S01-T001"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T001"], repo)

    result = run(["python3", "-B", "-S", str(ZOMBIE), "--apply", "--verbose"], repo)
    assert "removed zombie task worktree" in result.stdout
    assert not wt.exists()
    branches = run(["git", "branch", "--format=%(refname:short)"], repo).stdout.splitlines()
    assert "dev/P00-S01-T001" not in branches


def test_cleanup_zombie_skips_live_registry_task(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    wt = tmp_path / "repo-worktrees" / "P00-S01-T002"
    run(["git", "branch", "dev/P00-S01-T002"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T002"], repo)
    state = repo / "orchestrator-state" / "tasks"
    state.mkdir(parents=True)
    (state / "registry.json").write_text(
        json.dumps({"tasks": [{"id": "P00-S01-T002", "status": "in_progress"}]}),
        encoding="utf-8",
    )

    result = run(["python3", "-B", "-S", str(ZOMBIE), "--apply", "--verbose"], repo)
    assert "skip live task worktree" in result.stdout
    assert wt.exists()
    branches = run(["git", "branch", "--format=%(refname:short)"], repo).stdout.splitlines()
    assert "dev/P00-S01-T002" in branches


def test_cleanup_zombie_skips_unique_patch_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    run(["git", "checkout", "-b", "dev/P00-S01-T003"], repo)
    (repo / "feature.txt").write_text("unique\n", encoding="utf-8")
    run(["git", "add", "feature.txt"], repo)
    run(["git", "commit", "-m", "unique"], repo)
    run(["git", "checkout", "main"], repo)

    result = run(["python3", "-B", "-S", str(ZOMBIE), "--apply", "--verbose"], repo)
    assert "skip local branch with unique patches" in result.stdout
    branches = run(["git", "branch", "--format=%(refname:short)"], repo).stdout.splitlines()
    assert "dev/P00-S01-T003" in branches
