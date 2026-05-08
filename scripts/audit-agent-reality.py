#!/usr/bin/env python3
"""Audit Claude agent prompts against the real orchestrator contract/files.

This is a repo-internal consistency audit. It checks that agent prompts do not
teach stale source-of-truth wording, nonexistent slash commands, nonexistent
scripts/skills, or trailer/status vocabulary outside .claude/orchestrator-contract.json.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".claude" / "agents"
COMMANDS_DIR = ROOT / ".claude" / "commands"
SKILLS_DIR = ROOT / ".claude" / "skills"
CONTRACT_PATH = ROOT / ".claude" / "orchestrator-contract.json"
SETTINGS_PATH = ROOT / ".claude" / "settings.json"

OUTCOME_PATTERN = re.compile(r"(?<![A-Z0-9_])OUTCOME:\s*([a-z][a-z0-9_]*(?:\|[a-z][a-z0-9_]*)*)")
NEXT_STATUS_PATTERN = re.compile(r"(?<![A-Z0-9_])NEXT_STATUS:\s*([a-z][a-z0-9_]*(?:\|[a-z][a-z0-9_]*)*)")
SCRIPT_REF_PATTERN = re.compile(r"(?<![\w/.-])(?:\.\/)?scripts/[A-Za-z0-9_.-]+")
CLAUDE_BIN_REF_PATTERN = re.compile(r"(?<![\w/.-])\.claude/bin/[A-Za-z0-9_.-]+")
RULE_REF_PATTERN = re.compile(r"(?<![\w/.-])\.claude/rules/[A-Za-z0-9_.-]+")
COMMAND_REF_PATTERN = re.compile(r"(?<![\w:])/(auto-verify-slice|verify-slice|verify-journey|next-slice|next-wave|phase-gate|register-followup|revise-slice|slice-maintain|clear|bootstrap|helper|hook)\b")
HOOK_REF_PATTERN = re.compile(r"\bhook_[A-Za-z0-9_]+\.py\b")

# These strings have caused runtime/tracing drift in the past. They should not
# appear in agent prompts unless this audit explicitly allows them.
FORBIDDEN_AGENT_PATTERNS = {
    r"\bLos tres `?\.md`?": "source-of-truth is now the five-file pack, not three md files",
    r"\bthree `?\.md`?": "source-of-truth is now the five-file pack, not three md files",
    r"\b3 docs\b": "source-of-truth is now the five-file pack, not three docs",
    r"\bSix phases\b": "phase count is source-of-truth driven, not hardcoded",
    r"\bsix phases\b": "phase count is source-of-truth driven, not hardcoded",
    r"P00`?\.\.`?P05": "phase range is dynamic; do not hardcode P05 as final",
    r"\breview_pending\b": "legacy task status; use validator_tester_pending/ready_for_close/needs_debug lifecycle",
    r"\btest_pending\b": "legacy task status; use validator_tester_pending/ready_for_close/needs_debug lifecycle",
    r"\bqa_pending\b": "legacy task status; use validator_tester_pending/ready_for_close/needs_debug lifecycle",
    r"OUTCOME:\s*implemented\b": "invalid trailer outcome drift",
    r"OUTCOME:\s*researched\b": "invalid trailer outcome drift",
    r"OUTCOME:\s*validated\b": "invalid trailer outcome drift",
    r"NEXT_STATUS:\s*ready_for_validation\b": "invalid trailer next-status drift",
    r"NEXT_STATUS:\s*needs_review\b": "invalid trailer next-status drift",
    r"NEXT_STATUS:\s*ready_for_retest\b": "invalid trailer next-status drift",
    r"NEXT_STATUS:\s*info_only\b": "invalid trailer next-status drift",
    r"\bevidence-reporter\b": "legacy/non-existent agent name",
    r"\bgit-manager\b": "legacy/non-existent agent name",
    r"\bphase-controller\b": "legacy/non-existent agent name",
    r"\bcontext-curator\b": "legacy/non-existent agent name",
    r"\btechnical-analyst\b": "legacy/non-existent agent name",
    r"\bsecurity-auditor\b": "legacy/non-existent agent name",
    r"\bqa-validator\b": "legacy/non-existent agent name",
    r"\b7 agentes tienen `memory`": "hardcoded memory-agent count is stale",
    r"orchestrator-state/memory/agent-memory": "agent memory lives under orchestrator-state/agent-memory",
}

BOOTSTRAP_SOURCE_ROLES = {"document-analyzer", "project-architect", "task-planner"}
PLANNING_SOURCE_ROLES = {"main-orchestrator", "planner"} | BOOTSTRAP_SOURCE_ROLES
SOURCE_FILES = [
    "instrucciones.md",
    "*_TECHNICAL_GUIDE.md",
    "*_IMPLEMENTATION_CHECKLIST.md",
    "STACK_PROFILE.yaml",
    "UX_CONTRACT.md",
]


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def parse_skills(raw: str | None) -> list[str]:
    if not raw:
        return []
    raw = raw.strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        return []
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    return [part.strip().strip('"\'') for part in raw[1:-1].split(",") if part.strip()]


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


def audit_trailer_vocabulary(role: str, text: str, spec: dict[str, Any], errors: list[str], agent_path: Path) -> None:
    allowed_out = set(spec.get("outcome_values", []))
    allowed_next = set(spec.get("next_status_values", []))

    for match in OUTCOME_PATTERN.finditer(text):
        expr = match.group(1)
        unknown = split_expr(expr) - allowed_out
        if unknown:
            fail(errors, f"{agent_path}: OUTCOME {expr!r} outside trailer_schema.roles.{role}.outcome_values={sorted(allowed_out)}")

    for match in NEXT_STATUS_PATTERN.finditer(text):
        expr = match.group(1)
        values = split_expr(expr)
        if not allowed_next:
            fail(errors, f"{agent_path}: mentions NEXT_STATUS {expr!r}, but role has no next_status_values")
        else:
            unknown = values - allowed_next
            if unknown:
                fail(errors, f"{agent_path}: NEXT_STATUS {expr!r} outside trailer_schema.roles.{role}.next_status_values={sorted(allowed_next)}")

    if "## Cierre obligatorio" not in text:
        fail(errors, f"{agent_path}: missing ## Cierre obligatorio")
    if "## Production DAG trailer vocabulary" not in text:
        fail(errors, f"{agent_path}: missing ## Production DAG trailer vocabulary")
    if f"trailer_schema.roles.{role}.outcome_values" not in text:
        fail(errors, f"{agent_path}: does not point to its own outcome schema path")
    if f"trailer_schema.roles.{role}.next_status_values" not in text:
        fail(errors, f"{agent_path}: does not point to its own next-status schema path")

    expected_out = "|".join(spec.get("outcome_values", []))
    expected_next = "|".join(spec.get("next_status_values", []))
    canonical_blocks = [block for _, block in markdown_code_blocks(text) if "CLAUDE_TRAILER:" in block]
    if not canonical_blocks:
        fail(errors, f"{agent_path}: no CLAUDE_TRAILER code block")
    for block in canonical_blocks:
        if expected_out and f"OUTCOME: {expected_out}" not in block:
            fail(errors, f"{agent_path}: CLAUDE_TRAILER block lacks exact OUTCOME: {expected_out}")
        if expected_next:
            if f"NEXT_STATUS: {expected_next}" not in block:
                fail(errors, f"{agent_path}: CLAUDE_TRAILER block lacks exact NEXT_STATUS: {expected_next}")
        elif "NEXT_STATUS:" in block:
            fail(errors, f"{agent_path}: CLAUDE_TRAILER block teaches NEXT_STATUS although contract has none")
        for line in block.splitlines():
            if line.strip().startswith(("OUTCOME:", "NEXT_STATUS:", "TASK_ID:", "HANDOFF:", "EVIDENCE:")) and "#" in line:
                fail(errors, f"{agent_path}: inline comment inside machine-readable trailer line: {line.strip()}")

    if spec.get("info_only") and spec.get("next_status_values"):
        needed = ["info-only", "informational only", "validator_next_status", "does not mutate `task.status`"]
        if not all(token in text for token in needed):
            fail(errors, f"{agent_path}: info_only NEXT_STATUS semantics are not documented close to the trailer")


def audit_frontmatter_and_skills(role: str, text: str, errors: list[str], agent_path: Path) -> None:
    fm = parse_frontmatter(text)
    if fm.get("name") != role:
        fail(errors, f"{agent_path}: frontmatter name={fm.get('name')!r} does not match filename role={role!r}")
    for skill in parse_skills(fm.get("skills")):
        if not (SKILLS_DIR / skill / "SKILL.md").is_file():
            fail(errors, f"{agent_path}: frontmatter skill {skill!r} has no .claude/skills/{skill}/SKILL.md")


def audit_file_refs(text: str, errors: list[str], agent_path: Path) -> None:
    for pattern, label in [
        (SCRIPT_REF_PATTERN, "script"),
        (CLAUDE_BIN_REF_PATTERN, "claude-bin"),
        (RULE_REF_PATTERN, "rule"),
    ]:
        for match in pattern.finditer(text):
            raw = match.group(0)
            rel = raw[2:] if raw.startswith("./") else raw
            if not (ROOT / rel).is_file():
                fail(errors, f"{agent_path}: {label} reference does not exist: {raw}")

    for match in HOOK_REF_PATTERN.finditer(text):
        rel = ".claude/bin/" + match.group(0)
        if not (ROOT / rel).is_file():
            fail(errors, f"{agent_path}: hook reference does not exist: {rel}")

    commands = {p.stem for p in COMMANDS_DIR.glob("*.md")}
    for match in COMMAND_REF_PATTERN.finditer(text):
        command = match.group(1)
        if command == "clear":
            continue  # Built-in Claude Code command, not stored under .claude/commands.
        if command not in commands:
            fail(errors, f"{agent_path}: slash command /{command} is mentioned but .claude/commands/{command}.md does not exist")


def audit_source_pack_language(role: str, text: str, errors: list[str], agent_path: Path) -> None:
    for regex, reason in FORBIDDEN_AGENT_PATTERNS.items():
        if re.search(regex, text):
            fail(errors, f"{agent_path}: stale/invalid wording matched {regex!r}: {reason}")

    if role in PLANNING_SOURCE_ROLES:
        for name in SOURCE_FILES:
            if name not in text:
                fail(errors, f"{agent_path}: planning/bootstrap role must mention source-of-truth file {name}")


def audit_settings_hooks(errors: list[str]) -> None:
    settings = load_json(SETTINGS_PATH)
    hooks = settings.get("hooks", {})
    for event, entries in hooks.items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = str(hook.get("command") or "")
                for match in HOOK_REF_PATTERN.finditer(command):
                    rel = ".claude/bin/" + match.group(0)
                    if not (ROOT / rel).is_file():
                        fail(errors, f".claude/settings.json:{event}: hook command references missing {rel}")


def audit_contract_mirrors(contract: dict[str, Any], roles: dict[str, dict[str, Any]], errors: list[str]) -> None:
    lifecycle_from_schema = [role for role, spec in roles.items() if spec.get("mutates_registry_lifecycle")]
    info_only_from_schema = [role for role, spec in roles.items() if spec.get("info_only")]
    if contract.get("trailers", {}).get("lifecycle_agents") != lifecycle_from_schema:
        fail(errors, "contract.trailers.lifecycle_agents does not match trailer_schema.roles[*].mutates_registry_lifecycle")
    if contract.get("trailers", {}).get("info_only_agents") != info_only_from_schema:
        fail(errors, "contract.trailers.info_only_agents does not match trailer_schema.roles[*].info_only")
    expected_outcome = {role: spec.get("outcome_values", []) for role, spec in roles.items()}
    expected_next = {role: spec.get("next_status_values", []) for role, spec in roles.items()}
    if contract.get("outcome_enums") != expected_outcome:
        fail(errors, "contract.outcome_enums mirror does not match trailer_schema.roles[*].outcome_values")
    if contract.get("next_status_enums") != expected_next:
        fail(errors, "contract.next_status_enums mirror does not match trailer_schema.roles[*].next_status_values")


def audit_agent_memory_contract(role: str, text: str, contract: dict[str, Any], errors: list[str], agent_path: Path) -> None:
    expected = f"orchestrator-state/agent-memory/{role}/MEMORY.md"
    if expected not in text:
        fail(errors, f"{agent_path}: missing expected role memory path {expected}")
    write_contract = contract.get("agent_write_contract", {})
    if role not in write_contract:
        fail(errors, f"agent_write_contract missing role {role!r}")
        return
    may_write = "\n".join(str(x) for x in write_contract.get(role, {}).get("may_write", []))
    if expected not in may_write:
        fail(errors, f"agent_write_contract.{role}.may_write does not allow {expected}")
    if re.search(r"(?<!orchestrator-state/)agent-memory/[A-Za-z0-9_-]+/[^`\s]+\.md", text):
        fail(errors, f"{agent_path}: uses relative agent-memory path; use orchestrator-state/agent-memory/<agent>/MEMORY.md")


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    roles: dict[str, dict[str, Any]] = contract["trailer_schema"]["roles"]
    errors: list[str] = []
    rows: list[tuple[str, str, str, str, str, str]] = []

    agent_roles = {p.stem for p in AGENTS_DIR.glob("*.md")}
    if agent_roles != set(roles):
        fail(errors, f"agent files and trailer_schema.roles differ: agents={sorted(agent_roles)} roles={sorted(roles)}")
    audit_contract_mirrors(contract, roles, errors)

    for agent_path in sorted(AGENTS_DIR.glob("*.md")):
        role = agent_path.stem
        text = agent_path.read_text(encoding="utf-8")
        spec = roles.get(role, {})
        audit_frontmatter_and_skills(role, text, errors, agent_path)
        audit_agent_memory_contract(role, text, contract, errors, agent_path)
        audit_trailer_vocabulary(role, text, spec, errors, agent_path)
        audit_file_refs(text, errors, agent_path)
        audit_source_pack_language(role, text, errors, agent_path)
        rows.append((
            role,
            "|".join(spec.get("outcome_values", [])),
            "|".join(spec.get("next_status_values", [])) or "<none>",
            str(spec.get("info_only", False)).lower(),
            ",".join(parse_skills(parse_frontmatter(text).get("skills"))) or "<none>",
            "ok",
        ))

    audit_settings_hooks(errors)

    headers = ("agent", "OUTCOME", "NEXT_STATUS", "info_only", "skills", "result")
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(widths[i], len(row[i])) for i in range(len(headers))]

    def fmt(row: tuple[str, ...]) -> str:
        return "  ".join(row[i].ljust(widths[i]) for i in range(len(row)))

    print(fmt(headers))
    print(fmt(tuple("-" * width for width in widths)))
    for row in rows:
        print(fmt(row))

    if errors:
        print("\nAGENT_REALITY_AUDIT: fail", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("\nAGENT_REALITY_AUDIT: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
