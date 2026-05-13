#!/usr/bin/env python3
"""Synchronize the cumulative source-of-truth into docs/product-baseline.

The orchestrator treats `docs/source-of-truth/` as the live cumulative product
contract. `docs/product-baseline/` is the built baseline snapshot passed back to
ChatGPT when planning the next increment (v0/v1/v2/current). The closer
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
    workspace_root,
    relpath,
    sha256_file,
)
try:
    from check_handoff_contract import validate as validate_handoff_contract
except Exception:  # pragma: no cover - optional import guard
    validate_handoff_contract = None  # type: ignore[assignment]

MANIFEST_NAME = "BASELINE_MANIFEST.json"


def baseline_dir() -> Path:
    # Versioned product snapshot belongs to the current task checkout/branch,
    # not necessarily the canonical state repo. In pr-flow the closer runs from
    # a per-TASK_ID worktree and must commit this snapshot on that branch.
    return workspace_root() / "docs" / "product-baseline"


def manifest_path() -> Path:
    return baseline_dir() / MANIFEST_NAME


def baseline_lock_path() -> Path:
    # Keep lock files out of docs/product-baseline so a broad `git add docs/`
    # cannot accidentally commit an fcntl sidecar.
    return project_root() / "orchestrator-state" / "tasks" / "locks" / "product-baseline.json"


def _load_manifest() -> dict[str, Any]:
    path = manifest_path()
    if not path.exists():
        return {
            "schema_version": 1,
            "purpose": "Cumulative built product-baseline snapshot for future ChatGPT/source-of-truth increments.",
            "writer": "sync_product_baseline.py",
            "source_pack_contract": "five-file source-of-truth pack",
            "latest_version": None,
            "snapshots": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("manifest is not a JSON object")
        data.setdefault("schema_version", 1)
        data.setdefault("purpose", "Cumulative built product-baseline snapshot for future ChatGPT/source-of-truth increments.")
        data.setdefault("writer", "sync_product_baseline.py")
        data.setdefault("source_pack_contract", "five-file source-of-truth pack")
        data.setdefault("snapshots", [])
        return data
    except Exception:
        return {
            "schema_version": 1,
            "purpose": "Cumulative built product-baseline snapshot for future ChatGPT/source-of-truth increments.",
            "writer": "sync_product_baseline.py",
            "source_pack_contract": "five-file source-of-truth pack",
            "latest_version": None,
            "snapshots": [],
            "read_error": "manifest could not be parsed",
        }


def _workspace_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root().resolve()).as_posix()
    except Exception:
        return relpath(path)


def _chosen_docs() -> dict[str, Path]:
    docs = discover_source_docs(workspace_root())
    required = ("instructions", "guide", "checklist", "ux", "stack_profile")
    invalid = [k for k in required if len(docs.get(k) or []) != 1]
    if invalid:
        raise ValueError(
            "Need exactly one source doc for each five-file source-of-truth kind "
            f"before syncing product-baseline; invalid={invalid} docs={docs}"
        )
    return {
        "instructions": docs["instructions"][0],
        "guide": docs["guide"][0],
        "checklist": docs["checklist"][0],
        "ux_contract": docs["ux"][0],
        "stack_profile": docs["stack_profile"][0],
    }


def _target_for(kind: str, src: Path) -> Path:
    dest = baseline_dir()
    if kind == "instructions":
        return dest / "instrucciones.md"
    if kind == "ux_contract":
        return dest / "UX_CONTRACT.md"
    if kind == "stack_profile":
        return dest / "STACK_PROFILE.yaml"
    return dest / src.name




def _write_manifest_unlocked(manifest: dict[str, Any]) -> None:
    """Atomically write manifest while the product-baseline lock is held.

    Do not call common.write_json here: that helper creates a lock sidecar next
    to BASELINE_MANIFEST.json, and docs/product-baseline must not contain
    ephemeral `.lock` files that could be committed as product history.
    """
    path = manifest_path()
    ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


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
    for path in baseline_dir().glob(pattern):
        if path.resolve() != keep.resolve():
            path.unlink()


def _snapshot_docs() -> dict[str, Any]:
    docs = _chosen_docs()
    snapshot: dict[str, Any] = {}
    for kind, src in docs.items():
        target = _target_for(kind, src)
        snapshot[kind] = {
            "source": _workspace_rel(src),
            "target": _workspace_rel(target),
            "source_sha256": sha256_file(src),
            "target_sha256": sha256_file(target) if target.exists() else None,
            "in_sync": target.exists() and sha256_file(src) == sha256_file(target),
        }
    return snapshot


def _require_verified_close_context(args: argparse.Namespace) -> None:
    """Prevent product-baseline from being synced by arbitrary workers.

    The baseline is a built snapshot for the next planning pass. It must only be
    updated after a verified slice close, normally by the closer. For exceptional
    manual migrations, require an explicit --allow-unverified flag so accidental
    `sync` calls from planner/developer/tester do not make unfinished work look
    like baseline.
    """
    if getattr(args, "allow_unverified", False):
        return
    task_id = args.task or os.environ.get("CLAUDE_ACTIVE_TASK_ID") or None
    if not task_id:
        raise SystemExit(
            "Refusing product-baseline sync without --task. "
            "Use closer after /verify-slice, or pass --allow-unverified for an explicit manual migration."
        )
    if validate_handoff_contract is None:
        raise SystemExit("Refusing product-baseline sync: handoff validator is unavailable.")
    ok, errors, _details = validate_handoff_contract(
        str(task_id),
        require_ready_for_close=True,
        require_verify_slice=True,
        require_screen_journey_review=False,
    )
    if not ok:
        raise SystemExit(
            "Refusing product-baseline sync before verified close for "
            f"{task_id}: " + "; ".join(errors)
        )


def status(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _load_manifest()
    try:
        docs = _snapshot_docs()
        source_pack_ready = True
        source_pack_error = None
    except ValueError as exc:
        docs = {}
        source_pack_ready = False
        source_pack_error = str(exc)
    return {
        "ok": True,
        "baseline_dir": _workspace_rel(baseline_dir()),
        "manifest": _workspace_rel(manifest_path()),
        "latest_version": manifest.get("latest_version"),
        "snapshot_count": len(manifest.get("snapshots") or []),
        "source_pack_ready": source_pack_ready,
        "source_pack_error": source_pack_error,
        "docs": docs,
        "all_in_sync": bool(docs) and all(v.get("in_sync") for v in docs.values()),
    }



def sync(args: argparse.Namespace) -> dict[str, Any]:
    _require_verified_close_context(args)
    version = args.version or os.environ.get("PRODUCT_INCREMENT") or "current"
    task_id = args.task or os.environ.get("CLAUDE_ACTIVE_TASK_ID") or None
    reason = args.reason or "verified slice closed"
    baseline_dir().mkdir(parents=True, exist_ok=True)

    copied: dict[str, Any] = {}
    with file_lock(baseline_lock_path()):
        try:
            docs = _chosen_docs()
        except ValueError as exc:
            raise SystemExit(str(exc))
        for kind, src in docs.items():
            target = _target_for(kind, src)
            ensure_parent(target)
            _remove_stale_target(kind, target)
            shutil.copy2(src, target)
            copied[kind] = {
                "source": _workspace_rel(src),
                "target": _workspace_rel(target),
                "sha256": sha256_file(target),
            }
        manifest = _load_manifest()
        entry = {
            "ts": now_iso(),
            "version": version,
            "task_id": task_id,
            "phase_id": args.phase,
            "reason": reason,
            "writer": "sync_product_baseline.py",
            "source_pack": "five-file",
            "written_paths": sorted(item["target"] for item in copied.values()),
            "docs": copied,
        }
        manifest["writer"] = "sync_product_baseline.py"
        manifest["source_pack_contract"] = "five-file source-of-truth pack"
        manifest["latest_version"] = version
        manifest["latest_task_id"] = task_id
        manifest["updated_at"] = entry["ts"]
        manifest["last_written_paths"] = entry["written_paths"]
        snapshots = list(manifest.get("snapshots") or [])
        snapshots.append(entry)
        manifest["snapshots"] = snapshots[-200:]
        _write_manifest_unlocked(manifest)
    append_jsonl(ledger_path(), {"ts": now_iso(), "event": "product_baseline_synced", "writer": "sync_product_baseline.py", "version": version, "task_id": task_id, "reason": reason, "docs": copied})
    return {"ok": True, "version": version, "task_id": task_id, "manifest": _workspace_rel(manifest_path()), "docs": copied}


def print_human(result: dict[str, Any]) -> None:
    if result.get("ok"):
        print("OK " + " ".join(f"{k}={v}" for k, v in result.items() if k not in {"ok", "docs"}))
        docs = result.get("docs") or {}
        for kind, item in docs.items():
            print(f"- {kind}: {item.get('source')} -> {item.get('target')} sync={item.get('in_sync', 'copied')} sha={item.get('sha256') or item.get('source_sha256')}")
    else:
        print("ERROR " + json.dumps(result, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync verified five-file source-of-truth into docs/product-baseline baseline snapshot.")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("status", help="Compare docs/source-of-truth against docs/product-baseline.")
    sy = sub.add_parser("sync", help="Copy verified current source-of-truth docs into docs/product-baseline and append manifest entry.")
    sy.add_argument("--version", default=None, help="Product increment, e.g. v0, v1, v2, current.")
    sy.add_argument("--task", default=None, help="TASK_ID that triggered the sync; defaults to CLAUDE_ACTIVE_TASK_ID.")
    sy.add_argument("--phase", default=None)
    sy.add_argument("--reason", default=None)
    sy.add_argument("--allow-unverified", action="store_true", help="Maintenance-only escape hatch; closer should never use this.")
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
