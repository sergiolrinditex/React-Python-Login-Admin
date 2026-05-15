#!/usr/bin/env python3
"""Audit agent prompt trailer vocabulary against orchestrator-contract.json.

This intentionally checks the markdown prompts, not runtime state. It catches cases
where an agent prompt teaches a synonym such as OUTCOME=implemented or
NEXT_STATUS=ready_for_retest instead of the closed enum from trailer_schema.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / ".claude" / "orchestrator-contract.json"
AGENTS_DIR = ROOT / ".claude" / "agents"

OUTCOME_PATTERN = re.compile(r"(?<![A-Z0-9_])OUTCOME:\s*([a-z][a-z0-9_]*(?:\|[a-z][a-z0-9_]*)*)")
NEXT_STATUS_PATTERN = re.compile(r"(?<![A-Z0-9_])NEXT_STATUS:\s*([a-z][a-z0-9_]*(?:\|[a-z][a-z0-9_]*)*)")


def load_roles() -> dict[str, dict[str, list[str]]]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    return contract["trailer_schema"]["roles"]


def unique_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    values: list[str] = []
    for match in pattern.finditer(text):
        expr = match.group(1)
        if expr not in values:
            values.append(expr)
    return values


def split_expr(expr: str) -> set[str]:
    return {part for part in expr.split("|") if part}


def markdown_code_blocks(text: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    in_block = False
    current: list[str] = []
    start_line = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            if in_block:
                blocks.append((start_line, "\n".join(current)))
                current = []
                in_block = False
            else:
                in_block = True
                start_line = lineno + 1
                current = []
            continue
        if in_block:
            current.append(line)
    return blocks


def main() -> int:
    roles = load_roles()
    errors: list[str] = []
    rows: list[tuple[str, str, str, str, str]] = []

    for agent_path in sorted(AGENTS_DIR.glob("*.md")):
        role = agent_path.stem
        if role not in roles:
            continue
        text = agent_path.read_text(encoding="utf-8")
        allowed_out = set(roles[role].get("outcome_values", []))
        allowed_next = set(roles[role].get("next_status_values", []))
        md_out = unique_matches(OUTCOME_PATTERN, text)
        md_next = unique_matches(NEXT_STATUS_PATTERN, text)

        for expr in md_out:
            unknown = split_expr(expr) - allowed_out
            if unknown:
                errors.append(
                    f"{agent_path}: OUTCOME {expr!r} contains values outside "
                    f"trailer_schema.roles.{role}.outcome_values={sorted(allowed_out)}"
                )
        for expr in md_next:
            values = split_expr(expr)
            if not allowed_next:
                errors.append(
                    f"{agent_path}: NEXT_STATUS {expr!r} is mentioned but "
                    f"trailer_schema.roles.{role}.next_status_values is empty"
                )
                continue
            unknown = values - allowed_next
            if unknown:
                errors.append(
                    f"{agent_path}: NEXT_STATUS {expr!r} contains values outside "
                    f"trailer_schema.roles.{role}.next_status_values={sorted(allowed_next)}"
                )

        for block_start, block in markdown_code_blocks(text):
            if "CLAUDE_TRAILER:" not in block:
                continue
            trailer_tail = block.split("CLAUDE_TRAILER:", 1)[1]
            for rel_lineno, line in enumerate(trailer_tail.splitlines(), start=block_start + block[: block.find("CLAUDE_TRAILER:")].count("\n") + 1):
                if "#" in line and ":" in line:
                    errors.append(
                        f"{agent_path}:{rel_lineno}: CLAUDE_TRAILER code block contains inline comment; "
                        "machine-readable trailer lines must be comment-free"
                    )

        if roles[role].get("info_only") and allowed_next:
            if not re.search(r"NEXT_STATUS`[^\n]*(info-only|informational only|informativa)", text, flags=re.I):
                errors.append(
                    f"{agent_path}: role is info_only and has next_status_values; "
                    "prompt must state that NEXT_STATUS is info-only/informational metadata near the canonical trailer"
                )

        rows.append(
            (
                role,
                "|".join(roles[role].get("outcome_values", [])),
                ", ".join(md_out) or "<none>",
                "|".join(roles[role].get("next_status_values", [])) or "<none>",
                ", ".join(md_next) or "<none>",
            )
        )

    headers = ("agent", "contract_outcome", "md_outcome_mentions", "contract_next_status", "md_next_status_mentions")
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(widths[i], len(row[i])) for i in range(len(headers))]

    def fmt(row: tuple[str, str, str, str, str]) -> str:
        return "  ".join(row[i].ljust(widths[i]) for i in range(len(row)))

    print(fmt(headers))
    print(fmt(tuple("-" * width for width in widths)))
    for row in rows:
        print(fmt(row))

    if errors:
        print("\nTRAILER_VOCABULARY_AUDIT: fail", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("\nTRAILER_VOCABULARY_AUDIT: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
