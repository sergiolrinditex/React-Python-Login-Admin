#!/usr/bin/env python3
"""PreToolUse write-scope guard for DAG-safe orchestration.

This hook blocks only corruption-prone writes. It does not try to validate
product code quality; validator/tester own that. The guarded cases are:
  - app-building agents editing static `.claude/` config;
  - any active TASK_ID writing another task's handoff/evidence/report/pack;
  - DAG task terminals editing source-of-truth docs mid-slice;
  - direct Write/Edit/MultiEdit to generated core state that should be written
    by bootstrap/claim/hooks under locks.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    dag_worker_task_id,
    append_jsonl,
    ledger_path,
    load_registry,
    find_task,
    log_hook_error,
    now_iso,
    project_root,
    workspace_root,
    task_write_set,
    write_patterns_conflict,
)

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

CORE_STATE_FILES = {
    "orchestrator-state/tasks/registry.json",
    "orchestrator-state/tasks/runtime-state.json",
    "orchestrator-state/tasks/ledger.jsonl",
    "orchestrator-state/memory/task-dag.json",
    "orchestrator-state/memory/task-dag.md",
    "orchestrator-state/memory/execution-graph.json",
}

TASK_SCOPED_PATTERNS = [
    re.compile(r"^orchestrator-state/tasks/handoffs/([^/]+)\.md$"),
    re.compile(r"^orchestrator-state/tasks/reports/([^/]+?)(?:-revision-[^/]*)?\.md$"),
    re.compile(r"^orchestrator-state/tasks/task-packs/([^/]+)\.md$"),
    re.compile(r"^orchestrator-state/tasks/evidence/([^/]+)(?:/.*)?$"),
]


def _target_path(data: dict[str, Any]) -> str:
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""
    return str(
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or tool_input.get("path")
        or ""
    )


def _repo_rel(path_text: str) -> str:
    if not path_text:
        return ""
    workspace = workspace_root().resolve()
    orchestrator = project_root().resolve()
    raw = Path(path_text).expanduser()
    if not raw.is_absolute():
        raw = workspace / raw
    resolved = raw.resolve()
    # Product writes happen in the active task worktree; state writes happen in
    # the canonical orchestrator repo. Try workspace first to avoid treating
    # worktree product paths as absolute paths outside the repo.
    for root in (workspace, orchestrator):
        try:
            return resolved.relative_to(root).as_posix()
        except Exception:
            pass
    rel = str(path_text).replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    return rel


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))


def _task_id_from_scoped_path(rel: str) -> str | None:
    for regex in TASK_SCOPED_PATTERNS:
        match = regex.match(rel)
        if match:
            return match.group(1)
    return None


def _write_set_warning(rel: str, task_id: str) -> str | None:
    """Warn when a product-code write is outside the declared write-set.

    This remains non-blocking because write_set is a scheduling/conflict hint,
    not a complete ACL. The warning is still logged so closer/validator can see
    it in the ledger and decide whether the source-of-truth needs widening.
    """
    try:
        task = find_task(load_registry(), task_id)
        if not task:
            return None
        declared = task_write_set(task)
        if not declared:
            return None
        if rel.startswith("orchestrator-state/") or rel.startswith("docs/") or rel.startswith(".claude/"):
            return None
        if not any(write_patterns_conflict(rel, pattern) for pattern in declared):
            return f"write outside declared Write set for {task_id}: {rel} not in {declared}"
    except Exception:
        return None
    return None


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        data = json.loads(raw)
        tool_name = str(data.get("tool_name") or "")
        if tool_name not in WRITE_TOOLS:
            return 0

        target = _target_path(data)
        rel = _repo_rel(target)
        if not rel:
            return 0

        task_id = dag_worker_task_id()

        # Static orchestrator config is not product-code runtime. Allow only in
        # intentional orchestrator-maintenance mode.
        if rel.startswith(".claude/") and os.environ.get("CLAUDE_ALLOW_STATIC_CONFIG_WRITES") != "1":
            _deny(
                "Blocked write to static orchestrator config during app execution: "
                f"{rel}. Set CLAUDE_ALLOW_STATIC_CONFIG_WRITES=1 only for explicit orchestrator maintenance."
            )
            return 0

        # Source-of-truth changes during a claimed/active DAG terminal would
        # invalidate registry/task-dag while agents are mid-slice.
        if task_id and rel.startswith("docs/source-of-truth/") and os.environ.get("CLAUDE_ALLOW_SOURCE_TRUTH_WRITES") != "1":
            _deny(
                f"Blocked source-of-truth edit while TASK_ID {task_id} is active: {rel}. "
                "Finish/abort the slice, edit docs, then rerun bootstrap/checks."
            )
            return 0

        # docs/product-baseline is the cumulative built baseline snapshot. It is synced
        # by scripts/sync-product-baseline.sh after verified closer evidence, not
        # hand-edited by an active worker terminal.
        if task_id and rel.startswith("docs/product-baseline/") and os.environ.get("CLAUDE_ALLOW_BASELINE_SYNC_WRITES") != "1":
            _deny(
                f"Blocked direct baseline edit while TASK_ID {task_id} is active: {rel}. "
                "Use scripts/sync-product-baseline.sh from closer/phase-gate context instead."
            )
            return 0

        # Follow-up proposal YAML and source-doc patches are written by
        # register_followup_task.py under locks. Free-form model writes here can
        # create orphan tasks that the DAG cannot schedule safely.
        if task_id and (rel.startswith("orchestrator-state/tasks/follow-ups/") or rel.startswith("orchestrator-state/tasks/source-doc-patches/")) and os.environ.get("CLAUDE_ALLOW_FOLLOWUP_SCRIPT_WRITES") != "1":
            _deny(
                f"Blocked direct follow-up/source-patch write while TASK_ID {task_id} is active: {rel}. "
                "Use scripts/register-followup-task.sh propose|promote|waive."
            )
            return 0

        # Stack-specific dev profile is owned by the generated app, not by any
        # individual slice. Editing it during a slice (especially in
        # push-to-main with parallel terminals) lets one closer/developer
        # squash the concrete profile to the neutral stub from the
        # meta-orchestrator template, breaking dev-restart for every parallel
        # terminal at once. Setup/teardown of the profile happens outside the
        # DAG pipeline (app generation + STACK_PROFILE.yaml), not from inside
        # a slice -- override only for intentional maintenance.
        DEV_PROFILE_PROTECTED = (
            "scripts/dev-restart.profile.sh",
            "scripts/dev-restart.sh",
        )
        if task_id and rel in DEV_PROFILE_PROTECTED and os.environ.get("CLAUDE_ALLOW_DEV_PROFILE_WRITES") != "1":
            _deny(
                f"Blocked stack-specific dev profile edit while TASK_ID {task_id} is active: {rel}. "
                "This file is shared across all parallel terminals; editing it during a slice can "
                "silently overwrite the working profile when another terminal commits. "
                "Adjust the profile outside any active slice, or set "
                "CLAUDE_ALLOW_DEV_PROFILE_WRITES=1 for intentional maintenance."
            )
            return 0

        # Generated core state is written by scripts/hooks under locks, not by
        # model text editing.
        if rel in CORE_STATE_FILES and os.environ.get("CLAUDE_ALLOW_CORE_STATE_WRITES") != "1":
            _deny(
                "Blocked direct edit to generated core orchestrator state: "
                f"{rel}. Use bootstrap/claim/hooks or explicit maintenance override."
            )
            return 0

        # Per-task artifacts must match the terminal's TASK_ID. This is the
        # strongest DAG corruption guard for handoffs/evidence/reports/packs.
        scoped_tid = _task_id_from_scoped_path(rel)
        if task_id and scoped_tid and scoped_tid != task_id:
            _deny(
                f"Blocked cross-task write under CLAUDE_ACTIVE_TASK_ID={task_id}: {rel} belongs to {scoped_tid}. "
                "Use the correct terminal or correct TASK_ID before writing."
            )
            return 0

        warning = _write_set_warning(rel, task_id) if task_id else None
        if warning:
            append_jsonl(ledger_path(), {
                "ts": now_iso(),
                "event": "write_scope_warning",
                "task_id": task_id,
                "file_path": rel,
                "warning": warning,
            })
    except Exception as exc:
        log_hook_error("hook_write_scope_guard", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
