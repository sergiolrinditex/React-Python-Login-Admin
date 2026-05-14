#!/usr/bin/env python3
"""Keep local orchestrator runtime files from blocking Git transport.

Older installs may still have registry/runtime files tracked. In the current
contract they are local scheduler state. This guard lets pr-flow fast-forward
canonical main safely when the only dirty paths are local runtime files:
backup -> clean for merge -> restore -> mark tracked runtime skip-worktree.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

RUNTIME_EXACT = {
    "orchestrator-state/tasks/registry.json",
    "orchestrator-state/tasks/runtime-state.json",
    "orchestrator-state/tasks/ledger.jsonl",
    "orchestrator-state/tasks/bash-ledger.jsonl",
    "orchestrator-state/memory/PROGRESS.md",
    "orchestrator-state/memory/task-dag.json",
    "orchestrator-state/memory/task-dag.md",
    "orchestrator-state/memory/execution-graph.json",
    "orchestrator-state/memory/stack-profile.json",
    "orchestrator-state/memory/source-manifest.json",
    "orchestrator-state/hook-errors.log",
    "orchestrator-state/hook-info.log",
}
RUNTIME_PREFIXES = (
    "orchestrator-state/agent-memory/",
    "orchestrator-state/tasks/work-items/",
    "orchestrator-state/tasks/task-packs/",
    "orchestrator-state/tasks/handoffs/",
    "orchestrator-state/tasks/evidence/",
    "orchestrator-state/tasks/reports/",
    "orchestrator-state/tasks/follow-ups/",
    "orchestrator-state/tasks/source-doc-patches/",
    "orchestrator-state/tasks/cleanup-requests/",
    "orchestrator-state/memory/official-doc-notes/",
    "orchestrator-state/memory/archive/",
    "orchestrator-state/archive/",
    "orchestrator-state/dev-logs/",
)
# Intentionally NOT runtime: orchestrator-state/tasks/lifecycle-events/


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(root), text=True, capture_output=True, check=False, timeout=30)

LOCAL_EXCLUDES = [
    "orchestrator-state/archive/",
    "orchestrator-state/hook-info.log",
    "orchestrator-state/hook-errors.log",
]


def ensure_local_excludes(root: Path) -> None:
    git_dir_proc = _git(root, "rev-parse", "--git-dir")
    if git_dir_proc.returncode != 0:
        return
    git_dir = Path(git_dir_proc.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (root / git_dir).resolve()
    info = git_dir / "info"
    info.mkdir(parents=True, exist_ok=True)
    exclude = info / "exclude"
    existing = exclude.read_text(encoding="utf-8", errors="replace") if exclude.exists() else ""
    additions = [item for item in LOCAL_EXCLUDES if item not in existing.splitlines()]
    if additions:
        with exclude.open("a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            for item in additions:
                fh.write(item + "\n")

def _status_entries(root: Path) -> list[dict[str, str]]:
    proc = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git status failed")
    raw = proc.stdout
    if not raw:
        return []
    parts = raw.split("\0")
    entries: list[dict[str, str]] = []
    i = 0
    while i < len(parts):
        item = parts[i]
        i += 1
        if not item:
            continue
        code = item[:2]
        path = item[3:] if len(item) > 3 else ""
        if code.startswith("R") or code.startswith("C"):
            # porcelain -z emits dest then source; use dest for classification.
            if i < len(parts):
                i += 1
        if path:
            entries.append({"code": code, "path": path})
    return entries


def _is_runtime(path: str) -> bool:
    norm = path.replace("\\", "/").lstrip("./")
    return norm in RUNTIME_EXACT or norm.startswith(RUNTIME_PREFIXES)


def _copy_path(src: Path, dst: Path) -> None:
    if src.is_dir() and not src.is_symlink():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=True)
    elif src.exists() or src.is_symlink():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=False)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def protect(root: Path, paths: list[str] | None = None) -> list[str]:
    ensure_local_excludes(root)
    protected: list[str] = []
    candidates = paths or sorted(RUNTIME_EXACT)
    for rel in candidates:
        if not _is_runtime(rel):
            continue
        if _git(root, "ls-files", "--error-unmatch", rel).returncode == 0:
            _git(root, "update-index", "--skip-worktree", "--", rel)
            protected.append(rel)
    return protected


def backup(root: Path) -> dict[str, Any]:
    ensure_local_excludes(root)
    entries = _status_entries(root)
    non_runtime = [e for e in entries if not _is_runtime(e["path"])]
    if non_runtime:
        return {"ok": False, "reason": "non_runtime_dirty", "non_runtime": non_runtime, "runtime": [e for e in entries if _is_runtime(e["path"])]}
    if not entries:
        protected = protect(root)
        return {"ok": True, "backup_dir": "", "paths": [], "protected": protected}

    ts = subprocess.run(["date", "-u", "+%Y%m%dT%H%M%SZ"], text=True, capture_output=True, check=False).stdout.strip() or "runtime"
    backup_dir = root / "orchestrator-state" / "archive" / f"runtime-git-sync-{ts}-{os.getpid()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "orquestador.runtime-git-guard.v1", "paths": [], "root": str(root)}
    protected = protect(root, [e["path"] for e in entries])

    for entry in entries:
        rel = entry["path"]
        src = root / rel
        dst = backup_dir / rel
        if src.exists() or src.is_symlink():
            _copy_path(src, dst)
            manifest["paths"].append({"path": rel, "code": entry["code"], "existed": True})
        else:
            manifest["paths"].append({"path": rel, "code": entry["code"], "existed": False})

        if _git(root, "ls-files", "--error-unmatch", rel).returncode == 0:
            _git(root, "restore", "--staged", "--worktree", "--", rel)
        else:
            _remove_path(src)

    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "backup_dir": str(backup_dir), "paths": [e["path"] for e in entries], "protected": protected}


def restore(root: Path, backup_dir: Path) -> dict[str, Any]:
    ensure_local_excludes(root)
    manifest_path = backup_dir / "manifest.json"
    if not backup_dir or not manifest_path.exists():
        return {"ok": True, "restored": [], "reason": "no_backup"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored: list[str] = []
    for item in manifest.get("paths", []) or []:
        rel = str(item.get("path") or "")
        if not rel or not _is_runtime(rel) or not item.get("existed"):
            continue
        protect(root, [rel])
        src = backup_dir / rel
        dst = root / rel
        if src.exists() or src.is_symlink():
            _copy_path(src, dst)
            restored.append(rel)
    return {"ok": True, "backup_dir": str(backup_dir), "restored": restored, "protected": protect(root, restored)}


def _print_lines(result: dict[str, Any]) -> None:
    if result.get("ok"):
        print("RUNTIME_GIT_GUARD_READY: yes")
    else:
        print("RUNTIME_GIT_GUARD_READY: no")
    if result.get("backup_dir"):
        print(f"RUNTIME_BACKUP_DIR: {result['backup_dir']}")
    if result.get("paths"):
        print(f"RUNTIME_PATHS_BACKED_UP: {len(result['paths'])}")
    if result.get("restored"):
        print(f"RUNTIME_PATHS_RESTORED: {len(result['restored'])}")
    if result.get("protected"):
        print(f"RUNTIME_PATHS_PROTECTED: {len(result['protected'])}")
    if result.get("non_runtime"):
        for entry in result["non_runtime"]:
            print(f"DIRTY_NON_RUNTIME: {entry['code']} {entry['path']}")
    if result.get("reason"):
        print(f"Reason: {result['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup/restore local runtime files around canonical main sync.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("backup", "protect"):
        sp = sub.add_parser(name)
        sp.add_argument("--root", default=".")
        sp.add_argument("--json", action="store_true")
    sp = sub.add_parser("restore")
    sp.add_argument("--root", default=".")
    sp.add_argument("--backup-dir", required=True)
    sp.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.cmd == "backup":
        result = backup(root)
    elif args.cmd == "restore":
        result = restore(root, Path(args.backup_dir).resolve())
    else:
        result = {"ok": True, "protected": protect(root)}
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_lines(result)
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
