#!/usr/bin/env python3
"""PreToolUse hook — surfaces unresolved docs discrepancies, NEVER blocks.

When `official-docs-researcher` detects a mismatch between internal docs and
vendor official documentation, it drops a note in
`orchestrator-state/memory/official-doc-notes/<slug>.md`. The framework's rule is that
the developer should reconcile those notes before writing more product code.

This hook runs on Write / Edit / MultiEdit / NotebookEdit calls and, if any note lacks
a `RESOLVED: <how>` line (archived `RESOLVED 2026-...` is accepted), injects a **warning** into the tool-use context
via `hookSpecificOutput.additionalContext`. It does NOT emit a deny
decision — the tool call always proceeds. The warning is purely informative
so the agent can decide to reconcile first and preserves the user's
"never block anything" stance.

It also does NOT fire at all when the target file is part of the
reconciliation workflow itself (notes folder, handoffs, registry, source
docs, etc.) — listing those in ALLOW_DURING_DISCREPANCY keeps the signal
clean.

Reference: source-of-truth contract and official-doc notes policy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from common import (
        has_unresolved_doc_discrepancies,
        log_hook_error,
        project_root,
        workspace_root,
    )
except Exception:
    has_unresolved_doc_discrepancies = lambda: (False, [])  # type: ignore[assignment]
    project_root = lambda: Path(".")  # type: ignore[assignment]
    workspace_root = lambda: Path(".")  # type: ignore[assignment]
    def log_hook_error(name, exc):  # type: ignore[no-redef]
        return None


# Paths that stay editable even during a discrepancy — they are part of the
# reconciliation workflow itself, not product code.
ALLOW_DURING_DISCREPANCY = (
    "orchestrator-state/memory/official-doc-notes/",
    "orchestrator-state/memory/PROGRESS.md",
    "orchestrator-state/memory/decisions.md",
    "orchestrator-state/memory/risk-register.md",
    "orchestrator-state/tasks/handoffs/",
    "orchestrator-state/tasks/reports/",
    "orchestrator-state/tasks/evidence/",
    "orchestrator-state/tasks/registry.json",
    "orchestrator-state/tasks/runtime-state.json",
    "orchestrator-state/tasks/ledger.jsonl",
    "orchestrator-state/hook-errors.log",
    "docs/source-of-truth/",  # reconciling the source-of-truth pack is allowed
)


def _target_path(data: dict) -> str:
    tool_input = data.get("tool_input") or {}
    return (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or ""
    )


def _is_allowlisted(target: str) -> bool:
    if not target:
        return False
    # Normalise to a repo-relative path (best effort).
    try:
        roots = [workspace_root().resolve(), project_root().resolve()]
        p = Path(target)
        if not p.is_absolute():
            p = roots[0] / p
        p = p.resolve()
        rel = target
        for root in roots:
            try:
                rel = p.relative_to(root).as_posix()
                break
            except ValueError:
                continue
    except Exception:
        rel = target
    # Strip a leading "./" prefix only, preserving any leading dot directory
    # name (e.g. ".claude/..."). Using str.lstrip("./") here would be a bug:
    # it strips every leading `.` and `/` character, collapsing `.claude/...`
    # into `claude/...` and breaking the prefix check.
    if rel.startswith("./"):
        rel = rel[2:]
    return any(rel.startswith(prefix) for prefix in ALLOW_DURING_DISCREPANCY)


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        data = json.loads(raw)
        tool_name = data.get("tool_name") or ""

        # Only enforce on code-writing tools; Bash/Grep/Glob/Read are free.
        if tool_name not in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
            return 0

        target = _target_path(data)
        if _is_allowlisted(target):
            return 0

        has_unresolved, notes = has_unresolved_doc_discrepancies()
        if not has_unresolved:
            return 0

        warn_lines = [
            "⚠️  Unresolved docs discrepancies detected (framework warning, not a block).",
            "",
            "Unresolved notes:",
        ]
        for note in notes[:10]:
            warn_lines.append(f"  - {note}")
        warn_lines.append("")
        warn_lines.append(
            "Recommendation: reconcile the source-of-truth pack with the "
            "official docs, then add a `RESOLVED: <how>` line to each note (`RESOLVED 2026-...` date-prefixed notes are also accepted). "
            "This hook is INFORMATIONAL only — your tool call proceeds."
        )
        # additionalContext is non-blocking: the tool runs as usual, the agent
        # just sees this warning injected into its next turn. No deny, no
        # permissionDecision.
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n".join(warn_lines),
            },
        }
        print(json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        try:
            log_hook_error("hook_docs_discrepancy_check", exc)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
