#!/usr/bin/env python3
"""Safely clean local worktrees and branches for tasks already closed.

This is housekeeping for DAG projects: a closer may leave the active task
worktree alive until Claude Stop/SubagentStop hooks persist the trailer. Later,
`next-wave` can remove clean, completed task checkouts and their local branches.
The script never deletes main/master, never discards dirty worktrees, and never
uses remote state as proof of completion.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

TASK_RE = re.compile(r"P\d{2,}-S\d{2,}-T\d{3,}")
BRANCH_PREFIXES = ("dev/", "feature/", "fix/", "bugfix/", "chore/", "hotfix/")


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def realpath(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except FileNotFoundError:
        return path.resolve(strict=False)


def git_output(args: list[str], cwd: Path) -> str:
    proc = run(["git", *args], cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def resolve_canonical_root(start: Path) -> Path:
    top = Path(git_output(["rev-parse", "--show-toplevel"], start))
    common = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=top)
    if common.returncode == 0:
        common_path = Path(common.stdout.strip())
        if common_path.name == ".git" and common_path.parent.exists():
            return realpath(common_path.parent)
    return realpath(top)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def closed_tasks(root: Path) -> set[str]:
    closed: set[str] = set()
    registry = load_json(root / "orchestrator-state" / "tasks" / "registry.json")
    if isinstance(registry, dict):
        tasks = registry.get("tasks")
        if isinstance(tasks, list):
            iterable = tasks
        elif isinstance(tasks, dict):
            iterable = []
            for tid, value in tasks.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("id", tid)
                    iterable.append(item)
        else:
            iterable = []
        for item in iterable:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("id") or item.get("task_id") or "")
            if TASK_RE.fullmatch(tid) and str(item.get("status") or "") == "done":
                closed.add(tid)

    event_dir = root / "orchestrator-state" / "tasks" / "lifecycle-events"
    if event_dir.is_dir():
        for path in sorted(event_dir.glob("*.json")):
            event = load_json(path)
            if not isinstance(event, dict):
                continue
            tid = str(event.get("task_id") or "")
            if not TASK_RE.fullmatch(tid):
                continue
            if (
                event.get("schema") == "orquestador.lifecycle-event.v1"
                and event.get("agent_type") == "closer"
                and event.get("outcome") == "committed"
                and event.get("next_status") == "done"
            ):
                closed.add(tid)
    return closed


def parse_worktrees(root: Path) -> list[dict[str, str]]:
    proc = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if proc.returncode != 0:
        return []
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in proc.stdout.splitlines() + [""]:
        line = raw.rstrip("\n")
        if not line:
            if current:
                records.append(current)
            current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line[len("worktree ") :]
        elif line.startswith("branch "):
            branch = line[len("branch ") :]
            current["branch"] = branch.removeprefix("refs/heads/")
        elif line == "detached":
            current.setdefault("branch", "detached")
    return records


def active_roots(root: Path) -> set[Path]:
    roots = {realpath(root)}
    for key in ("CLAUDE_WORKTREE_ROOT", "CLAUDE_WORKSPACE_ROOT", "CLAUDE_PROJECT_DIR"):
        raw = os.environ.get(key)
        if raw:
            p = Path(raw)
            if p.exists():
                top = run(["git", "-C", str(p), "rev-parse", "--show-toplevel"])
                if top.returncode == 0 and top.stdout.strip():
                    roots.add(realpath(Path(top.stdout.strip())))
    cwd_top = run(["git", "rev-parse", "--show-toplevel"])
    if cwd_top.returncode == 0 and cwd_top.stdout.strip():
        roots.add(realpath(Path(cwd_top.stdout.strip())))
    return roots


def branch_looks_task_scoped(branch: str, task_id: str) -> bool:
    if branch in {"", "main", "master", "HEAD", "detached"}:
        return False
    if task_id not in branch:
        return False
    if branch == task_id:
        return True
    return branch.startswith(BRANCH_PREFIXES)


def match_task(text: str, allowed: set[str]) -> str | None:
    for tid in sorted(allowed):
        if tid in text:
            return tid
    return None


def git_status(path: Path) -> str:
    proc = run(["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"])
    return proc.stdout.strip() if proc.returncode == 0 else ""


def local_branches(root: Path) -> list[str]:
    proc = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=root)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def branch_in_worktree(branch: str, records: list[dict[str, str]]) -> bool:
    return any(rec.get("branch") == branch and Path(rec.get("path", "")).exists() for rec in records)


def remove_cleanup_request(root: Path, task_id: str) -> None:
    req = root / "orchestrator-state" / "tasks" / "cleanup-requests" / f"{task_id}.json"
    if req.exists():
        req.unlink()


def say(message: str, quiet: bool = False, err: bool = False) -> None:
    if quiet:
        return
    print(message, file=sys.stderr if err else sys.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean local worktrees/branches for closed DAG tasks")
    parser.add_argument("--apply", action="store_true", help="remove clean closed worktrees and local task branches")
    parser.add_argument("--dry-run", action="store_true", help="show what would be removed")
    parser.add_argument("--task", default="", help="limit cleanup to one TASK_ID")
    parser.add_argument("--quiet", action="store_true", help="suppress normal output")
    parser.add_argument("--verbose", action="store_true", help="print skipped diagnostics")
    args = parser.parse_args(argv)

    start = Path.cwd()
    try:
        root = resolve_canonical_root(start)
    except Exception as exc:
        say(f"cleanup-closed-task-worktrees: git_repository=no reason={exc}", args.quiet)
        return 0

    if args.task and not TASK_RE.fullmatch(args.task):
        print(f"ERROR: invalid TASK_ID: {args.task}", file=sys.stderr)
        return 2

    closed = closed_tasks(root)
    if args.task:
        if args.task not in closed:
            say(f"cleanup-closed-task-worktrees: pending task={args.task}; not closed, nothing removed", args.quiet)
            return 0
        closed = {args.task}

    records = parse_worktrees(root)
    active = active_roots(root)
    current_branch = run(["git", "branch", "--show-current"], cwd=root).stdout.strip()

    matched = would_remove = removed = skipped_dirty = skipped_active = branches_deleted = branches_skipped = stale_pruned = 0
    dirty_paths: list[str] = []

    for rec in records:
        wt_raw = rec.get("path", "")
        branch = rec.get("branch", "")
        if not wt_raw:
            continue
        wt = Path(wt_raw)
        haystack = f"{wt_raw} {branch}"
        tid = match_task(haystack, closed)
        if not tid:
            continue
        if branch in {"main", "master"}:
            continue
        matched += 1
        if not wt.exists():
            if args.apply:
                run(["git", "worktree", "prune"], cwd=root)
                stale_pruned += 1
                say(f"pruned missing worktree metadata: {wt_raw} ({branch})", args.quiet)
            else:
                would_remove += 1
                say(f"would prune missing worktree metadata: {wt_raw} ({branch})", args.quiet)
            continue
        wt_real = realpath(wt)
        if wt_real in active:
            skipped_active += 1
            if args.verbose:
                say(f"skip active checkout: {wt_raw} ({branch})", args.quiet)
            continue
        status = git_status(wt)
        if status:
            skipped_dirty += 1
            dirty_paths.append(str(wt))
            if args.verbose:
                say(f"skip dirty closed worktree: {wt_raw} ({branch})", args.quiet, err=True)
                for line in status.splitlines()[:40]:
                    say(f"  {line}", args.quiet, err=True)
                say(f"manual review: git -C {str(wt)!r} status --short && git -C {str(wt)!r} diff --stat", args.quiet, err=True)
            continue
        if args.apply:
            proc = run(["git", "worktree", "remove", str(wt)], cwd=root)
            if proc.returncode != 0:
                proc = run(["git", "worktree", "remove", "--force", str(wt)], cwd=root)
            if proc.returncode != 0 and wt.exists():
                skipped_dirty += 1
                dirty_paths.append(str(wt))
                say(f"skip worktree remove failed: {wt_raw} ({branch})", args.quiet, err=True)
                continue
            removed += 1
            say(f"removed closed worktree: {wt_raw} ({branch})", args.quiet)
            remove_cleanup_request(root, tid)
        else:
            would_remove += 1
            say(f"would remove closed worktree: {wt_raw} ({branch})", args.quiet)

    # Re-read worktrees after removals so branch deletion sees detached branches correctly.
    records_after = parse_worktrees(root)
    for branch in local_branches(root):
        tid = match_task(branch, closed)
        if not tid or not branch_looks_task_scoped(branch, tid):
            continue
        if branch in {current_branch, "main", "master"}:
            branches_skipped += 1
            if args.verbose:
                say(f"skip current/main branch: {branch}", args.quiet)
            continue
        if branch_in_worktree(branch, records_after):
            branches_skipped += 1
            if args.verbose:
                say(f"skip branch still used by worktree: {branch}", args.quiet)
            continue
        if args.apply:
            proc = run(["git", "branch", "-D", branch], cwd=root)
            if proc.returncode == 0:
                branches_deleted += 1
                say(f"deleted closed task branch: {branch}", args.quiet)
            else:
                branches_skipped += 1
                say(f"skip branch delete failed: {branch}", args.quiet, err=True)
        else:
            would_remove += 1
            say(f"would delete closed task branch: {branch}", args.quiet)

    container = Path(os.environ.get("CLAUDE_TASK_WORKTREES_DIR", str(root.parent / f"{root.name}-worktrees")))
    if args.apply and container.is_dir():
        try:
            next(container.iterdir())
        except StopIteration:
            try:
                container.rmdir()
                say(f"removed empty container: {container}", args.quiet)
            except OSError:
                pass

    mode = "apply" if args.apply else "dry-run"
    if not args.quiet:
        print(
            "cleanup-closed-task-worktrees: "
            f"closed_tasks={len(closed)} matched={matched} would_remove={would_remove} "
            f"removed={removed} skipped_dirty={skipped_dirty} skipped_active={skipped_active} "
            f"stale_pruned={stale_pruned} branches_deleted={branches_deleted} "
            f"branches_skipped={branches_skipped} mode={mode} task={args.task or 'all'}"
        )
    if skipped_dirty > 0:
        if args.quiet:
            print(
                "cleanup-closed-task-worktrees: dirty closed worktree(s) skipped; "
                "run: bash scripts/cleanup-closed-task-worktrees.sh --apply --verbose",
                file=sys.stderr,
            )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
