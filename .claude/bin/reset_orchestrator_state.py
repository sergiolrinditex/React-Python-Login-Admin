#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from common import agent_memory_dir, memory_dir, project_root, state_dir, tasks_dir

ROOT = project_root()
SOT = ROOT / "docs" / "source-of-truth"
TEMPLATE_MARKERS = re.compile(
    r">>>\s*MODELO:|📋\s*SI APLICA|\{\{[^}]+\}\}"
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_source_of_truth() -> None:
    if not (ROOT / ".claude").is_dir():
        fail(".claude/ not found. Run from a valid project checkout.")
    if not SOT.is_dir():
        fail("docs/source-of-truth/ not found.")

    md_files = sorted(p for p in SOT.glob("*.md") if not p.name.endswith(".template.md"))
    if list(SOT.glob("*.template.md")):
        fail("Template files are not allowed inside docs/source-of-truth/.")

    has_modern_stack = (SOT / "STACK_PROFILE.yaml").is_file()
    has_modern_ux = (SOT / "UX_CONTRACT.md").is_file()

    if not (SOT / "instrucciones.md").is_file():
        fail("Missing docs/source-of-truth/instrucciones.md.")
    if len(list(SOT.glob("*_TECHNICAL_GUIDE.md"))) != 1:
        fail("Expected exactly 1 *_TECHNICAL_GUIDE.md in docs/source-of-truth/.")
    if len(list(SOT.glob("*_IMPLEMENTATION_CHECKLIST.md"))) != 1:
        fail("Expected exactly 1 *_IMPLEMENTATION_CHECKLIST.md in docs/source-of-truth/.")

    # Modern AnyStack projects use the 5-file source-of-truth pack:
    # instrucciones.md + technical guide + implementation checklist +
    # UX_CONTRACT.md + STACK_PROFILE.yaml. Keep accepting the old 3-md
    # contract for legacy projects, but do not reject current templates.
    if has_modern_stack or has_modern_ux:
        if not has_modern_stack:
            fail("Missing docs/source-of-truth/STACK_PROFILE.yaml.")
        if not has_modern_ux:
            fail("Missing docs/source-of-truth/UX_CONTRACT.md.")
        if len(md_files) != 4:
            fail(f"docs/source-of-truth modern pack must contain exactly 4 filled .md files plus STACK_PROFILE.yaml; found {len(md_files)} .md files.")
    elif len(md_files) != 3:
        fail(f"docs/source-of-truth legacy pack must contain exactly 3 filled .md files; found {len(md_files)}.")

    for path in md_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if TEMPLATE_MARKERS.search(text):
            fail(f"{path.relative_to(ROOT)} still contains template markers.")


def recreate_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").touch()


def unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def main() -> int:
    validate_source_of_truth()
    print("==> Cleaning derived orchestrator state. Source-of-truth docs are preserved.")

    for pattern in ("*.lock", "**/*.lock"):
        for lock in state_dir().glob(pattern):
            if lock.is_file():
                unlink(lock)

    unlink(state_dir() / "hook-errors.log")
    recreate_dir(tasks_dir())
    for sub in ["task-packs", "follow-ups", "source-doc-patches", "work-items", "phases", "handoffs", "evidence", "reports", "journey-handoffs"]:
        d = tasks_dir() / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()
    for name in [
        "registry.json",
        "runtime-state.json",
        "ledger.jsonl",
        "task-dag.json",
        "task-dag.md",
        "execution-graph.json",
        "api-contracts.json",
        "stack-profile.json",
        "ux-contract.md",
    ]:
        unlink(tasks_dir() / name)

    # Manual agent memory is preserved across app resets on purpose. It carries
    # useful Reflexion-style lessons between slices and future apps. Create the
    # root if missing, but do not delete it.
    agent_memory_dir().mkdir(parents=True, exist_ok=True)
    shutil.rmtree(state_dir() / "worktrees", ignore_errors=True)
    dev_logs = state_dir() / "dev-logs"
    shutil.rmtree(dev_logs, ignore_errors=True)
    dev_logs.mkdir(parents=True, exist_ok=True)
    (dev_logs / ".gitkeep").touch()

    memory = memory_dir()
    memory.mkdir(parents=True, exist_ok=True)
    for name in [
        "PROGRESS.md",
        "decisions.md",
        "risk-register.md",
        "project-brief.md",
        "architecture-contract.md",
        "source-manifest.json",
        "execution-graph.json",
        "task-dag.json",
        "task-dag.md",
        "stack-profile.json",
        "ux-contract.md",
        "active-phase.json",
        "active-phase.md",
        "active-task.json",
        "active-task.md",
    ]:
        unlink(memory / name)
    shutil.rmtree(memory / "official-doc-notes", ignore_errors=True)
    shutil.rmtree(memory / "archive", ignore_errors=True)

    for path in [
        ROOT / "app" / "build",
        ROOT / "app" / ".dart_tool",
        ROOT / "scripts" / "__pycache__",
    ]:
        shutil.rmtree(path, ignore_errors=True)

    print("==> Reset complete.")
    print("Next:")
    print("  python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh")
    print("  ./scripts/check-task-dag.sh --strict")
    print("  ./scripts/check-journey-matrix.sh --strict")
    print("  ./scripts/check-wiring-contract.sh --strict --require-new-template-columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
