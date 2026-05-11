from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESET = ROOT / ".claude" / "bin" / "reset_orchestrator_state.py"


def _write(path: Path, text: str = "filled\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_reset_accepts_modern_source_of_truth_and_cleans_derived_state(tmp_path: Path) -> None:
    project = tmp_path
    (project / ".claude").mkdir()
    sot = project / "docs" / "source-of-truth"
    _write(sot / "instrucciones.md")
    _write(sot / "APP_TECHNICAL_GUIDE.md")
    _write(sot / "APP_IMPLEMENTATION_CHECKLIST.md")
    _write(sot / "UX_CONTRACT.md")
    _write(sot / "STACK_PROFILE.yaml", "profile_version: stack-profile-v1\n")

    tasks = project / "orchestrator-state" / "tasks"
    memory = project / "orchestrator-state" / "memory"
    _write(tasks / "registry.json", "{}\n")
    _write(tasks / "runtime-state.json", "{}\n")
    _write(tasks / "task-dag.json", "{}\n")
    _write(tasks / "work-items" / "old.md")
    _write(memory / "archive" / "old" / "handoff.md")
    _write(project / "orchestrator-state" / "stale.lock")

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["PYTHONPATH"] = str(ROOT / ".claude" / "bin") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-B", "-S", str(RESET)],
        cwd=project,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (sot / "UX_CONTRACT.md").is_file()
    assert (sot / "STACK_PROFILE.yaml").is_file()
    assert not (tasks / "registry.json").exists()
    assert not (tasks / "runtime-state.json").exists()
    assert not (tasks / "task-dag.json").exists()
    assert not (tasks / "work-items" / "old.md").exists()
    assert not (memory / "archive").exists()
    assert not (project / "orchestrator-state" / "stale.lock").exists()


def test_reset_accepts_empty_source_of_truth_for_fresh_orchestrator_checkout(tmp_path: Path) -> None:
    project = tmp_path
    (project / ".claude").mkdir()
    (project / "docs" / "source-of-truth").mkdir(parents=True)
    _write(project / "orchestrator-state" / "tasks" / "registry.json", "{}\n")

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["PYTHONPATH"] = str(ROOT / ".claude" / "bin") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-B", "-S", str(RESET)],
        cwd=project,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert not (project / "orchestrator-state" / "tasks" / "registry.json").exists()
    assert (project / "docs" / "source-of-truth").is_dir()
