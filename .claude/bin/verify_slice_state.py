#!/usr/bin/env python3
"""Classify the mechanical /verify-slice state for one DAG TASK_ID."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from common import (
    find_task,
    handoff_path,
    load_registry,
    load_runtime_state,
    project_root,
    report_path,
    task_pack_path,
    workspace_relpath,
    workspace_root,
)
from check_handoff_contract import SECTION_RE, _heading_key_value, _section_from_match, validate as validate_handoff


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _latest_key_in_section(text: str, section_name: str, key: str) -> str | None:
    """Return the last value for KEY in the last matching markdown section."""
    section_norm = section_name.strip().lower()
    current: str | None = None
    found: str | None = None
    wanted_key = key.upper()
    for line in text.splitlines():
        heading_key = _heading_key_value(line)
        if heading_key and (current == section_norm or (section_norm == "verify-slice" and current == "verify-slice")):
            heading_name, heading_value = heading_key
            if heading_name == wanted_key:
                found = heading_value
            continue
        sec = SECTION_RE.match(line)
        if sec and not heading_key:
            section_name = _section_from_match(sec)
            if section_name is None:
                # H3/H4 prose subheading inside the current section; do not
                # lose the section's machine-readable keys.
                continue
            if section_norm == "verify-slice":
                current = "verify-slice" if section_name == "verify-slice" else None
            else:
                current = section_name
            continue
        if current == section_norm or (section_norm == "verify-slice" and current == "verify-slice"):
            stripped = line.strip()
            if stripped.startswith("-"):
                stripped = stripped[1:].strip()
            prefix = f"{key}:"
            if stripped.startswith(prefix):
                found = stripped.split(":", 1)[1].strip()
    return found


def classify(task_id: str) -> dict[str, Any]:
    registry = load_registry()
    runtime = load_runtime_state()
    task = find_task(registry, task_id)
    canonical = project_root().resolve()
    workspace = workspace_root().resolve()
    handoff = handoff_path(task_id)
    report = report_path(task_id)
    pack_env = os.environ.get("CLAUDE_TASK_PACK")
    if pack_env:
        pack = Path(pack_env).expanduser()
        if not pack.is_absolute():
            pack = (workspace / pack).resolve()
    else:
        pack = task_pack_path(task_id)
    text = _read_text(handoff)

    active_task = os.environ.get("CLAUDE_ACTIVE_TASK_ID") or None
    errors: list[str] = []
    warnings: list[str] = []

    if not task:
        errors.append(f"unknown TASK_ID: {task_id}")
    if active_task and active_task != task_id:
        errors.append(f"CLAUDE_ACTIVE_TASK_ID mismatch: {active_task} != {task_id}")
    if not pack.exists():
        errors.append(f"missing task pack: {workspace_relpath(pack)}")
    elif task_id not in _read_text(pack):
        errors.append(f"task pack does not mention TASK_ID: {workspace_relpath(pack)}")
    if not handoff.exists():
        errors.append(f"missing handoff: {workspace_relpath(handoff)}")

    ready_ok, ready_errors, ready_details = validate_handoff(
        task_id,
        require_ready_for_close=True,
        require_verify_slice=False,
    )
    verify_ok, verify_errors, verify_details = validate_handoff(
        task_id,
        require_ready_for_close=True,
        require_verify_slice=True,
    )

    verify_outcome = _latest_key_in_section(text, "verify-slice", "VERIFY_OUTCOME")
    verify_agent = _latest_key_in_section(text, "verify-slice", "AGENT")
    status = str((task or {}).get("status") or "")
    last_updated_by = str((task or {}).get("last_updated_by") or "")
    has_report = report.exists()

    action = "blocked"
    reason = "unclassified"

    if errors:
        action = "blocked"
        reason = "precondition_failed"
    elif status == "done" and has_report:
        action = "post_closer_done"
        reason = "registry done and report exists; do not relaunch closer/debugger"
    elif verify_outcome == "verified" and verify_ok:
        action = "invoke_closer"
        if last_updated_by == "closer" and status == "blocked":
            reason = "verified_after_early_closer_block; relaunch closer only"
        else:
            reason = "verify handoff is verified and close contract is satisfied"
    elif verify_outcome == "issues_found":
        action = "invoke_debugger_or_register_followup"
        reason = "verify-slice reported issues_found"
    elif verify_outcome == "blocked":
        action = "blocked"
        reason = "verify-slice blocked; inspect blocker in handoff and fix mechanical/MCP environment before relaunch"
    elif verify_outcome in {"pending", "partial"}:
        action = "invoke_slice_verifier"
        reason = "verify-slice has only a pending/partial skeleton; relaunch slice-verifier"
    elif ready_ok:
        action = "invoke_slice_verifier"
        reason = "validator/tester ready but no verified verify-slice handoff yet"
    else:
        if status == "needs_debug":
            action = "invoke_debugger"
            reason = "task status needs_debug before verify"
        elif status in {"validator_tester_pending", "in_progress", "claimed"}:
            action = "wait_validator_tester"
            reason = "pipeline has not reached ready_for_close"
        else:
            action = "blocked"
            reason = "handoff not ready for close"
        warnings.extend(ready_errors)

    return {
        "ok": action not in {"blocked"},
        "task_id": task_id,
        "action": action,
        "reason": reason,
        "status": status,
        "last_updated_by": last_updated_by,
        "verify_outcome": verify_outcome,
        "verify_agent": verify_agent,
        "canonical_root": str(canonical),
        "workspace_root": str(workspace),
        "handoff": workspace_relpath(handoff),
        "handoff_exists": handoff.exists(),
        "task_pack": workspace_relpath(pack),
        "task_pack_exists": pack.exists(),
        "report": workspace_relpath(report),
        "report_exists": has_report,
        "ready_for_close_contract_ok": ready_ok,
        "verify_contract_ok": verify_ok,
        "ready_errors": ready_errors,
        "verify_errors": verify_errors,
        "errors": errors,
        "warnings": warnings,
        "runtime_last_worker": runtime.get("last_worker"),
        "runtime_last_event": runtime.get("last_event"),
        "details": {"ready": ready_details, "verify": verify_details},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify the next /verify-slice action for a TASK_ID.")
    parser.add_argument("task_id", nargs="?", help="DAG TASK_ID. Defaults to CLAUDE_ACTIVE_TASK_ID.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    task_id = args.task_id or os.environ.get("CLAUDE_ACTIVE_TASK_ID")
    if not task_id:
        print("ERROR: TASK_ID required", file=sys.stderr)
        return 2
    result = classify(task_id)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"VERIFY_SLICE_ACTION: {result['action']}")
        print(f"REASON: {result['reason']}")
        for err in result.get("errors") or []:
            print(f"ERROR: {err}")
        for warn in result.get("warnings") or []:
            print(f"WARN: {warn}")
    return 0 if result["action"] not in {"blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
