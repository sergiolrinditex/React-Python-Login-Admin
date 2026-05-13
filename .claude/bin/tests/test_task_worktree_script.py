from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True, timeout=30)


def test_ensure_task_worktree_creates_and_checks_pr_flow_worktree(tmp_path):
    if not shutil.which("git"):
        return
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test"], repo)
    (repo / "scripts").mkdir()
    (repo / ".claude" / "bin").mkdir(parents=True)
    (repo / "docs" / "source-of-truth").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "ensure-task-worktree.sh", repo / "scripts" / "ensure-task-worktree.sh")
    shutil.copy2(ROOT / ".claude" / "bin" / "stack_profile.py", repo / ".claude" / "bin" / "stack_profile.py")
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text("profile_version: stack-profile-v1\ngit_workflow: pr-flow\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "init"], repo)

    result = run(["bash", "scripts/ensure-task-worktree.sh", "P00-S01-T001"], repo)
    wt = Path(result.stdout.strip())
    assert wt.is_dir()
    assert wt.name == "P00-S01-T001"
    assert run(["git", "branch", "--show-current"], wt).stdout.strip() == "dev/P00-S01-T001"
    check = run(["bash", "scripts/ensure-task-worktree.sh", "--check-current", "P00-S01-T001"], wt)
    assert "TASK_WORKTREE_READY: yes" in check.stdout


def test_ensure_task_worktree_rejects_main_for_pr_flow(tmp_path):
    if not shutil.which("git"):
        return
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test"], repo)
    (repo / "scripts").mkdir()
    (repo / ".claude" / "bin").mkdir(parents=True)
    (repo / "docs" / "source-of-truth").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "ensure-task-worktree.sh", repo / "scripts" / "ensure-task-worktree.sh")
    shutil.copy2(ROOT / ".claude" / "bin" / "stack_profile.py", repo / ".claude" / "bin" / "stack_profile.py")
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text("profile_version: stack-profile-v1\ngit_workflow: pr-flow\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "init"], repo)

    result = subprocess.run(["bash", "scripts/ensure-task-worktree.sh", "--check-current", "P00-S01-T001"], cwd=repo, text=True, capture_output=True, timeout=30)
    assert result.returncode == 2
    assert "requires a task branch/worktree" in result.stdout


def test_ensure_task_worktree_from_task_worktree_reuses_canonical_main_root(tmp_path):
    if not shutil.which("git"):
        return
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test"], repo)
    (repo / "scripts").mkdir()
    (repo / ".claude" / "bin").mkdir(parents=True)
    (repo / "docs" / "source-of-truth").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "ensure-task-worktree.sh", repo / "scripts" / "ensure-task-worktree.sh")
    shutil.copy2(ROOT / ".claude" / "bin" / "stack_profile.py", repo / ".claude" / "bin" / "stack_profile.py")
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text("profile_version: stack-profile-v1\ngit_workflow: pr-flow\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "init"], repo)

    wt1 = Path(run(["bash", "scripts/ensure-task-worktree.sh", "P00-S01-T001"], repo).stdout.strip())
    assert wt1.is_dir()
    root_from_wt = run(["bash", "scripts/ensure-task-worktree.sh", "--print-root"], wt1).stdout.strip()
    assert Path(root_from_wt) == repo

    wt2 = Path(run(["bash", "scripts/ensure-task-worktree.sh", "P00-S01-T002"], wt1).stdout.strip())
    assert wt2 == repo.parent / "repo-worktrees" / "P00-S01-T002"
    assert wt2.is_dir()
    assert "P00-S01-T001-worktrees" not in str(wt2)
    assert run(["git", "branch", "--show-current"], wt2).stdout.strip() == "dev/P00-S01-T002"
