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

    has_any_pack_file = bool(md_files) or (SOT / "STACK_PROFILE.yaml").is_file()
    if not has_any_pack_file:
        # A fresh orchestrator checkout intentionally has no built app yet. Resetting
        # derived state must still work before the user generates the five-file pack
        # from docs/templates/.
        return

    has_modern_stack = (SOT / "STACK_PROFILE.yaml").is_file()
    has_modern_ux = (SOT / "UX_CONTRACT.md").is_file()

    if not (SOT / "instrucciones.md").is_file():
        fail("Missing docs/source-of-truth/instrucciones.md.")
    if len(list(SOT.glob("*_TECHNICAL_GUIDE.md"))) != 1:
        fail("Expected exactly 1 *_TECHNICAL_GUIDE.md in docs/source-of-truth/.")
    if len(list(SOT.glob("*_IMPLEMENTATION_CHECKLIST.md"))) != 1:
        fail("Expected exactly 1 *_IMPLEMENTATION_CHECKLIST.md in docs/source-of-truth/.")
    if not has_modern_stack:
        fail("Missing docs/source-of-truth/STACK_PROFILE.yaml.")
    if not has_modern_ux:
        fail("Missing docs/source-of-truth/UX_CONTRACT.md.")
    if len(md_files) != 4:
        fail(f"docs/source-of-truth modern pack must contain exactly 4 filled .md files plus STACK_PROFILE.yaml; found {len(md_files)} .md files.")

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


def source_of_truth_is_empty() -> bool:
    return not any(p.is_file() and p.name != ".gitkeep" for p in SOT.glob("*"))


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
    memory = memory_dir()
    cleanup_names = [
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
    ]
    # Remove obsolete singleton selector files from older checkouts without
    # reintroducing them as runtime concepts.
    obsolete_prefixes = [("active", "task"), ("active", "phase")]
    for left, right in obsolete_prefixes:
        cleanup_names.extend([f"{left}-{right}.json", f"{left}-{right}.md"])
    for name in cleanup_names:
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
    if source_of_truth_is_empty():
        print("  1) Generate the five source-of-truth files from docs/templates/ into docs/source-of-truth/.")
        print("  2) python3 -B -S .claude/bin/bootstrap_source_of_truth.py --validate-only")
        print("  3) python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh --reset-runtime-state")
    else:
        print("  python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh")
        print("  ./scripts/check-task-dag.sh --strict")
        print("  ./scripts/check-journey-matrix.sh --strict")
        print("  ./scripts/check-wiring-contract.sh --strict --require-new-template-columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
