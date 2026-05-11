#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from common import (
    append_jsonl,
    effective_active_task_id,
    find_task,
    ledger_path,
    load_active_task,
    load_registry,
    now_iso,
    project_root,
    run_commands,
    tasks_dir,
)


def _lock_file() -> Path:
    return tasks_dir() / ".async-test.lock"

def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    data = json.loads(raw)
    if data.get("tool_name") not in {"Write", "Edit"}:
        return 0

    active = load_active_task()
    task_id = effective_active_task_id(active)
    task = active
    if task_id and task_id != active.get("id"):
        # In DAG worker terminals the environment override is authoritative.
        # Pull commands from registry for that node instead of from the global
        # active-task singleton, which another terminal may have moved.
        task = find_task(load_registry(), task_id) or active
    commands = task.get("verification_commands", []) or []
    if not task_id or not commands:
        return 0
    lock_file = _lock_file()
    if lock_file.exists():
        return 0

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(now_iso(), encoding="utf-8")
    try:
        results = run_commands(commands, cwd=project_root(), timeout=900)
        evidence_dir = tasks_dir() / "evidence" / task_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        log_file = evidence_dir / "async-check.log"
        chunks = []
        for item in results:
            chunks.append(f"$ {item['command']}\n[returncode] {item['returncode']}\n")
            if item["stdout"]:
                chunks.append("STDOUT:\n" + item["stdout"] + "\n")
            if item["stderr"]:
                chunks.append("STDERR:\n" + item["stderr"] + "\n")
            chunks.append("\n")
        log_file.write_text("".join(chunks), encoding="utf-8")

        append_jsonl(ledger_path(), {
            "ts": now_iso(),
            "event": "async_test_run",
            "active_task_id": task_id,
            "commands": commands,
            "log_file": str(log_file),
            "success": all(item["returncode"] == 0 for item in results),
        })
    finally:
        try:
            lock_file.unlink()
        except FileNotFoundError:
            pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
