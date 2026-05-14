#!/usr/bin/env python3
"""Append a recoverable write-first /verify-slice skeleton to a task handoff."""
from __future__ import annotations

import argparse
from pathlib import Path

from common import handoff_path, now_iso, workspace_relpath


def latest_verify_is_pending(text: str, task_id: str) -> bool:
    if "## verify-slice" not in text and "## slice-verifier" not in text:
        return False
    marker_positions = [text.rfind("## verify-slice"), text.rfind("## slice-verifier")]
    pos = max(marker_positions)
    if pos < 0:
        return False
    tail = text[pos:]
    return f"TASK_ID: {task_id}" in tail and "VERIFY_OUTCOME: pending" in tail


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a recoverable pending verify-slice skeleton to the handoff.")
    parser.add_argument("task_id")
    parser.add_argument("--mode", default="pre-closer", choices=["pre-closer", "post-closer"])
    args = parser.parse_args()

    path = handoff_path(args.task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else f"# Handoff {args.task_id}\n"
    if latest_verify_is_pending(text, args.task_id):
        print(f"VERIFY_SKELETON: exists path={workspace_relpath(path)}")
        return 0

    evidence = Path("orchestrator-state") / "tasks" / "evidence" / args.task_id
    block = f"""

## verify-slice

- AGENT: slice-verifier
- TASK_ID: {args.task_id}
- TIMESTAMP: {now_iso()}
- MODE: {args.mode}
- VERIFY_STATUS: started
- VERIFY_OUTCOME: pending
- MCP_BROWSER: pending
- DATA_CONTRACT_ROWS: pending
- DATA_SETUP: pending
- PERSISTED_DATA_OBSERVED: pending
- FLOWS_TESTED: pending
- FINDINGS: pending
- BLOCKER_REASON: verification_started_not_completed
- EVIDENCE: {evidence}/verify-*

CLAUDE_TRAILER:
AGENT: slice-verifier
TASK_ID: {args.task_id}
OUTCOME: blocked
NEXT_STATUS: blocked
HANDOFF: orchestrator-state/tasks/handoffs/{args.task_id}.md
EVIDENCE: orchestrator-state/tasks/evidence/{args.task_id}/
VERIFY_OUTCOME: pending
"""
    with path.open("a", encoding="utf-8") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        fh.write(block)
    print(f"VERIFY_SKELETON: written path={workspace_relpath(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
