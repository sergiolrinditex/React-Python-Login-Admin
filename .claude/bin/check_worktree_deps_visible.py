#!/usr/bin/env python3
"""Read-only guard for stale task worktrees."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

LIFECYCLE_PREFIX = "orchestrator-state/tasks/lifecycle-events"


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, timeout=20)


def git_toplevel(cwd: Path) -> Path:
    res = run_git(cwd, ["rev-parse", "--show-toplevel"])
    if res.returncode == 0 and res.stdout.strip():
        return Path(res.stdout.strip()).resolve()
    return cwd.resolve()


def load_registry(root: Path) -> dict[str, Any]:
    path = root / "orchestrator-state/tasks/registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERROR: registry.json not found at {path}")
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: registry.json must be an object: {path}")
    return data


def tasks_list(registry: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = registry.get("tasks") or []
    if isinstance(tasks, dict):
        out: list[dict[str, Any]] = []
        for key, value in tasks.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("id", key)
                out.append(item)
        return out
    return [t for t in tasks if isinstance(t, dict)]


def task_by_id(registry: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for task in tasks_list(registry):
        if str(task.get("id") or "") == task_id:
            return task
    return None


def git_ref_exists(repo: Path, ref: str) -> bool:
    return run_git(repo, ["rev-parse", "--verify", "--quiet", ref]).returncode == 0


def path_exists_in_ref(repo: Path, ref: str, rel: str) -> bool:
    return run_git(repo, ["cat-file", "-e", f"{ref}:{rel}"]).returncode == 0


def grep_commit(repo: Path, ref: str, needle: str) -> str | None:
    if not git_ref_exists(repo, ref):
        return None
    res = run_git(repo, ["log", "--format=%H", "--grep", needle, "-n", "1", ref])
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.splitlines()[0]
    return None


def rel_exists(repo: Path, rel: str) -> bool:
    return (repo / rel).exists() or path_exists_in_ref(repo, "HEAD", rel)


def check(task_id: str, canonical_root: Path, workspace_root: Path) -> dict[str, Any]:
    registry = load_registry(canonical_root)
    task = task_by_id(registry, task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "reason": "task_not_found", "errors": [f"TASK_ID not found: {task_id}"]}

    done = {str(t.get("id")) for t in tasks_list(registry) if str(t.get("status") or "") == "done"}
    deps = [str(dep).strip() for dep in (task.get("depends_on") or []) if str(dep).strip()]
    done_deps = [dep for dep in deps if dep in done]
    origin_main = "origin/main"
    origin_available = git_ref_exists(workspace_root, origin_main)
    missing: list[dict[str, Any]] = []
    warnings: list[str] = []

    for dep in done_deps:
        rel_event = f"{LIFECYCLE_PREFIX}/{dep}.json"
        head_has_event = rel_exists(workspace_root, rel_event)
        canonical_has_event = (canonical_root / rel_event).exists()
        origin_has_event = origin_available and path_exists_in_ref(workspace_root, origin_main, rel_event)
        head_commit = grep_commit(workspace_root, "HEAD", dep)
        origin_commit = grep_commit(workspace_root, origin_main, dep) if origin_available else None
        evidence: list[str] = []
        if origin_has_event and not head_has_event:
            evidence.append(f"{origin_main}:{rel_event} exists but HEAD/worktree does not")
        if canonical_has_event and not head_has_event and workspace_root.resolve() != canonical_root.resolve():
            evidence.append(f"canonical {rel_event} exists but active worktree does not")
        if origin_commit and not head_commit:
            evidence.append(f"{origin_main} has commit matching {dep} ({origin_commit[:12]}) but HEAD does not")
        if evidence:
            missing.append({
                "dependency": dep,
                "lifecycle_event": rel_event,
                "origin_has_event": origin_has_event,
                "canonical_has_event": canonical_has_event,
                "head_has_event": head_has_event,
                "origin_commit": origin_commit,
                "head_commit": head_commit,
                "evidence": evidence,
            })

    if not origin_available:
        warnings.append("origin/main not available; dependency visibility checked against canonical root and HEAD only")

    return {
        "ok": not missing,
        "task_id": task_id,
        "reason": None if not missing else "stale_worktree_dep_missing",
        "canonical_root": str(canonical_root),
        "workspace_root": str(workspace_root),
        "origin_main_available": origin_available,
        "depends_on": deps,
        "done_dependencies": done_deps,
        "missing_dependency_visibility": missing,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Block planning from a stale worktree that cannot see done dependencies")
    parser.add_argument("task_id")
    parser.add_argument("--canonical-root", default=os.environ.get("CLAUDE_ORCHESTRATOR_ROOT") or "")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace_root).resolve() if args.workspace_root else git_toplevel(Path.cwd().resolve())
    canonical = Path(args.canonical_root).resolve() if args.canonical_root else workspace
    payload = check(args.task_id, canonical, workspace)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if payload["ok"]:
            print(f"worktree-deps-visible: ok task={args.task_id}")
            for warning in payload.get("warnings") or []:
                print(f"WARN: {warning}")
        else:
            print(f"worktree-deps-visible: blocked task={args.task_id} reason={payload.get('reason')}", file=sys.stderr)
            for item in payload.get("missing_dependency_visibility") or []:
                print(f"- dep {item.get('dependency')} invisible in active worktree", file=sys.stderr)
                for ev in item.get("evidence") or []:
                    print(f"  {ev}", file=sys.stderr)
            print("Planner must not auto-rebase. Recreate/update the task worktree from the canonical root, then rerun /next-slice.", file=sys.stderr)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
