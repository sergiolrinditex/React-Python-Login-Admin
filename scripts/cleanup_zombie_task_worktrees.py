#!/usr/bin/env python3
"""Clean local task branches/worktrees that have no unique patches vs main.

This complements closed-task cleanup. It is deliberately conservative:
- only task-scoped local branches are considered;
- dirty or active worktrees are never removed;
- live registry tasks are skipped;
- branches with any unique patch compared with origin/main are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TASK_RE = re.compile(r"P\d{2,}-S\d{2,}-T\d{3,}")
BRANCH_PREFIXES = ("dev/", "feature/", "fix/", "bugfix/", "chore/", "hotfix/")
PROTECTED = {"", "HEAD", "main", "master", "develop", "dev", "release", "staging", "production", "detached"}
LIVE_STATUSES = {"ready", "claimed", "in_progress", "validator_tester_pending", "ready_for_close", "verified_pending_close"}


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)


def say(message: str, quiet: bool = False, err: bool = False) -> None:
    if quiet:
        return
    print(message, file=sys.stderr if err else sys.stdout)


def git_output(root: Path, *args: str) -> str:
    proc = run(["git", *args], cwd=root)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def resolve_root(start: Path) -> Path:
    top = Path(git_output(start, "rev-parse", "--show-toplevel"))
    common = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=top)
    if common.returncode == 0:
        common_path = Path(common.stdout.strip())
        if common_path.name == ".git" and common_path.parent.exists():
            return common_path.parent.resolve()
    return top.resolve()


def realpath(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except FileNotFoundError:
        return path.resolve(strict=False)


def task_id_from_branch(branch: str) -> str:
    match = TASK_RE.search(branch)
    return match.group(0) if match else ""


def branch_looks_task_scoped(branch: str) -> bool:
    if branch in PROTECTED or branch.startswith("HEAD"):
        return False
    tid = task_id_from_branch(branch)
    if not tid:
        return False
    return branch == tid or branch.startswith(BRANCH_PREFIXES)


def parse_worktrees(root: Path) -> list[dict[str, str]]:
    proc = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if proc.returncode != 0:
        return []
    records: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for raw in proc.stdout.splitlines() + [""]:
        line = raw.rstrip("\n")
        if not line:
            if cur:
                records.append(cur)
            cur = {}
            continue
        if line.startswith("worktree "):
            cur["path"] = line[len("worktree ") :]
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch ") :].removeprefix("refs/heads/")
        elif line == "detached":
            cur.setdefault("branch", "detached")
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


def local_branches(root: Path) -> list[str]:
    proc = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=root)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def branch_in_worktree(branch: str, records: list[dict[str, str]]) -> bool:
    return any(rec.get("branch") == branch and Path(rec.get("path", "")).exists() for rec in records)


def git_status(path: Path) -> str:
    proc = run(["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"])
    return proc.stdout.strip() if proc.returncode == 0 else ""


def load_registry_statuses(root: Path) -> dict[str, str]:
    path = root / "orchestrator-state" / "tasks" / "registry.json"
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    tasks = registry.get("tasks") if isinstance(registry, dict) else None
    out: dict[str, str] = {}
    if isinstance(tasks, list):
        for item in tasks:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("id") or item.get("task_id") or "")
            if TASK_RE.fullmatch(tid):
                out[tid] = str(item.get("status") or "")
    elif isinstance(tasks, dict):
        for tid, item in tasks.items():
            if TASK_RE.fullmatch(str(tid)) and isinstance(item, dict):
                out[str(tid)] = str(item.get("status") or "")
    return out


def main_ref(root: Path, remote: str, main_branch: str) -> str:
    if run(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{remote}/{main_branch}"], cwd=root).returncode == 0:
        return f"{remote}/{main_branch}"
    return main_branch


def has_unique_patches(root: Path, base_ref: str, branch: str) -> tuple[bool, str]:
    proc = run(["git", "cherry", base_ref, branch], cwd=root)
    if proc.returncode != 0:
        # Conservative fallback: if we cannot compute patch equivalence, skip.
        return True, "git_cherry_failed"
    plus = [line for line in proc.stdout.splitlines() if line.startswith("+")]
    if plus:
        return True, f"unique_patches={len(plus)}"
    return False, "patch_equivalent_to_main"


def safe_live_status(status: str) -> bool:
    return status in LIVE_STATUSES


def remove_worktree(root: Path, path: Path) -> bool:
    proc = run(["git", "worktree", "remove", str(path)], cwd=root)
    if proc.returncode == 0:
        return True
    proc = run(["git", "worktree", "remove", "--force", str(path)], cwd=root)
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean local task branches/worktrees with no unique patches vs main")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--task", default="")
    parser.add_argument("--remote", default=os.environ.get("CLAUDE_GIT_REMOTE", "origin"))
    parser.add_argument("--main", default=os.environ.get("CLAUDE_GIT_MAIN_BRANCH") or os.environ.get("GIT_DEFAULT_BRANCH", "main"))
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        args.apply = False
    if args.task and not TASK_RE.fullmatch(args.task):
        print(f"ERROR: invalid TASK_ID: {args.task}", file=sys.stderr)
        return 2
    try:
        root = resolve_root(Path.cwd())
    except Exception as exc:
        say(f"cleanup-zombie-task-worktrees: git_repository=no reason={exc}", args.quiet)
        return 0

    base = main_ref(root, args.remote, args.main)
    statuses = load_registry_statuses(root)
    records = parse_worktrees(root)
    active = active_roots(root)
    current_branch = git_output(root, "rev-parse", "--abbrev-ref", "HEAD") if run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).returncode == 0 else ""

    matched = removed_wt = would_remove_wt = skipped_dirty = skipped_active = skipped_live = skipped_unique = branches_deleted = branches_skipped = would_delete_branches = 0

    for rec in records:
        branch = rec.get("branch", "")
        wt_raw = rec.get("path", "")
        if not branch_looks_task_scoped(branch) or not wt_raw:
            continue
        tid = task_id_from_branch(branch)
        if args.task and tid != args.task:
            continue
        status = statuses.get(tid, "")
        if safe_live_status(status):
            skipped_live += 1
            if args.verbose:
                say(f"skip live task worktree: {wt_raw} ({branch}) status={status}", args.quiet)
            continue
        unique, reason = has_unique_patches(root, base, branch)
        if unique:
            skipped_unique += 1
            if args.verbose:
                say(f"skip branch with unique patches: {branch} reason={reason}", args.quiet)
            continue
        matched += 1
        wt = Path(wt_raw)
        if not wt.exists():
            if args.apply:
                run(["git", "worktree", "prune"], cwd=root)
                removed_wt += 1
                say(f"pruned zombie worktree metadata: {wt_raw} ({branch})", args.quiet)
            else:
                would_remove_wt += 1
                say(f"would prune zombie worktree metadata: {wt_raw} ({branch})", args.quiet)
            continue
        if realpath(wt) in active:
            skipped_active += 1
            if args.verbose:
                say(f"skip active zombie candidate: {wt_raw} ({branch})", args.quiet)
            continue
        status_text = git_status(wt)
        if status_text:
            skipped_dirty += 1
            if args.verbose:
                say(f"skip dirty zombie candidate: {wt_raw} ({branch})", args.quiet, err=True)
                for line in status_text.splitlines()[:40]:
                    say(f"  {line}", args.quiet, err=True)
            continue
        if args.apply:
            if remove_worktree(root, wt):
                removed_wt += 1
                say(f"removed zombie task worktree: {wt_raw} ({branch})", args.quiet)
            else:
                skipped_dirty += 1
                say(f"skip zombie worktree remove failed: {wt_raw} ({branch})", args.quiet, err=True)
        else:
            would_remove_wt += 1
            say(f"would remove zombie task worktree: {wt_raw} ({branch})", args.quiet)

    records_after = parse_worktrees(root)
    for branch in local_branches(root):
        if not branch_looks_task_scoped(branch):
            continue
        tid = task_id_from_branch(branch)
        if args.task and tid != args.task:
            continue
        status = statuses.get(tid, "")
        if safe_live_status(status):
            branches_skipped += 1
            continue
        if branch in {current_branch, "main", "master"}:
            branches_skipped += 1
            continue
        if branch_in_worktree(branch, records_after):
            branches_skipped += 1
            continue
        unique, reason = has_unique_patches(root, base, branch)
        if unique:
            branches_skipped += 1
            if args.verbose:
                say(f"skip local branch with unique patches: {branch} reason={reason}", args.quiet)
            continue
        if args.apply:
            proc = run(["git", "branch", "-D", branch], cwd=root)
            if proc.returncode == 0:
                branches_deleted += 1
                say(f"deleted zombie task branch: {branch}", args.quiet)
            else:
                branches_skipped += 1
                say(f"skip local branch delete failed: {branch}", args.quiet, err=True)
        else:
            would_delete_branches += 1
            say(f"would delete zombie task branch: {branch}", args.quiet)

    if not args.quiet:
        mode = "apply" if args.apply else "dry-run"
        print(
            "cleanup-zombie-task-worktrees: "
            f"matched={matched} would_remove={would_remove_wt} removed={removed_wt} "
            f"skipped_dirty={skipped_dirty} skipped_active={skipped_active} skipped_live={skipped_live} "
            f"skipped_unique={skipped_unique} branches_deleted={branches_deleted} "
            f"branches_would_delete={would_delete_branches} branches_skipped={branches_skipped} "
            f"mode={mode} task={args.task or 'all'} base={base}"
        )
    if skipped_dirty:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
