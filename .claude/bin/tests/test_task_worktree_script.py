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


def test_ensure_task_worktree_cuts_pr_flow_branch_from_fresh_origin_main(tmp_path):
    if not shutil.which("git"):
        return
    repo = tmp_path / "repo"
    remote = tmp_path / "origin.git"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test"], repo)
    (repo / "scripts").mkdir()
    (repo / ".claude" / "bin").mkdir(parents=True)
    (repo / "docs" / "source-of-truth").mkdir(parents=True)
    for script_name in ["ensure-task-worktree.sh", "sync-main-before-wave.sh", "runtime-git-guard.sh"]:
        shutil.copy2(ROOT / "scripts" / script_name, repo / "scripts" / script_name)
    for py_name in ["stack_profile.py", "runtime_git_guard.py"]:
        shutil.copy2(ROOT / ".claude" / "bin" / py_name, repo / ".claude" / "bin" / py_name)
    shutil.copy2(ROOT / "scripts" / "sync_main_before_wave.py", repo / "scripts" / "sync_main_before_wave.py")
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text("profile_version: stack-profile-v1\ngit_workflow: pr-flow\n", encoding="utf-8")
    (repo / "app.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "init"], repo)
    run(["git", "init", "-q", "--bare", str(remote)], repo)
    run(["git", "remote", "add", "origin", str(remote)], repo)
    run(["git", "push", "-u", "origin", "main"], repo)
    run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], remote)

    other = tmp_path / "other"
    run(["git", "clone", str(remote), str(other)], tmp_path)
    run(["git", "config", "user.email", "test@example.com"], other)
    run(["git", "config", "user.name", "Test"], other)
    (other / "app.txt").write_text("base\nremote-main-change\n", encoding="utf-8")
    run(["git", "add", "app.txt"], other)
    run(["git", "commit", "-q", "-m", "remote main change"], other)
    run(["git", "push", "origin", "main"], other)
    remote_sha = run(["git", "rev-parse", "origin/main"], other).stdout.strip()

    wt = Path(run(["bash", "scripts/ensure-task-worktree.sh", "P00-S01-T009"], repo).stdout.strip())
    assert wt.is_dir()
    assert run(["git", "rev-parse", "HEAD"], wt).stdout.strip() == remote_sha
    assert run(["git", "rev-parse", "main"], repo).stdout.strip() == remote_sha


def test_ensure_task_worktree_new_pr_branch_starts_from_origin_main_when_local_main_is_stale(tmp_path):
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
    shutil.copy2(ROOT / "scripts" / "sync-main-before-wave.sh", repo / "scripts" / "sync-main-before-wave.sh")
    shutil.copy2(ROOT / "scripts" / "sync_main_before_wave.py", repo / "scripts" / "sync_main_before_wave.py")
    shutil.copy2(ROOT / "scripts" / "runtime-git-guard.sh", repo / "scripts" / "runtime-git-guard.sh")
    shutil.copy2(ROOT / ".claude" / "bin" / "stack_profile.py", repo / ".claude" / "bin" / "stack_profile.py")
    shutil.copy2(ROOT / ".claude" / "bin" / "runtime_git_guard.py", repo / ".claude" / "bin" / "runtime_git_guard.py")
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text("profile_version: stack-profile-v1\ngit_workflow: pr-flow\n", encoding="utf-8")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "init"], repo)

    remote = tmp_path / "origin.git"
    run(["git", "init", "-q", "--bare", str(remote)], tmp_path)
    run(["git", "remote", "add", "origin", str(remote)], repo)
    run(["git", "push", "-q", "-u", "origin", "main"], repo)
    run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], remote)

    updater = tmp_path / "updater"
    run(["git", "clone", "-q", str(remote), str(updater)], tmp_path)
    run(["git", "config", "user.email", "test@example.com"], updater)
    run(["git", "config", "user.name", "Test"], updater)
    (updater / "remote-main-only.txt").write_text("remote\n", encoding="utf-8")
    run(["git", "add", "remote-main-only.txt"], updater)
    run(["git", "commit", "-q", "-m", "remote main advance"], updater)
    run(["git", "push", "-q", "origin", "main"], updater)

    remote_main = run(["git", "rev-parse", "origin/main"], updater).stdout.strip()
    wt = Path(run(["bash", "scripts/ensure-task-worktree.sh", "P00-S01-T009"], repo).stdout.strip())

    assert (wt / "remote-main-only.txt").is_file()
    assert run(["git", "merge-base", "--is-ancestor", "origin/main", "dev/P00-S01-T009"], repo).returncode == 0
    assert run(["git", "rev-parse", "main"], repo).stdout.strip() == remote_main
