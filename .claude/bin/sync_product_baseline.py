#!/usr/bin/env python3
"""Synchronize the cumulative source-of-truth into docs/base-app.

The orchestrator treats `docs/source-of-truth/` as the live cumulative product
contract. `docs/base-app/` is the built baseline snapshot passed back to
ChatGPT when planning the next increment (BaseApp + v1 + v2 + ...). The closer
runs this after a verified slice, before the atomic commit, so the baseline is
never stale and `/clear` never loses product context.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from common import (
    append_jsonl,
    discover_source_docs,
    ensure_parent,
    file_lock,
    ledger_path,
    now_iso,
    project_root,
    relpath,
    sha256_file,
    write_json,
)

MANIFEST_NAME = "BASELINE_MANIFEST.json"


def base_app_dir() -> Path:
    return project_root() / "docs" / "base-app"


def manifest_path() -> Path:
    return base_app_dir() / MANIFEST_NAME


def _load_manifest() -> dict[str, Any]:
    path = manifest_path()
    if not path.exists():
        return {
            "schema_version": 1,
            "purpose": "Cumulative built baseline snapshot for ChatGPT/source-of-truth increments.",
            "latest_version": None,
            "snapshots": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("manifest is not a JSON object")
        data.setdefault("schema_version", 1)
        data.setdefault("snapshots", [])
        return data
    except Exception:
        return {"schema_version": 1, "latest_version": None, "snapshots": [], "read_error": "manifest could not be parsed"}


def _chosen_docs() -> dict[str, Path]:
    docs = discover_source_docs(project_root())
    missing = [k for k in ("instructions", "guide", "checklist") if len(docs.get(k) or []) != 1]
    if missing:
        raise SystemExit(f"Need exactly one source doc for each core kind; invalid={missing} docs={docs}")
    chosen = {"instructions": docs["instructions"][0], "guide": docs["guide"][0], "checklist": docs["checklist"][0]}
    if len(docs.get("ux") or []) == 1:
        chosen["ux_contract"] = docs["ux"][0]
    if len(docs.get("stack_profile") or []) == 1:
        chosen["stack_profile"] = docs["stack_profile"][0]
    return chosen


def _target_for(kind: str, src: Path) -> Path:
    dest = base_app_dir()
    if kind == "instructions":
        return dest / "instrucciones.md"
    if kind == "ux_contract":
        return dest / "UX_CONTRACT.md"
    if kind == "stack_profile":
        return dest / "STACK_PROFILE.yaml"
    return dest / src.name


def _remove_stale_target(kind: str, keep: Path) -> None:
    patterns = {
        "guide": "*_TECHNICAL_GUIDE.md",
        "checklist": "*_IMPLEMENTATION_CHECKLIST.md",
        "ux_contract": "UX_CONTRACT.md",
        "stack_profile": "STACK_PROFILE.yaml",
    }
    pattern = patterns.get(kind)
    if not pattern:
        return
    for path in base_app_dir().glob(pattern):
        if path.resolve() != keep.resolve():
            path.unlink()


def _snapshot_docs() -> dict[str, Any]:
    docs = _chosen_docs()
    snapshot: dict[str, Any] = {}
    for kind, src in docs.items():
        target = _target_for(kind, src)
        snapshot[kind] = {
            "source": relpath(src),
            "target": relpath(target),
            "source_sha256": sha256_file(src),
            "target_sha256": sha256_file(target) if target.exists() else None,
            "in_sync": target.exists() and sha256_file(src) == sha256_file(target),
        }
    return snapshot


def status(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _load_manifest()
    docs = _snapshot_docs()
    return {
        "ok": True,
        "base_app_dir": relpath(base_app_dir()),
        "manifest": relpath(manifest_path()),
        "latest_version": manifest.get("latest_version"),
        "snapshot_count": len(manifest.get("snapshots") or []),
        "docs": docs,
        "all_in_sync": all(v.get("in_sync") for v in docs.values()),
    }


def sync(args: argparse.Namespace) -> dict[str, Any]:
    version = args.version or os.environ.get("PRODUCT_INCREMENT") or "current"
    task_id = args.task or os.environ.get("CLAUDE_ACTIVE_TASK_ID") or None
    reason = args.reason or "verified slice closed"
    base_app_dir().mkdir(parents=True, exist_ok=True)

    copied: dict[str, Any] = {}
    with file_lock(manifest_path()):
        docs = _chosen_docs()
        for kind, src in docs.items():
            target = _target_for(kind, src)
            ensure_parent(target)
            _remove_stale_target(kind, target)
            shutil.copy2(src, target)
            copied[kind] = {
                "source": relpath(src),
                "target": relpath(target),
                "sha256": sha256_file(target),
            }
        manifest = _load_manifest()
        entry = {
            "ts": now_iso(),
            "version": version,
            "task_id": task_id,
            "phase_id": args.phase,
            "reason": reason,
            "docs": copied,
        }
        manifest["latest_version"] = version
        manifest["latest_task_id"] = task_id
        manifest["updated_at"] = entry["ts"]
        snapshots = list(manifest.get("snapshots") or [])
        snapshots.append(entry)
        manifest["snapshots"] = snapshots[-200:]
        write_json(manifest_path(), manifest)
    append_jsonl(ledger_path(), {"ts": now_iso(), "event": "product_baseline_synced", "version": version, "task_id": task_id, "reason": reason, "docs": copied})
    return {"ok": True, "version": version, "task_id": task_id, "manifest": relpath(manifest_path()), "docs": copied}


def print_human(result: dict[str, Any]) -> None:
    if result.get("ok"):
        print("OK " + " ".join(f"{k}={v}" for k, v in result.items() if k not in {"ok", "docs"}))
        docs = result.get("docs") or {}
        for kind, item in docs.items():
            print(f"- {kind}: {item.get('source')} -> {item.get('target')} sync={item.get('in_sync', 'copied')} sha={item.get('sha256') or item.get('source_sha256')}")
    else:
        print("ERROR " + json.dumps(result, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync cumulative source-of-truth into docs/base-app baseline snapshot.")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("status", help="Compare docs/source-of-truth against docs/base-app.")
    sy = sub.add_parser("sync", help="Copy current source-of-truth docs into docs/base-app and append manifest entry.")
    sy.add_argument("--version", default=None, help="Product increment, e.g. baseapp, v1, v2, current.")
    sy.add_argument("--task", default=None, help="TASK_ID that triggered the sync; defaults to CLAUDE_ACTIVE_TASK_ID.")
    sy.add_argument("--phase", default=None)
    sy.add_argument("--reason", default=None)
    parser.add_argument("--json", action="store_true")
    for sp in (st, sy):
        sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "status":
        result = status(args)
    elif args.command == "sync":
        result = sync(args)
    else:  # pragma: no cover
        parser.error("unknown command")
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
