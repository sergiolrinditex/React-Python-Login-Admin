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


def test_cleanup_worktrees_removes_empty_container_dir(tmp_path):
    """Tras borrar la última slice de la wave, el directorio padre <repo>-worktrees/
    debe quedar vacío y eliminarse para no dejar carpetas huérfanas al lado del repo."""
    repo = tmp_path / "repo"
    container = tmp_path / "repo-worktrees"  # convención: <root>-worktrees al lado
    container.mkdir()
    wt = container / "P00-S01-T001"

    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T001"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T001"], repo)

    assert wt.exists() and container.exists()

    applied = run(["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T001"], repo)
    assert "removed:" in applied.stdout
    assert not wt.exists()
    # NUEVO: contenedor vacío debe haberse eliminado también
    assert not container.exists(), f"container should be removed when empty: {applied.stdout}"
    assert "removed empty container" in applied.stdout


def test_cleanup_worktrees_keeps_container_when_not_empty(tmp_path):
    """Si tras un --task X queda otro worktree en el contenedor, NO se borra el padre."""
    repo = tmp_path / "repo"
    container = tmp_path / "repo-worktrees"
    container.mkdir()
    wt_a = container / "P00-S01-T001"
    wt_b = container / "P00-S01-T002"

    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T001"], repo)
    run(["git", "branch", "dev/P00-S01-T002"], repo)
    run(["git", "worktree", "add", str(wt_a), "dev/P00-S01-T001"], repo)
    run(["git", "worktree", "add", str(wt_b), "dev/P00-S01-T002"], repo)

    # Borramos solo el A
    applied = run(["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T001"], repo)
    assert not wt_a.exists()
    # B sigue ahí, por tanto el contenedor NO se borra
    assert wt_b.exists()
    assert container.exists(), "container must remain while other worktrees live in it"
    assert "removed empty container" not in applied.stdout


def test_cleanup_worktrees_can_remove_current_task_worktree(tmp_path):
    repo = tmp_path / "repo"
    container = tmp_path / "repo-worktrees"
    wt = container / "P00-S01-T001"

    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T001"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T001"], repo)

    applied = run(["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T001"], wt)

    assert "removed:" in applied.stdout
    assert "removed=1" in applied.stdout
    assert not wt.exists()
    assert not container.exists()


def test_cleanup_worktrees_deletes_task_branch_after_squash_merge_shape(tmp_path):
    """PR squash merges do not make feature tip an ancestor of main.
    A scoped cleanup after successful pr-flow should still remove the local task branch.
    """
    repo = tmp_path / "repo"
    wt = tmp_path / "wt-P00-S01-T003"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "feature/P00-S01-T003"], repo)
    run(["git", "worktree", "add", str(wt), "feature/P00-S01-T003"], repo)
    (wt / "feature.txt").write_text("feature\n", encoding="utf-8")
    run(["git", "add", "feature.txt"], wt)
    run(["git", "commit", "-m", "feat: task"], wt)

    # Simulate GitHub squash merge on main: same content, different commit SHA,
    # so feature/P00-S01-T003 is not an ancestor of main.
    run(["git", "checkout", "main"], repo)
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    run(["git", "add", "feature.txt"], repo)
    run(["git", "commit", "-m", "squash merge PR"], repo)
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", "feature/P00-S01-T003", "main"], cwd=repo)
    assert anc.returncode != 0

    applied = run(["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T003"], repo)

    assert "removed:" in applied.stdout
    assert "deleted local branch: feature/P00-S01-T003" in applied.stdout
    show = subprocess.run(["git", "show-ref", "--verify", "refs/heads/feature/P00-S01-T003"], cwd=repo)
    assert show.returncode != 0
