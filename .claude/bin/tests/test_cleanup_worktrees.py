from __future__ import annotations

import os
import subprocess
import time
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


def test_cleanup_worktrees_defers_current_task_worktree_by_default(tmp_path):
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

    assert "defer active worktree removal" in applied.stdout
    assert "active_deferred=1" in applied.stdout
    assert "removed=0" in applied.stdout
    assert wt.exists()
    assert container.exists()


def test_cleanup_worktrees_defers_active_worktree_even_when_invoked_from_root_with_claude_env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    container = tmp_path / "repo-worktrees"
    wt = container / "P00-S01-T010"

    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T010"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T010"], repo)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))

    applied = run(["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T010"], repo)

    assert "defer active worktree removal" in applied.stdout
    assert "active_deferred=1" in applied.stdout
    assert wt.exists()


def test_cleanup_worktrees_can_remove_current_task_worktree_when_explicit(tmp_path):
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

    applied = run(["bash", str(SCRIPT), "--apply", "--remove-active", "--task", "P00-S01-T001"], wt)

    assert "removed:" in applied.stdout
    assert "removed=1" in applied.stdout
    assert not wt.exists()
    assert not container.exists()


def test_cleanup_worktrees_prunes_missing_metadata_without_blocking(tmp_path):
    repo = tmp_path / "repo"
    wt = tmp_path / "wt-P00-S01-T009"

    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T009"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T009"], repo)
    # Simulate stale/prunable worktree metadata left by an external deletion.
    subprocess.run(["rm", "-rf", str(wt)], check=True)

    applied = run(["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T009"], repo)

    assert "prune missing worktree metadata" in applied.stdout
    assert "missing_pruned=1" in applied.stdout
    assert "skipped=0" in applied.stdout


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


def test_cleanup_worktrees_records_active_cleanup_request_and_deferred_helper_removes_it(tmp_path):
    repo = tmp_path / "repo"
    container = tmp_path / "repo-worktrees"
    wt = container / "P00-S01-T777"

    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T777"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T777"], repo)

    applied = subprocess.run(
        ["bash", str(SCRIPT), "--apply", "--task", "P00-S01-T777"],
        cwd=wt,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "active_deferred=1" in applied.stdout
    assert "DEFERRED_CLEANUP_COMMAND:" in applied.stdout
    req = repo / "orchestrator-state" / "tasks" / "cleanup-requests" / "P00-S01-T777.json"
    assert req.exists()
    # Deferred cleanup now waits until the task is actually closed/merged.
    # A lifecycle event is the durable signal emitted by the closer/git-add flow.
    _write_lifecycle_event(repo, "P00-S01-T777")

    env = {**os.environ, "CLAUDE_DEFERRED_CLEANUP_ASSUME_INACTIVE": "1"}
    flushed = subprocess.run(
        ["bash", str(ROOT / "scripts" / "cleanup-deferred-worktrees.sh"), "--apply", "--task", "P00-S01-T777"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "removed=1" in flushed.stdout
    assert not wt.exists()
    assert not req.exists()


def test_cleanup_deferred_helper_is_bash32_compatible():
    script = ROOT / "scripts" / "cleanup-deferred-worktrees.sh"
    text = script.read_text(encoding="utf-8")
    assert "mapfile" not in text
    result = subprocess.run(["bash", str(script), "--help"], text=True, capture_output=True, check=True)
    assert "cleanup-deferred-worktrees" in result.stdout


def _setup_repo_with_task_worktree(tmp_path, task_id: str):
    repo = tmp_path / "repo"
    container = tmp_path / "repo-worktrees"
    wt = container / task_id
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", f"dev/{task_id}"], repo)
    run(["git", "worktree", "add", str(wt), f"dev/{task_id}"], repo)
    return repo, wt


def _write_cleanup_request(repo: Path, task_id: str, wt: Path):
    req_dir = repo / "orchestrator-state" / "tasks" / "cleanup-requests"
    req_dir.mkdir(parents=True, exist_ok=True)
    req = req_dir / f"{task_id}.json"
    req.write_text(
        '{\n'
        f'  "task_id": "{task_id}",\n'
        f'  "worktree": "{wt.as_posix()}",\n'
        f'  "branch": "dev/{task_id}"\n'
        '}\n',
        encoding="utf-8",
    )
    return req


def _write_registry(repo: Path, task_id: str, status: str):
    path = repo / "orchestrator-state" / "tasks" / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"task_dag":{"mode":"explicit_dag"},"tasks":[{"id":"%s","status":"%s"}]}\n' % (task_id, status),
        encoding="utf-8",
    )


def _write_lifecycle_event(repo: Path, task_id: str):
    path = repo / "orchestrator-state" / "tasks" / "lifecycle-events" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{\n'
        '  "schema": "orquestador.lifecycle-event.v1",\n'
        f'  "task_id": "{task_id}",\n'
        '  "agent_type": "closer",\n'
        '  "outcome": "committed",\n'
        '  "next_status": "done"\n'
        '}\n',
        encoding="utf-8",
    )


def test_deferred_cleanup_does_not_warn_or_delete_task_that_is_not_closed(tmp_path):
    task_id = "P00-S01-T901"
    repo, wt = _setup_repo_with_task_worktree(tmp_path, task_id)
    req = _write_cleanup_request(repo, task_id, wt)
    _write_registry(repo, task_id, "ready")

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "cleanup-deferred-worktrees.sh"), "--apply", "--task", task_id],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "pending=1" in result.stdout
    assert wt.exists()
    assert req.exists()


def test_deferred_cleanup_removes_when_lifecycle_event_proves_closed(tmp_path):
    task_id = "P00-S01-T902"
    repo, wt = _setup_repo_with_task_worktree(tmp_path, task_id)
    req = _write_cleanup_request(repo, task_id, wt)
    _write_registry(repo, task_id, "ready")
    _write_lifecycle_event(repo, task_id)

    env = {**os.environ, "CLAUDE_DEFERRED_CLEANUP_ASSUME_INACTIVE": "1"}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "cleanup-deferred-worktrees.sh"), "--apply", "--task", task_id],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "removed=1" in result.stdout
    assert not wt.exists()
    assert not req.exists()


def test_deferred_cleanup_dirty_closed_task_reports_dirty_paths(tmp_path):
    task_id = "P00-S01-T903"
    repo, wt = _setup_repo_with_task_worktree(tmp_path, task_id)
    _write_cleanup_request(repo, task_id, wt)
    _write_registry(repo, task_id, "done")
    (wt / "uncommitted.txt").write_text("not committed\n", encoding="utf-8")

    env = {**os.environ, "CLAUDE_DEFERRED_CLEANUP_ASSUME_INACTIVE": "1"}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "cleanup-deferred-worktrees.sh"), "--apply", "--task", task_id, "--quiet"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 3
    assert wt.exists()
    assert "skip dirty:" in result.stderr
    assert "DIRTY_STATUS_BEGIN" in result.stderr
    assert "uncommitted.txt" in result.stderr

CLOSED_CLEANUP = ROOT / "scripts" / "cleanup-closed-task-worktrees.sh"


def test_cleanup_closed_task_worktrees_removes_done_clean_worktree_and_branch_without_request(tmp_path):
    task_id = "P04-S03-T001"
    repo, wt = _setup_repo_with_task_worktree(tmp_path, task_id)
    _write_registry(repo, task_id, "done")

    result = subprocess.run(
        ["bash", str(CLOSED_CLEANUP), "--apply", "--task", task_id],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert not wt.exists()
    assert "removed closed worktree" in result.stdout
    assert "deleted closed task branch: dev/P04-S03-T001" in result.stdout
    show = subprocess.run(["git", "show-ref", "--verify", f"refs/heads/dev/{task_id}"], cwd=repo)
    assert show.returncode != 0


def test_cleanup_closed_task_worktrees_deletes_orphan_branch_for_done_task(tmp_path):
    task_id = "P04-S03-T002"
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run(["git", "add", "README.md"], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", f"dev/{task_id}"], repo)
    _write_lifecycle_event(repo, task_id)

    result = subprocess.run(
        ["bash", str(CLOSED_CLEANUP), "--apply", "--task", task_id],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "deleted closed task branch: dev/P04-S03-T002" in result.stdout
    show = subprocess.run(["git", "show-ref", "--verify", f"refs/heads/dev/{task_id}"], cwd=repo)
    assert show.returncode != 0


def test_cleanup_closed_task_worktrees_does_not_remove_ready_task(tmp_path):
    task_id = "P04-S03-T003"
    repo, wt = _setup_repo_with_task_worktree(tmp_path, task_id)
    _write_registry(repo, task_id, "ready")

    result = subprocess.run(
        ["bash", str(CLOSED_CLEANUP), "--apply", "--task", task_id],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert wt.exists()
    show = subprocess.run(["git", "show-ref", "--verify", f"refs/heads/dev/{task_id}"], cwd=repo)
    assert show.returncode == 0
    assert "pending task=" in result.stdout


def test_cleanup_closed_task_worktrees_skips_dirty_done_worktree(tmp_path):
    task_id = "P04-S03-T004"
    repo, wt = _setup_repo_with_task_worktree(tmp_path, task_id)
    _write_registry(repo, task_id, "done")
    (wt / "dirty.txt").write_text("keep me\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(CLOSED_CLEANUP), "--apply", "--task", task_id, "--verbose"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 3
    assert wt.exists()
    assert "skip dirty closed worktree" in result.stderr
    show = subprocess.run(["git", "show-ref", "--verify", f"refs/heads/dev/{task_id}"], cwd=repo)
    assert show.returncode == 0
