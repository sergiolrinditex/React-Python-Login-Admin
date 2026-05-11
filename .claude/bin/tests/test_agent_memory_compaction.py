from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "compact-agent-memory.py"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "scripts").mkdir()
    (root / "scripts" / "compact-agent-memory.py").write_bytes(SCRIPT.read_bytes())
    (root / ".claude" / "agents").mkdir(parents=True)
    (root / ".claude" / "agents" / "developer.md").write_text("static developer prompt\n", encoding="utf-8")
    memdir = root / "orchestrator-state" / "agent-memory" / "developer"
    memdir.mkdir(parents=True)
    lines = ["# Developer historical memory", "", "## Decisions"]
    for i in range(230):
        lines.append(
            f"- D{i}: DAG explicit_dag invariant, bootstrap --refresh, Write set, docker-compose.yml, OUTCOME success, NEXT_STATUS validator_tester_pending"
        )
    (memdir / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def run_compact(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-S", "scripts/compact-agent-memory.py", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_compact_agent_memory_dry_run_does_not_mutate(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    memory = root / "orchestrator-state" / "agent-memory" / "developer" / "MEMORY.md"
    agent_prompt = root / ".claude" / "agents" / "developer.md"
    before_memory = memory.read_bytes()
    before_agent = agent_prompt.read_bytes()

    result = run_compact(root, "--all", "--threshold-lines", "200", "--timestamp", "2026-05-09-120000")

    assert result.returncode == 0, result.stderr
    assert "mode: dry-run" in result.stdout
    assert "COMPACT developer" in result.stdout
    assert memory.read_bytes() == before_memory
    assert agent_prompt.read_bytes() == before_agent
    assert not (memory.parent / "archive").exists()


def test_compact_agent_memory_apply_archives_full_before_compacting(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    memory = root / "orchestrator-state" / "agent-memory" / "developer" / "MEMORY.md"
    agent_prompt = root / ".claude" / "agents" / "developer.md"
    before_memory = memory.read_bytes()
    before_agent = agent_prompt.read_bytes()
    before_sha = sha256_bytes(before_memory)

    result = run_compact(root, "--agent", "developer", "--apply", "--threshold-lines", "200", "--timestamp", "2026-05-09-120000")

    assert result.returncode == 0, result.stderr
    archive = memory.parent / "archive" / "MEMORY.full.2026-05-09-120000.md"
    assert archive.is_file()
    assert archive.read_bytes() == before_memory
    assert agent_prompt.read_bytes() == before_agent

    compacted = memory.read_text(encoding="utf-8")
    assert "Compact operational memory. No history was deleted." in compacted
    assert "orchestrator-state/agent-memory/developer/archive/MEMORY.full.2026-05-09-120000.md" in compacted
    assert before_sha in compacted
    assert "Production work is DAG-only" in compacted
    assert "docker-compose.yml" in compacted
    assert ".claude/orchestrator-contract.json" in compacted
    assert len(compacted.splitlines()) < len(before_memory.decode("utf-8").splitlines())
