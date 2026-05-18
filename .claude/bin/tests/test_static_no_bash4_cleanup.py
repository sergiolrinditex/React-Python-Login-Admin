import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_cleanup_deferred_worktrees_is_bash3_compatible() -> None:
    text = (ROOT / "scripts" / "cleanup-deferred-worktrees.sh").read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    assert "mapfile" not in code
    assert "readarray" not in code
    assert "sort -z" not in code
    assert "REQUESTS[@]" not in code
    assert "REQUESTS=()" not in code


def test_cleanup_deferred_empty_request_dir_is_quiet_success(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, text=True, capture_output=True, check=True)
    (repo / "orchestrator-state" / "tasks" / "cleanup-requests").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "cleanup-deferred-worktrees.sh"), "--apply", "--quiet"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout == ""
    assert result.stderr == ""


def test_cleanup_deferred_missing_task_request_is_quiet_success(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, text=True, capture_output=True, check=True)
    (repo / "orchestrator-state" / "tasks" / "cleanup-requests").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "cleanup-deferred-worktrees.sh"), "--apply", "--quiet", "--task", "P99-S99-T999"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout == ""
    assert result.stderr == ""


def test_cleanup_loop_is_bash3_compatible() -> None:
    text = (ROOT / "scripts" / "cleanup-deferred-worktrees-loop.sh").read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    assert "mapfile" not in code
    assert "readarray" not in code
    assert "sort -z" not in code
    assert "[@]" not in code


def test_critical_git_and_mcp_shell_paths_avoid_empty_array_expansion() -> None:
    files = [
        ROOT / ".claude" / "git-workflows" / "pr-flow.sh",
        ROOT / "scripts" / "git-workflow.sh",
        ROOT / "scripts" / "git-add-slice.sh",
        ROOT / "scripts" / "slice-clean.sh",
        ROOT / ".claude" / "enforcers" / "design_tokens_v1.sh",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "merge_author_args[@]" not in combined
    assert "late_paths[@]" not in combined
    assert "SLICE_PATHS[@]" not in combined
    assert "prune_args[@]" not in combined
    assert "THEME_ARG[@]" not in combined
    assert "THEME_ARG=()" not in combined
