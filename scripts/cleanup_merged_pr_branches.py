#!/usr/bin/env python3
"""Safely delete remote task branches after their GitHub PR is merged.

This cleans the third Git layer that local worktree cleanup cannot touch:
remote branches such as origin/dev/P04-S01-T004 that remain after squash merge.
It is deliberately conservative:
- requires gh CLI;
- only considers task-scoped branch names;
- only deletes when GitHub reports a MERGED PR for that exact head branch;
- only deletes if the current remote branch SHA still equals the PR headRefOid.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TASK_RE = re.compile(r"P\d{2,}-S\d{2,}-T\d{3,}")
BRANCH_PREFIXES = ("dev/", "feature/", "fix/", "bugfix/", "chore/", "hotfix/")
PROTECTED_BRANCHES = {"", "HEAD", "main", "master", "develop", "dev", "release", "staging", "production"}


@dataclass(frozen=True)
class Candidate:
    branch: str
    tracking_ref: str
    sha: str
    task_id: str


@dataclass(frozen=True)
class PrDecision:
    action: str
    reason: str = ""
    pr_number: str = ""
    pr: dict[str, Any] | None = None


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    # Housekeeping must never block waiting for credentials in next-wave.
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def say(message: str, quiet: bool = False, err: bool = False) -> None:
    if quiet:
        return
    print(message, file=sys.stderr if err else sys.stdout)


def git_output(args: list[str], cwd: Path) -> str:
    proc = run(["git", *args], cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def resolve_root(start: Path) -> Path:
    top = Path(git_output(["rev-parse", "--show-toplevel"], start))
    common = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=top)
    if common.returncode == 0:
        common_path = Path(common.stdout.strip())
        if common_path.name == ".git" and common_path.parent.exists():
            return common_path.parent.resolve()
    return top.resolve()


def task_id_from_branch(branch: str) -> str:
    match = TASK_RE.search(branch)
    return match.group(0) if match else ""


def looks_task_branch(branch: str) -> bool:
    if branch in PROTECTED_BRANCHES or branch.startswith("HEAD"):
        return False
    tid = task_id_from_branch(branch)
    if not tid:
        return False
    if branch == tid:
        return True
    return branch.startswith(BRANCH_PREFIXES)


def branch_is_task_scoped(branch: str) -> bool:
    return looks_task_branch(branch)


def list_remote_candidates(root: Path, remote: str, task_filter: str = "") -> list[Candidate]:
    proc = run(["git", "for-each-ref", "--format=%(refname:short) %(objectname)", f"refs/remotes/{remote}"], cwd=root)
    if proc.returncode != 0:
        return []
    out: list[Candidate] = []
    prefix = f"{remote}/"
    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ref, sha = raw.split(maxsplit=1)
        except ValueError:
            continue
        if ref == f"{remote}/HEAD" or not ref.startswith(prefix):
            continue
        branch = ref[len(prefix) :]
        if not looks_task_branch(branch):
            continue
        tid = task_id_from_branch(branch)
        if task_filter and tid != task_filter:
            continue
        out.append(Candidate(branch=branch, tracking_ref=ref, sha=sha.strip(), task_id=tid))
    return out


def gh_prs_for_branch(root: Path, branch: str) -> tuple[list[dict[str, Any]], str]:
    proc = run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--head",
            branch,
            "--json",
            "number,state,headRefName,headRefOid,baseRefName,mergedAt,url",
            "--limit",
            "20",
        ],
        cwd=root,
    )
    if proc.returncode != 0:
        return [], proc.stderr.strip() or proc.stdout.strip() or "gh pr list failed"
    try:
        payload = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        return [], f"gh pr list returned invalid JSON: {exc}"
    if not isinstance(payload, list):
        return [], "gh pr list returned non-list JSON"
    return [item for item in payload if isinstance(item, dict)], ""


def choose_pr_decision(branch: str, sha: str, prs: list[dict[str, Any]], base_branch: str = "main") -> PrDecision:
    matches = [item for item in prs if isinstance(item, dict) and item.get("headRefName") == branch]
    if not matches:
        return PrDecision(action="skip", reason="no_pr_for_head_branch")
    merged = [item for item in matches if str(item.get("state") or "").upper() == "MERGED" or item.get("mergedAt")]
    if not merged:
        states = {str(item.get("state") or "unknown").lower() for item in matches}
        state = sorted(states)[0] if states else "unknown"
        return PrDecision(action="skip", reason=f"pr_not_merged_{state}", pr=matches[0], pr_number=str(matches[0].get("number") or ""))
    same_base = [item for item in merged if not item.get("baseRefName") or item.get("baseRefName") == base_branch]
    if not same_base:
        return PrDecision(action="skip", reason="pr_base_mismatch", pr=merged[0], pr_number=str(merged[0].get("number") or ""))
    same_base.sort(key=lambda item: int(item.get("number") or 0), reverse=True)
    pr = same_base[0]
    head_oid = str(pr.get("headRefOid") or "")
    if not head_oid:
        return PrDecision(action="skip", reason="missing_head_oid", pr=pr, pr_number=str(pr.get("number") or ""))
    if head_oid != sha:
        return PrDecision(action="skip", reason="branch_moved_after_pr_merge", pr=pr, pr_number=str(pr.get("number") or ""))
    return PrDecision(action="delete", pr=pr, pr_number=str(pr.get("number") or ""))


def cleanup_remote_branch(root: Path, remote: str, candidate: Candidate, *, apply: bool, quiet: bool, base_branch: str) -> tuple[str, str]:
    prs, error = gh_prs_for_branch(root, candidate.branch)
    if error:
        return "skipped_no_pr", f"skip gh_pr_query_failed: {candidate.tracking_ref} reason={error}"
    decision = choose_pr_decision(candidate.branch, candidate.sha, prs, base_branch)
    if decision.action != "delete":
        return "skipped", f"skip {decision.reason}: {candidate.tracking_ref}"
    label = f" PR #{decision.pr_number}" if decision.pr_number else ""
    if not apply:
        return "would_delete", f"would delete merged PR branch: {candidate.tracking_ref}{label}"
    proc = run(["git", "push", remote, "--delete", candidate.branch], cwd=root)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "delete failed").strip().splitlines()[0]
        return "failed", f"failed delete: {candidate.tracking_ref}{label} reason={detail}"
    return "deleted", f"deleted merged PR branch: {candidate.tracking_ref}{label}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete remote task branches whose GitHub PR is already merged")
    parser.add_argument("--apply", action="store_true", help="delete safe merged remote branches")
    parser.add_argument("--dry-run", action="store_true", help="show what would be deleted")
    parser.add_argument("--remote", default=os.environ.get("CLAUDE_GIT_REMOTE", "origin"), help="git remote name")
    parser.add_argument("--base", default=os.environ.get("GIT_DEFAULT_BRANCH", "main"), help="PR base branch to consider")
    parser.add_argument("--task", default="", help="limit cleanup to one TASK_ID")
    parser.add_argument("--branch", action="append", default=[], help="limit cleanup to exact remote branch name, e.g. dev/P00-S01-T001")
    parser.add_argument("--quiet", action="store_true", help="suppress normal output")
    parser.add_argument("--verbose", action="store_true", help="print skipped branch diagnostics")
    args = parser.parse_args(argv)

    if args.dry_run:
        args.apply = False
    if args.task and not TASK_RE.fullmatch(args.task):
        print(f"ERROR: invalid TASK_ID: {args.task}", file=sys.stderr)
        return 2
    try:
        root = resolve_root(Path.cwd())
    except Exception as exc:
        say(f"cleanup-merged-pr-branches: git_repository=no reason={exc}", args.quiet)
        return 0
    if run(["git", "remote", "get-url", args.remote], cwd=root).returncode != 0:
        say(f"cleanup-merged-pr-branches: remote={args.remote} not_configured", args.quiet)
        return 0
    if shutil.which("gh") is None or run(["gh", "--version"], cwd=root).returncode != 0:
        say("cleanup-merged-pr-branches: gh_cli=missing; remote branch cleanup skipped", args.quiet)
        return 0

    fetch = run(["git", "fetch", args.remote, "--prune"], cwd=root)
    if fetch.returncode != 0:
        say(f"cleanup-merged-pr-branches: fetch_prune=failed remote={args.remote}; skipped", args.quiet, err=True)
        if args.verbose:
            say((fetch.stderr or fetch.stdout).strip(), args.quiet, err=True)
        return 0
    candidates = list_remote_candidates(root, args.remote, args.task)
    if args.branch:
        allowed = set(args.branch)
        candidates = [candidate for candidate in candidates if candidate.branch in allowed]

    counts: dict[str, int] = {"candidates": len(candidates), "would_delete": 0, "deleted": 0, "skipped": 0, "failed": 0}
    for candidate in candidates:
        status, message = cleanup_remote_branch(root, args.remote, candidate, apply=bool(args.apply), quiet=args.quiet, base_branch=args.base)
        counts[status] = counts.get(status, 0) + 1
        if message and (args.verbose or status in {"would_delete", "deleted", "failed"}):
            say(message, args.quiet, err=status == "failed")

    if args.apply and counts.get("deleted", 0):
        run(["git", "fetch", args.remote, "--prune"], cwd=root)
    if not args.quiet:
        print(
            "cleanup-merged-pr-branches: "
            f"remote={args.remote} base={args.base} candidates={counts['candidates']} "
            f"would_delete={counts['would_delete']} deleted={counts['deleted']} "
            f"skipped={counts['skipped']} failed={counts['failed']} "
            f"mode={'apply' if args.apply else 'dry-run'} task={args.task or 'all'}"
        )
    return 3 if counts.get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
