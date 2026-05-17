#!/usr/bin/env python3
"""Compact long per-agent MEMORY.md files without losing information.

Dry-run by default. With --apply, the original MEMORY.md is copied byte-for-
byte to orchestrator-state/agent-memory/<agent>/archive/MEMORY.full.<ts>.md
before MEMORY.md is replaced by a short operational index that points to the
full archive.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_THRESHOLD_LINES = 250

KEYWORDS_BY_AGENT: dict[str, list[str]] = {
    "developer": [
        "explicit_dag", "DAG", "bootstrap", "--refresh", "--reset-runtime-state",
        "registry", "runtime", "task-dag", "CLAUDE_ACTIVE_TASK_ID", "CLAUDE_TASK_PACK",
        "allowed_paths", "Write set", "write_set", "docker-compose", "Dockerfile",
        ".env.example", ".github/workflows", "follow-up", "register-followup",
        "OUTCOME", "NEXT_STATUS", "validator_tester_pending", "success", "blocked", "failed",
    ],
    "official-docs-researcher": [
        "official", "documentation", "docs", "version", "Context7", "MCP", "ToolSearch",
        "WebFetch", "WebSearch", "fan-out", "parallel", "Supabase", "GoRouter",
        "Riverpod", "verified", "discrepancy", "insufficient", "OUTCOME", "researched",
    ],
}

COMMON_KEYWORDS = [
    "decision", "invariant", "must", "never", "always", "gotcha", "failure", "risk",
    "contract", "trailer", "OUTCOME", "NEXT_STATUS", "source-of-truth", "DAG",
]

ROLE_TRAILERS: dict[str, tuple[str, str]] = {
    "developer": ("success|blocked|failed", "validator_tester_pending|blocked"),
    "official-docs-researcher": ("verified|discrepancy|insufficient", "<none>"),
}

@dataclass
class Candidate:
    agent: str
    path: Path
    line_count: int
    byte_count: int
    should_compact: bool


def repo_root() -> Path:
    return Path.cwd().resolve()


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def discover(agent: str | None, threshold: int) -> list[Candidate]:
    base = repo_root() / "orchestrator-state" / "agent-memory"
    paths: list[Path]
    if agent:
        paths = [base / agent / "MEMORY.md"]
    else:
        paths = sorted(base.glob("*/MEMORY.md")) if base.is_dir() else []
    candidates: list[Candidate] = []
    for path in paths:
        if not path.is_file():
            continue
        n_lines = count_lines(path)
        candidates.append(Candidate(
            agent=path.parent.name,
            path=path,
            line_count=n_lines,
            byte_count=path.stat().st_size,
            should_compact=n_lines > threshold,
        ))
    return candidates


def extract_headings(text: str, limit: int = 80) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(stripped)
        if len(headings) >= limit:
            break
    return headings


def interesting_lines(agent: str, text: str, limit: int = 80) -> list[str]:
    keywords = [*KEYWORDS_BY_AGENT.get(agent, []), *COMMON_KEYWORDS]
    seen: set[str] = set()
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) > 220:
            continue
        hay = line.lower()
        if any(k.lower() in hay for k in keywords):
            normalized = " ".join(line.split())
            if normalized not in seen:
                seen.add(normalized)
                out.append(line)
        if len(out) >= limit:
            break
    return out


def compact_text(agent: str, original: str, archive_rel: str, original_lines: int, original_sha: str, timestamp: str) -> str:
    headings = extract_headings(original)
    highlights = interesting_lines(agent, original)
    out: list[str] = []
    out.append(f"# {agent} agent memory")
    out.append("")
    out.append("Compact operational memory. No history was deleted.")
    out.append("")
    out.append("## Full history archive")
    out.append(f"- Original full file: `{archive_rel}`")
    out.append(f"- Original lines: {original_lines}")
    out.append(f"- Original SHA-256: `{original_sha}`")
    out.append(f"- Compacted at: `{timestamp}`")
    out.append("- When a detail is not present below, read the full archive before making assumptions.")
    out.append("")
    out.append("## Current operating invariants")
    if agent == "developer":
        out.extend([
            "- Production work is DAG-only: `task_dag.mode` must be `explicit_dag`.",
            "- `bootstrap_source_of_truth.py --refresh` preserves runtime by default; use `--reset-runtime-state` only for intentional destructive reset.",
            "- Never edit generated `registry.json`, `runtime-state.json`, `task-dag.json`, or `execution-graph.json` directly.",
            "- Scope every write by `CLAUDE_ACTIVE_TASK_ID` and `CLAUDE_TASK_PACK`.",
            "- Touch only paths present in the DAG task pack `Write set` / `allowed_paths`.",
            "- `docker-compose.yml`, `Dockerfile*`, `.env.example`, and `.github/workflows/**` require explicit task scope before editing.",
            "- Propose discovered out-of-slice work with `/register-followup`; do not promote follow-ups automatically.",
        ])
    elif agent == "official-docs-researcher":
        out.extend([
            "- Use official, current/versioned documentation only unless the task explicitly permits otherwise.",
            "- Fast lookup order: local/cache docs, ToolSearch/MCP, Context7, vendor MCP, then official WebFetch/WebSearch fallback.",
            "- Fan out independent documentation checks in one tool batch; do not serialize unless a result depends on a prior result.",
            "- Capture source, framework/library version, and concrete implementation implications.",
            "- Mark missing or conflicting documentation as `insufficient` or `discrepancy`; do not invent certainty.",
        ])
    else:
        out.extend([
            "- Treat `.claude/orchestrator-contract.json` and `.claude/rules/` as the source of operational truth.",
            "- Keep writes scoped to the active DAG task and agent write contract.",
            "- Use follow-ups for out-of-slice work; do not mutate generated DAG/runtime files directly.",
        ])
    out.append("")
    out.append("## Trailer vocabulary")
    outcome, next_status = ROLE_TRAILERS.get(agent, ("Read .claude/orchestrator-contract.json", "Read .claude/orchestrator-contract.json"))
    out.append(f"- `OUTCOME`: `{outcome}`")
    out.append(f"- `NEXT_STATUS`: `{next_status}`")
    out.append("- Always read `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` before emitting trailers.")
    out.append("")
    out.append("## High-signal preserved notes")
    if highlights:
        for line in highlights[:80]:
            out.append(f"- {line}")
    else:
        out.append("- No keyword-selected notes. Use the full archive for historical detail.")
    out.append("")
    out.append("## Original heading index")
    if headings:
        for heading in headings[:80]:
            out.append(f"- {heading}")
    else:
        out.append("- Original file had no markdown headings.")
    out.append("")
    out.append("## Canonical references")
    out.extend([
        "- `.claude/orchestrator-contract.json`",
        "- `.claude/rules/00-source-of-truth.md`",
        "- `.claude/rules/01-non-negotiables.md`",
        "- `.claude/rules/02-phase-execution.md`",
        "- `.claude/rules/05-runtime-write-contract.md`",
        "- `CHEATSHEET.md`",
        f"- `{archive_rel}`",
    ])
    out.append("")
    return "\n".join(out)


def _acquire_lock(lock_path: Path) -> int | None:
    try:
        fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return None
    os.write(fd, f"pid={os.getpid()}\n".encode("utf-8"))
    return fd


def compact(candidate: Candidate, timestamp: str) -> dict[str, object]:
    lock_path = candidate.path.parent / ".MEMORY.compact.lock"
    fd = _acquire_lock(lock_path)
    if fd is None:
        return {
            "agent": candidate.agent,
            "memory": candidate.path.relative_to(repo_root()).as_posix(),
            "skipped": "locked",
        }

    try:
        original_bytes = candidate.path.read_bytes()
        original_text = original_bytes.decode("utf-8", errors="replace")
        original_lines = len(original_text.splitlines())
        archive_dir = candidate.path.parent / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive = archive_dir / f"MEMORY.full.{timestamp}.md"
        if archive.exists():
            raise FileExistsError(f"archive already exists: {archive}")

        # Write the archive first, then ensure the live memory did not change
        # before replacing it. Agents do not share this lock, so the SHA check
        # prevents compaction from overwriting a concurrent append.
        archive.write_bytes(original_bytes)
        if archive.read_bytes() != original_bytes:
            raise RuntimeError(f"archive copy mismatch for {candidate.path}")
        if candidate.path.read_bytes() != original_bytes:
            archive.unlink(missing_ok=True)
            return {
                "agent": candidate.agent,
                "memory": candidate.path.relative_to(repo_root()).as_posix(),
                "skipped": "changed_during_compaction",
            }

        archive_rel = archive.relative_to(repo_root()).as_posix()
        original_sha = sha256(archive)
        compacted = compact_text(
            candidate.agent,
            original_text,
            archive_rel,
            original_lines,
            original_sha,
            timestamp,
        )
        tmp = candidate.path.with_name("MEMORY.md.compact.tmp")
        tmp.write_text(compacted, encoding="utf-8")
        os.replace(tmp, candidate.path)
        return {
            "agent": candidate.agent,
            "memory": candidate.path.relative_to(repo_root()).as_posix(),
            "archive": archive_rel,
            "original_lines": original_lines,
            "new_lines": count_lines(candidate.path),
            "original_sha256": original_sha,
        }
    finally:
        try:
            os.close(fd)
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact long orchestrator agent memories without loss")
    parser.add_argument("--apply", action="store_true", help="write compacted MEMORY.md files after archiving originals")
    parser.add_argument("--agent", help="compact only one agent memory")
    parser.add_argument("--all", action="store_true", help="scan all agent memories (default)")
    parser.add_argument("--threshold-lines", type=int, default=DEFAULT_THRESHOLD_LINES)
    parser.add_argument("--timestamp", help="override timestamp for deterministic tests")
    parser.add_argument("--json", action="store_true", help="emit machine-readable summary")
    parser.add_argument("--quiet", action="store_true", help="suppress human output when nothing actionable is needed")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    threshold = max(1, int(args.threshold_lines))
    timestamp = args.timestamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    candidates = discover(args.agent, threshold)
    selected = [c for c in candidates if c.should_compact]

    result: dict[str, object] = {
        "ok": True,
        "mode": "apply" if args.apply else "dry-run",
        "threshold_lines": threshold,
        "found": [c.__dict__ | {"path": c.path.relative_to(repo_root()).as_posix()} for c in candidates],
        "selected": [c.__dict__ | {"path": c.path.relative_to(repo_root()).as_posix()} for c in selected],
        "changed": [],
        "skipped": [],
    }

    if args.apply:
        changed = []
        skipped = []
        for candidate in selected:
            item = compact(candidate, timestamp)
            if item.get("skipped"):
                skipped.append(item)
            else:
                changed.append(item)
        result["changed"] = changed
        result["skipped"] = skipped

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.quiet:
        return 0

    title = "AGENT MEMORY COMPACTION"
    print(title)
    print("=" * len(title))
    print(f"mode: {result['mode']}")
    print(f"threshold_lines: {threshold}")
    if not candidates:
        print("No orchestrator-state/agent-memory/*/MEMORY.md files found.")
        return 0
    if not selected:
        print("No agent memories above threshold.")
        for c in candidates:
            print(f"KEEP {c.agent}: {c.line_count} lines")
        return 0
    for c in selected:
        planned = c.path.parent / "archive" / f"MEMORY.full.{timestamp}.md"
        print(f"COMPACT {c.agent}: {c.line_count} lines -> snapshot {planned.relative_to(repo_root()).as_posix()}")
    if not args.apply:
        print("Dry-run only. Re-run with --apply to archive originals and compact MEMORY.md.")
    else:
        for item in result["changed"]:  # type: ignore[index]
            print(f"APPLIED {item['agent']}: {item['original_lines']} -> {item['new_lines']} lines; archive={item['archive']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
