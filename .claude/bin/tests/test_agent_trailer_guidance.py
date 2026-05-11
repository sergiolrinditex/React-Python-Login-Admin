from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

FORBIDDEN_TRAILER_SYNONYMS = [
    "OUTCOME: planned",          # planner drift; deployer only uses planned inside a pipe-list enum
    "OUTCOME: researched",
    "OUTCOME: implemented",
    "OUTCOME: validated",
    "NEXT_STATUS: ready_for_validation",
    "NEXT_STATUS: needs_review",
    "NEXT_STATUS: info_only",
    "NEXT_STATUS: ready_for_retest",
    "NEXT_STATUS: validated",
]


def _contract_roles() -> dict:
    contract = json.loads((ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8"))
    return contract["trailer_schema"]["roles"]


def _markdown_code_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    in_block = False
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("```"):
            if in_block:
                blocks.append("\n".join(current))
                current = []
                in_block = False
            else:
                in_block = True
                current = []
            continue
        if in_block:
            current.append(line)
    return blocks


class AgentTrailerGuidanceTests(unittest.TestCase):
    def test_agent_prompts_use_production_dag_trailer_vocabulary(self) -> None:
        roles = _contract_roles()
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            role = agent_path.stem
            if role not in roles:
                continue
            with self.subTest(agent=agent_path.name):
                text = agent_path.read_text(encoding="utf-8")
                self.assertIn("## Production DAG trailer vocabulary", text)
                self.assertNotIn("## Trailer enum lock", text)
                expected_source = (
                    f"Closed trailer enums live in `.claude/orchestrator-contract.json` → "
                    f"`trailer_schema.roles.{role}.outcome_values` and "
                    f"`trailer_schema.roles.{role}.next_status_values`. Read that path before emitting the trailer."
                )
                self.assertIn(expected_source, text)
                self.assertIn(
                    "Scope writes by `CLAUDE_ACTIVE_TASK_ID`/`CLAUDE_TASK_PACK`; never edit generated registry/runtime/task-dag directly.",
                    text,
                )
                if role == "screen-journey-reviewer":
                    self.assertIn("Do not create or promote follow-ups directly", text)
                    self.assertIn("followup_candidate=yes", text)
                else:
                    self.assertIn("Use `/register-followup` for discovered work outside current slice.", text)
                self.assertIn("CLAUDE_TRAILER:", text)
                for value in roles[role].get("outcome_values", []):
                    self.assertIn(value, text, f"missing OUTCOME enum {value}")
                for value in roles[role].get("next_status_values", []):
                    self.assertIn(value, text, f"missing NEXT_STATUS enum {value}")

    def test_agent_prompts_do_not_teach_known_invalid_trailer_synonyms(self) -> None:
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            with self.subTest(agent=agent_path.name):
                text = agent_path.read_text(encoding="utf-8")
                for forbidden in FORBIDDEN_TRAILER_SYNONYMS:
                    self.assertNotIn(forbidden, text)


    def test_cierre_obligatorio_sections_match_contract(self) -> None:
        roles = _contract_roles()
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            role = agent_path.stem
            if role not in roles:
                continue
            spec = roles[role]
            expected_outcomes = "|".join(spec.get("outcome_values", []))
            expected_next = "|".join(spec.get("next_status_values", []))
            with self.subTest(agent=agent_path.name):
                text = agent_path.read_text(encoding="utf-8")
                match = re.search(r"^## Cierre obligatorio.*?(?=^##\s|\Z)", text, flags=re.M | re.S)
                self.assertIsNotNone(match, "missing ## Cierre obligatorio section")
                section = match.group(0)
                self.assertIn("CLAUDE_TRAILER:", section)
                self.assertIn(f"OUTCOME: {expected_outcomes}", section)
                if expected_next:
                    self.assertIn(f"NEXT_STATUS: {expected_next}", section)
                else:
                    self.assertNotIn("NEXT_STATUS:", section)

    def test_all_claude_trailer_code_blocks_match_contract(self) -> None:
        roles = _contract_roles()
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            role = agent_path.stem
            if role not in roles:
                continue
            spec = roles[role]
            expected_outcomes = "|".join(spec.get("outcome_values", []))
            expected_next = "|".join(spec.get("next_status_values", []))
            text = agent_path.read_text(encoding="utf-8")
            code_blocks = _markdown_code_blocks(text)
            trailer_blocks = [block for block in code_blocks if re.search(r"^CLAUDE_TRAILER:\s*$", block, flags=re.M)]
            with self.subTest(agent=agent_path.name):
                self.assertGreaterEqual(len(trailer_blocks), 1, "missing CLAUDE_TRAILER code block")
            for idx, block in enumerate(trailer_blocks, start=1):
                with self.subTest(agent=agent_path.name, trailer_block=idx):
                    self.assertIn(f"OUTCOME: {expected_outcomes}", block)
                    if expected_next:
                        self.assertIn(f"NEXT_STATUS: {expected_next}", block)
                    else:
                        self.assertNotIn("NEXT_STATUS:", block)


    def test_claude_trailer_code_blocks_are_comment_free(self) -> None:
        """Machine-readable examples must not teach inline comments in trailer lines."""
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            text = agent_path.read_text(encoding="utf-8")
            trailer_blocks = [block for block in _markdown_code_blocks(text) if re.search(r"^CLAUDE_TRAILER:\s*$", block, flags=re.M)]
            for idx, block in enumerate(trailer_blocks, start=1):
                trailer_tail = block.split("CLAUDE_TRAILER:", 1)[1]
                with self.subTest(agent=agent_path.name, trailer_block=idx):
                    for line in trailer_tail.splitlines():
                        if ":" in line:
                            self.assertNotIn("#", line, f"inline comment in machine-readable trailer line: {line}")

    def test_info_only_roles_with_next_status_explain_metadata_semantics(self) -> None:
        roles = _contract_roles()
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            role = agent_path.stem
            if role not in roles:
                continue
            spec = roles[role]
            if not (spec.get("info_only") and spec.get("next_status_values")):
                continue
            with self.subTest(agent=agent_path.name):
                text = agent_path.read_text(encoding="utf-8")
                self.assertIn("info-only metadata", text)
                self.assertIn("does not mutate `task.status`", text)


    def test_every_explicit_trailer_status_mention_matches_own_role_contract(self) -> None:
        """Guard against prompt drift outside the final CLAUDE_TRAILER blocks.

        This scans each agent prompt for literal `OUTCOME:` and `NEXT_STATUS:`
        mentions anywhere in the markdown. Values may be a single enum or a
        pipe-list enum. Every literal value taught by the prompt must belong to
        that agent's trailer schema. VERIFY_OUTCOME/JOURNEY_VERIFY_OUTCOME are
        intentionally ignored because they are handoff verification fields, not
        SubagentStop trailer fields.
        """
        roles = _contract_roles()
        outcome_pattern = re.compile(r"(?<![A-Z0-9_])OUTCOME:\s*([a-z][a-z0-9_]*(?:\|[a-z][a-z0-9_]*)*)")
        next_status_pattern = re.compile(r"(?<![A-Z0-9_])NEXT_STATUS:\s*([a-z][a-z0-9_]*(?:\|[a-z][a-z0-9_]*)*)")
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            role = agent_path.stem
            if role not in roles:
                continue
            text = agent_path.read_text(encoding="utf-8")
            allowed_outcomes = set(roles[role].get("outcome_values", []))
            allowed_next = set(roles[role].get("next_status_values", []))
            with self.subTest(agent=agent_path.name, field="OUTCOME"):
                for match in outcome_pattern.finditer(text):
                    value_expr = match.group(1)
                    values = set(value_expr.split("|"))
                    self.assertTrue(
                        values <= allowed_outcomes,
                        f"{agent_path.name} teaches OUTCOME {value_expr!r}, outside {sorted(allowed_outcomes)}",
                    )
            with self.subTest(agent=agent_path.name, field="NEXT_STATUS"):
                for match in next_status_pattern.finditer(text):
                    value_expr = match.group(1)
                    values = set(value_expr.split("|"))
                    self.assertTrue(
                        allowed_next,
                        f"{agent_path.name} must not teach NEXT_STATUS {value_expr!r}; role has no next_status_values",
                    )
                    self.assertTrue(
                        values <= allowed_next,
                        f"{agent_path.name} teaches NEXT_STATUS {value_expr!r}, outside {sorted(allowed_next)}",
                    )


    def test_every_literal_trailer_state_mention_matches_that_agent_contract(self) -> None:
        """Guardrail for the exact issue that caused hook noise.

        This scans every agent prompt, not only the final code blocks. Whenever an
        agent prompt uses a literal trailer assignment such as `OUTCOME: ...` or
        `NEXT_STATUS: ...`, the mentioned values must be valid for that same
        agent role in .claude/orchestrator-contract.json. Related protocol fields
        such as VERIFY_OUTCOME/JOURNEY_VERIFY_OUTCOME are intentionally ignored.
        """
        roles = _contract_roles()
        trailer_assignment = re.compile(r"(?<![A-Z_])(?P<field>OUTCOME|NEXT_STATUS):\s*`?(?P<value>[^`\s,;\)]+)")
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            role = agent_path.stem
            if role not in roles:
                continue
            spec = roles[role]
            allowed = {
                "OUTCOME": set(spec.get("outcome_values", [])),
                "NEXT_STATUS": set(spec.get("next_status_values", [])),
            }
            text = agent_path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for match in trailer_assignment.finditer(line):
                    field = match.group("field")
                    raw = match.group("value").strip("`")
                    # Generic prose should not look like a concrete trailer assignment.
                    self.assertFalse(
                        raw.startswith("<"),
                        f"{agent_path.name}:{lineno} uses placeholder trailer assignment {field}: {raw}",
                    )
                    values = [value for value in raw.split("|") if value]
                    invalid = [value for value in values if value not in allowed[field]]
                    self.assertFalse(
                        invalid,
                        f"{agent_path.name}:{lineno} has invalid {field} values {invalid}; "
                        f"allowed={sorted(allowed[field])}; line={line.strip()}",
                    )


    def test_info_only_next_status_roles_document_runtime_semantics(self) -> None:
        roles = _contract_roles()
        for agent_path in sorted((ROOT / ".claude/agents").glob("*.md")):
            role = agent_path.stem
            if role not in roles:
                continue
            spec = roles[role]
            if not spec.get("next_status_values") or not spec.get("info_only"):
                continue
            text = agent_path.read_text(encoding="utf-8")
            with self.subTest(agent=agent_path.name):
                self.assertRegex(text, r"informational only|info-only|informativo")
                self.assertIn("validator_next_status", text)
                self.assertIn("task.status", text)
                self.assertIn("Emit the line exactly as shown, with no inline comments", text)

    def test_main_orchestrator_spawn_table_lists_every_contract_role(self) -> None:
        roles = _contract_roles()
        text = (ROOT / ".claude/agents/main-orchestrator.md").read_text(encoding="utf-8")
        table_match = re.search(r"```text\n(closer:.*?main-orchestrator:.*?)\n```", text, flags=re.S)
        self.assertIsNotNone(table_match, "main-orchestrator trailer enum table not found")
        table = table_match.group(1)
        for role, spec in sorted(roles.items()):
            with self.subTest(role=role):
                self.assertIn(f"{role}:", table)
                self.assertIn("OUTCOME " + "|".join(spec.get("outcome_values", [])), table)
                next_values = spec.get("next_status_values", [])
                expected_next = "NEXT_STATUS " + ("|".join(next_values) if next_values else "<none>")
                self.assertIn(expected_next, table)

    def test_cheatsheet_documents_trailer_enums_and_git_modes(self) -> None:
        text = (ROOT / "CHEATSHEET.md").read_text(encoding="utf-8")
        self.assertIn("Production DAG trailer vocabulary", text)
        self.assertIn(
            "Closed trailer enums live in `.claude/orchestrator-contract.json` → `trailer_schema.roles.<agent>.outcome_values`",
            text,
        )
        for expected in [
            "developer",
            "validator_tester_pending",
            "ready_for_close",
            "official-docs-researcher",
            "push-to-main",
            "direct-main",
            "pr-flow",
            "document-analyzer",
            "project-architect",
            "task-planner",
        ]:
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
