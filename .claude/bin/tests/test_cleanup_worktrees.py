from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "cleanup-worktrees.sh"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def test_cleanup_worktrees_dry_run_and_apply(tmp_path):
    repo = tmp_path / "repo"
    wt = tmp_path / "wt-P00-S01-T001"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T001-test"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T001-test"], repo)

    dry = run(["bash", str(SCRIPT), "--task", "P00-S01-T001"], repo)
    assert "would remove:" in dry.stdout
    assert wt.exists()

    applied = run(["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T001"], repo)
    assert "removed:" in applied.stdout
    assert "removed=1" in applied.stdout
    assert not wt.exists()


def test_cleanup_worktrees_noops_outside_git(tmp_path):
    result = subprocess.run(["bash", str(SCRIPT), "--verbose"], cwd=tmp_path, text=True, capture_output=True, check=True)
    assert "git_repository=no" in result.stdout
    assert "matched=0" in result.stdout
