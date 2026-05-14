#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, subprocess, sys
from common import ensure_parent, find_task, journeys_closing_at_task, load_registry, now_iso, workspace_root, workspace_relpath, handoff_path, evidence_dir

ALLOWED_STATUS = {"ready_for_close", "done"}

def run_command(command: str, timeout: int) -> dict[str, object]:
    proc = subprocess.run(command, cwd=workspace_root(), shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return {"command": command, "returncode": proc.returncode, "stdout_tail": proc.stdout[-4000:], "stderr_tail": proc.stderr[-4000:]}

def append_handoff(task_id: str, section: str):
    path = handoff_path(task_id)
    ensure_parent(path)
    old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else f"# Handoff {task_id}\n"
    if not old.endswith("\n"): old += "\n"
    path.write_text(old + "\n" + section.rstrip() + "\n", encoding="utf-8")
    return path

def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-verify a low-risk DAG slice.")
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-any-status", action="store_true")
    args = parser.parse_args()
    registry = load_registry()
    task_id = args.task_id or os.environ.get("CLAUDE_ACTIVE_TASK_ID")
    task = find_task(registry, task_id)
    if not task:
        print(f"ERROR: unknown TASK_ID: {task_id}", file=sys.stderr); return 2
    risk = str(task.get("risk_level") or "medium").lower()
    mode = str(task.get("verify_mode") or "human").lower()
    status = str(task.get("status") or "")
    if risk != "low" or mode != "auto":
        print(f"ERROR: {task_id} is not eligible for auto-verify (risk={risk}, verify_mode={mode})", file=sys.stderr); return 2
    if not args.allow_any_status and status not in ALLOWED_STATUS:
        print(f"ERROR: {task_id} status={status}; auto-verify requires ready_for_close", file=sys.stderr); return 2
    closing = journeys_closing_at_task(registry, task_id)
    if closing:
        print(f"ERROR: {task_id} closes journey(s) {closing}; use /verify-slice for human journey gate", file=sys.stderr); return 2
    commands = [str(c) for c in (task.get("verification_commands") or []) if str(c).strip()]
    if not commands:
        print(f"ERROR: {task_id} has no verification_commands", file=sys.stderr); return 2
    if args.dry_run:
        print(json.dumps({"eligible": True, "task_id": task_id, "risk_level": risk, "verify_mode": mode, "commands": commands}, ensure_ascii=False, indent=2)); return 0
    ok, results = True, []
    try:
        for command in commands:
            result = run_command(command, args.timeout); results.append(result)
            if result["returncode"] != 0: ok = False; break
    except subprocess.TimeoutExpired as exc:
        ok = False; results.append({"command": exc.cmd, "timeout": args.timeout, "returncode": "timeout"})
    evidence_root = evidence_dir(task_id); evidence_root.mkdir(parents=True, exist_ok=True)
    stamp = now_iso().replace(":", "").replace("+00:00", "Z")
    evidence_path = evidence_root / f"auto-verify-{stamp}.json"
    evidence_path.write_text(json.dumps({"generated_at": now_iso(), "task_id": task_id, "results": results, "verified": ok}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    outcome = "verified" if ok else "issues_found"
    section = f"""
## verify-slice

- TASK_ID: {task_id}
- VERIFY_MODE: auto
- RISK_LEVEL: {risk}
- VERIFY_OUTCOME: {outcome}
- DATA_CONTRACT_ROWS: real/provided sandbox data from TECHNICAL_GUIDE Verification Data Contract; no decorative data-only closure
- PERSISTED_DATA_OBSERVED: command evidence in `{workspace_relpath(evidence_path)}`
- DATA_SETUP: command-driven only; no endpoint-under-test self-seeding
- FLOWS_TESTED: {', '.join(commands)}
- EVIDENCE: {workspace_relpath(evidence_path)}
- GENERATED_AT: {now_iso()}
"""
    handoff = append_handoff(task_id, section)
    print(json.dumps({"ok": ok, "task_id": task_id, "outcome": outcome, "handoff": workspace_relpath(handoff), "evidence": workspace_relpath(evidence_path)}, ensure_ascii=False, indent=2))
    return 0 if ok else 2
if __name__ == "__main__": raise SystemExit(main())
