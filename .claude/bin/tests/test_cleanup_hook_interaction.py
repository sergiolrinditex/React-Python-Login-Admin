from __future__ import annotations

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest import mock

_BIN = Path(__file__).resolve().parent.parent
ROOT = Path(__file__).resolve().parents[3]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


def run(cmd: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True, **kwargs)


def test_active_worktree_cleanup_does_not_prevent_closer_subagent_stop_state(tmp_path, monkeypatch):
    """Regression for a real Claude failure shape.

    If closer removes its own task worktree before Claude fires SubagentStop,
    the hook runner may fail to spawn and runtime-state/ledger stay on tester.
    cleanup-worktrees must therefore defer the active worktree by default; the
    closer trailer can then still be captured into canonical state.
    """
    repo = tmp_path / "repo"
    wt = tmp_path / "repo-worktrees" / "P00-S01-T001"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "orchestrator-contract.json").write_text(
        (ROOT / ".claude" / "orchestrator-contract.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo / "orchestrator-state" / "tasks").mkdir(parents=True)
    registry = {
        "generated_at": "2026-05-14T00:00:00Z",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "Phase", "status": "active", "task_ids": ["P00-S01-T001"]}],
        "tasks": [{"id": "P00-S01-T001", "phase_id": "P00", "step_id": "P00-S01", "status": "verified_pending_close", "depends_on": []}],
    }
    (repo / "orchestrator-state" / "tasks" / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (repo / "orchestrator-state" / "tasks" / "runtime-state.json").write_text(json.dumps({"last_worker": "tester"}), encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "branch", "dev/P00-S01-T001"], repo)
    run(["git", "worktree", "add", str(wt), "dev/P00-S01-T001"], repo)

    cleanup = run(["bash", str(ROOT / "scripts" / "cleanup-worktrees.sh"), "--apply", "--task", "P00-S01-T001"], wt)
    assert "active_deferred=1" in cleanup.stdout
    assert wt.exists(), "active task worktree must survive until SubagentStop hooks have run"

    monkeypatch.setenv("CLAUDE_ORCHESTRATOR_ROOT", str(repo))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    import common
    import hook_capture_subagent_stop

    common._LOCK_DEPTH.clear()
    payload = json.dumps({
        "agent_type": "closer",
        "last_assistant_message": "\n".join([
            "CLAUDE_TRAILER:",
            "TASK_ID: P00-S01-T001",
            "OUTCOME: blocked",
            "NEXT_STATUS: blocked",
            "BLOCKER_REASON: pr_pending",
        ]),
    })
    with mock.patch.object(sys, "stdin", StringIO(payload)):
        assert hook_capture_subagent_stop.main() == 0

    runtime = json.loads((repo / "orchestrator-state" / "tasks" / "runtime-state.json").read_text(encoding="utf-8"))
    assert runtime["last_worker"] == "closer"
    assert runtime["last_trailer"]["outcome"] == "blocked"
    ledger_lines = (repo / "orchestrator-state" / "tasks" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line).get("event") == "subagent_stop" and json.loads(line).get("agent_type") == "closer" for line in ledger_lines)
