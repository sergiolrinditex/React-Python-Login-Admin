#!/usr/bin/env python3
"""Guard staged product deletions for a single DAG task.

A task write_set is a scheduling/editing scope, not permission to remove files.
Destructive deletions must be explicitly declared via task.delete_set (or one of
its compatibility aliases) so stale worktrees and broad globs do not erase
unrelated product modules during closer/git-add-slice.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DELETE_KEYS = ("delete_set", "allowed_deletions", "remove_set", "expected_deletions")
DESTRUCTIVE_EDIT_KEYS = ("destructive_edit_set", "allowed_destructive_edits", "destructive_refactor_set")
SAFE_DELETE_PATTERNS = ("**/.gitkeep", ".gitkeep")
SHARED_RISK_PATTERNS = (
    "**/errors.ts",
    "**/errors.tsx",
    "**/errors.py",
    "**/exceptions.py",
    "**/auth/**",
    "**/chat/**",
    "**/security/**",
    "**/router/**",
    "**/routes/**",
    "**/navigation/**",
    "**/providers/**",
    "**/context/**",
    "**/store/**",
)
STRUCTURAL_DELETE_RE = re.compile(r"^[-]\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|type|enum|function|const|def)\b")
MAX_SHARED_RISK_DELETED_LINES = 25


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, timeout=30)


def load_task(registry_path: Path, task_id: str) -> dict[str, Any]:
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERROR: registry.json not found at {registry_path}")
    tasks = registry.get("tasks") or []
    if isinstance(tasks, dict):
        task = tasks.get(task_id)
        if isinstance(task, dict):
            return task
    for task in tasks:
        if isinstance(task, dict) and task.get("id") == task_id:
            return task
    raise SystemExit(f"ERROR: TASK_ID {task_id} not found in registry.json")


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        raw = value.replace("\n", ";")
        return [part.strip() for part in raw.split(";") if part.strip()]
    return []


def patterns_from_keys(task: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    patterns: list[str] = []
    for key in keys:
        for item in as_list(task.get(key)):
            if item not in patterns:
                patterns.append(item)
    return patterns


def deletion_patterns(task: dict[str, Any]) -> list[str]:
    return patterns_from_keys(task, DELETE_KEYS)


def destructive_edit_patterns(task: dict[str, Any]) -> list[str]:
    return patterns_from_keys(task, DESTRUCTIVE_EDIT_KEYS)


def normalize(path: str) -> str:
    return path.strip().replace("\\", "/").lstrip("./")


def pattern_matches(pattern: str, path: str) -> bool:
    pat = normalize(pattern)
    rel = normalize(path)
    if not pat:
        return False
    if pat == rel:
        return True
    if pat.endswith("/"):
        pat = pat + "**"
    if pat.endswith("/**"):
        prefix = pat[:-3].rstrip("/")
        if rel == prefix or rel.startswith(prefix + "/"):
            return True
    return fnmatch.fnmatchcase(rel, pat)


def staged_deletions(cwd: Path) -> list[str]:
    result = run_git(["diff", "--cached", "--name-status", "--diff-filter=D"], cwd)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "ERROR: git diff --cached failed")
    deletions: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].startswith("D"):
            deletions.append(normalize(parts[1]))
    return deletions



def staged_shared_risk_destructive_edits(cwd: Path, allowed_patterns: list[str]) -> list[dict[str, Any]]:
    """Return staged edits that remove too much from shared-risk files.

    This catches regressions where a slice edits a shared file (for example
    errors.ts/auth/chat) and accidentally strips existing exports/classes while
    still staying inside write_set. It is deliberately limited to shared-risk
    paths and can be bypassed only by declaring destructive_edit_set for the
    TASK_ID.
    """
    result = run_git(["diff", "--cached", "--numstat"], cwd)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "ERROR: git diff --cached --numstat failed")
    candidates: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, deleted_raw, path_raw = parts[0], parts[1], parts[2]
        if added_raw == "-" or deleted_raw == "-":
            continue
        try:
            deleted = int(deleted_raw)
        except ValueError:
            continue
        path = normalize(path_raw)
        if deleted <= 0:
            continue
        if not any(pattern_matches(pat, path) for pat in SHARED_RISK_PATTERNS):
            continue
        if any(pattern_matches(pat, path) for pat in allowed_patterns):
            continue
        if deleted >= MAX_SHARED_RISK_DELETED_LINES:
            candidates.append(path)
            continue
        patch = run_git(["diff", "--cached", "--", path], cwd)
        if patch.returncode == 0 and any(STRUCTURAL_DELETE_RE.match(l) for l in patch.stdout.splitlines()):
            candidates.append(path)

    out: list[dict[str, Any]] = []
    for path in sorted(set(candidates)):
        numstat = run_git(["diff", "--cached", "--numstat", "--", path], cwd).stdout.strip()
        deleted_lines = None
        added_lines = None
        if numstat:
            fields = numstat.split("\t")
            if len(fields) >= 2 and fields[0].isdigit() and fields[1].isdigit():
                added_lines = int(fields[0])
                deleted_lines = int(fields[1])
        out.append({"path": path, "added_lines": added_lines, "deleted_lines": deleted_lines})
    return out

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Block staged deletions not explicitly declared for a DAG task")
    parser.add_argument("task_id")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--unstage", action="store_true", help="unstage violating deletions before exiting non-zero")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    task = load_task(Path(args.registry), args.task_id)
    explicit = deletion_patterns(task)
    destructive_explicit = destructive_edit_patterns(task)
    allowed = list(SAFE_DELETE_PATTERNS) + explicit
    destructive_allowed = allowed + destructive_explicit
    deletions = staged_deletions(repo)
    violations = [path for path in deletions if not any(pattern_matches(pat, path) for pat in allowed)]
    destructive_violations = staged_shared_risk_destructive_edits(repo, destructive_allowed)
    if not violations and not destructive_violations:
        return 0

    if args.unstage:
        if violations:
            run_git(["restore", "--staged", "--", *violations], repo)
        if destructive_violations:
            run_git(["restore", "--staged", "--", *[item["path"] for item in destructive_violations]], repo)

    if violations:
        print("ERROR: staged file deletion(s) are not declared for this TASK_ID.", file=sys.stderr)
        print("A task write_set allows edits/creates; deletion is destructive and needs explicit delete_set/allowed_deletions.", file=sys.stderr)
        print(f"TASK_ID: {args.task_id}", file=sys.stderr)
        if explicit:
            print("Declared deletion patterns:", file=sys.stderr)
            for pat in explicit:
                print(f"  - {pat}", file=sys.stderr)
        else:
            print("Declared deletion patterns: none", file=sys.stderr)
        print("Blocked staged deletions:", file=sys.stderr)
        for path in violations:
            print(f"  - {path}", file=sys.stderr)
        print("", file=sys.stderr)
        print("If accidental, restore with:", file=sys.stderr)
        print("  git restore --staged --worktree -- <path>...", file=sys.stderr)
        print("If intentional, declare delete_set for the task in source-of-truth/registry and rerun git-add-slice.", file=sys.stderr)
    if destructive_violations:
        print("ERROR: staged destructive edit(s) in shared-risk files are not declared for this TASK_ID.", file=sys.stderr)
        print("A write_set allows edits, but large/structural removals in shared files need destructive_edit_set/allowed_destructive_edits.", file=sys.stderr)
        print(f"TASK_ID: {args.task_id}", file=sys.stderr)
        if destructive_explicit:
            print("Declared destructive edit patterns:", file=sys.stderr)
            for pat in destructive_explicit:
                print(f"  - {pat}", file=sys.stderr)
        else:
            print("Declared destructive edit patterns: none", file=sys.stderr)
        print("Blocked staged destructive edits:", file=sys.stderr)
        for item in destructive_violations:
            extra = ""
            if item.get("deleted_lines") is not None:
                extra = f" (deleted_lines={item.get('deleted_lines')} added_lines={item.get('added_lines')})"
            print(f"  - {item['path']}{extra}", file=sys.stderr)
        print("If intentional, declare destructive_edit_set for the task and require human visual verification.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
