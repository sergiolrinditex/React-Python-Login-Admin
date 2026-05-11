from __future__ import annotations

import json
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]


def test_bash_posttooluse_writes_runtime_ledger_not_canonical_ledger(tmp_project, monkeypatch):
    import hook_update_ledger

    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "./scripts/check-task-dag.sh --strict"}})
    with mock.patch.object(sys, "stdin", StringIO(payload)):
        assert hook_update_ledger.main() == 0

    canonical = tmp_project / "orchestrator-state" / "tasks" / "ledger.jsonl"
    bash_ledger = tmp_project / "orchestrator-state" / "tasks" / "bash-ledger.jsonl"
    assert not canonical.exists()
    line = bash_ledger.read_text(encoding="utf-8").splitlines()[-1]
    record = json.loads(line)
    assert record["tool_name"] == "Bash"
    assert record["runtime_only"] is True
    assert "check-task-dag" in record["command"]


def test_write_posttooluse_still_writes_canonical_ledger(tmp_project):
    import hook_update_ledger

    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "frontend/src/app/App.tsx"}})
    with mock.patch.object(sys, "stdin", StringIO(payload)):
        assert hook_update_ledger.main() == 0

    canonical = tmp_project / "orchestrator-state" / "tasks" / "ledger.jsonl"
    bash_ledger = tmp_project / "orchestrator-state" / "tasks" / "bash-ledger.jsonl"
    assert not bash_ledger.exists()
    record = json.loads(canonical.read_text(encoding="utf-8").splitlines()[-1])
    assert record["tool_name"] == "Write"
    assert record["file_path"] == "frontend/src/app/App.tsx"


def test_bash_runtime_ledger_is_git_ignored_and_does_not_dirty_repo(tmp_path, monkeypatch):
    if not shutil.which("git"):
        return
    repo = tmp_path / "repo"
    (repo / "orchestrator-state" / "tasks").mkdir(parents=True)
    (repo / ".gitignore").write_text("orchestrator-state/tasks/bash-ledger.jsonl\norchestrator-state/**/*.lock\n", encoding="utf-8")
    (repo / "orchestrator-state" / "tasks" / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))

    import common
    import hook_update_ledger
    common._LOCK_DEPTH.clear()
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "./scripts/git-workflow.sh"}})
    with mock.patch.object(sys, "stdin", StringIO(payload)):
        assert hook_update_ledger.main() == 0

    assert (repo / "orchestrator-state" / "tasks" / "bash-ledger.jsonl").exists()
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, text=True, capture_output=True, check=True)
    assert "bash-ledger.jsonl" not in status.stdout
    assert status.stdout == ""
