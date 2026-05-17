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


def _init_repo_with_user(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)


def test_git_add_slice_blocks_staged_product_deletions_not_in_delete_set(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    (canonical / "orchestrator-state/tasks").mkdir(parents=True)
    registry = {"tasks": [{"id": "P00-S01-T001", "write_set": ["app/**"]}]}
    (canonical / "orchestrator-state/tasks/registry.json").write_text(json.dumps(registry), encoding="utf-8")

    _init_repo_with_user(workspace)
    (workspace / "app").mkdir()
    (workspace / "app/authRepository.ts").write_text("export const auth = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app/authRepository.ts"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=workspace, check=True)
    (workspace / "app/authRepository.ts").unlink()

    env = {**os.environ, "CLAUDE_ORCHESTRATOR_ROOT": str(canonical)}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/git-add-slice.sh"), "P00-S01-T001"],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "staged file deletion" in result.stderr
    assert "app/authRepository.ts" in result.stderr
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=D"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout.splitlines()
    assert "app/authRepository.ts" not in staged


def test_git_add_slice_allows_explicit_delete_set(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    (canonical / "orchestrator-state/tasks").mkdir(parents=True)
    registry = {"tasks": [{"id": "P00-S01-T001", "write_set": ["app/**"], "delete_set": ["app/legacy.ts"]}]}
    (canonical / "orchestrator-state/tasks/registry.json").write_text(json.dumps(registry), encoding="utf-8")

    _init_repo_with_user(workspace)
    (workspace / "app").mkdir()
    (workspace / "app/legacy.ts").write_text("export const old = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app/legacy.ts"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=workspace, check=True)
    (workspace / "app/legacy.ts").unlink()

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
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=D"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout.splitlines()
    assert staged == ["app/legacy.ts"]


def test_git_add_slice_blocks_destructive_shared_risk_edit_without_declaration(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    (canonical / "orchestrator-state/tasks").mkdir(parents=True)
    registry = {"tasks": [{"id": "P00-S01-T001", "write_set": ["src/**"]}]}
    (canonical / "orchestrator-state/tasks/registry.json").write_text(json.dumps(registry), encoding="utf-8")

    _init_repo_with_user(workspace)
    shared = workspace / "src/features/auth/errors.ts"
    shared.parent.mkdir(parents=True)
    shared.write_text("\n".join([f"export class AuthError{i} extends Error {{}}" for i in range(40)]) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/features/auth/errors.ts"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=workspace, check=True)
    shared.write_text("export class AuthError0 extends Error {}\n", encoding="utf-8")

    env = {**os.environ, "CLAUDE_ORCHESTRATOR_ROOT": str(canonical)}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/git-add-slice.sh"), "P00-S01-T001"],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "destructive edit" in result.stderr
    assert "src/features/auth/errors.ts" in result.stderr
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout.splitlines()
    assert "src/features/auth/errors.ts" not in staged


def test_git_add_slice_allows_destructive_shared_risk_edit_when_declared(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    (canonical / "orchestrator-state/tasks").mkdir(parents=True)
    registry = {"tasks": [{"id": "P00-S01-T001", "write_set": ["src/**"], "destructive_edit_set": ["src/features/auth/errors.ts"]}]}
    (canonical / "orchestrator-state/tasks/registry.json").write_text(json.dumps(registry), encoding="utf-8")

    _init_repo_with_user(workspace)
    shared = workspace / "src/features/auth/errors.ts"
    shared.parent.mkdir(parents=True)
    shared.write_text("\n".join([f"export class AuthError{i} extends Error {{}}" for i in range(40)]) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/features/auth/errors.ts"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=workspace, check=True)
    shared.write_text("export class AuthError0 extends Error {}\n", encoding="utf-8")

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
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout.splitlines()
    assert "src/features/auth/errors.ts" in staged
