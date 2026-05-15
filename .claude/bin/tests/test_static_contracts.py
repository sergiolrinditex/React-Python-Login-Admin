"""Static contract checks for the Claude Code orchestrator."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RULES = [
    ".claude/rules/00-source-of-truth.md",
    ".claude/rules/01-non-negotiables.md",
    ".claude/rules/02-phase-execution.md",
    ".claude/rules/03-dev-loop.md",
    ".claude/rules/04-traceability.md",
    ".claude/rules/05-runtime-write-contract.md",
]


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ""
    return text.split("---\n", 2)[1]


class StaticClaudeContracts(unittest.TestCase):
    def test_settings_autonomous_and_hook_paths(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["permissions"]["defaultMode"], "bypassPermissions")
        raw = json.dumps(settings, ensure_ascii=False)
        self.assertIn('python3 -B -S', raw)
        self.assertIn('${CLAUDE_PROJECT_DIR:-$PWD}', raw)
        self.assertIn('/.claude/bin/', raw)
        self.assertIn('hook_write_scope_guard.py', raw)
        self.assertIn('MultiEdit', raw)
        self.assertIn('"timeout": 45', raw)  # SubagentStop has enough room.

    def test_agents_load_rules_and_use_external_memory(self):
        agents = sorted((ROOT / ".claude/agents").glob("*.md"))
        self.assertGreater(len(agents), 0)
        for path in agents:
            text = path.read_text(encoding="utf-8")
            fm = _frontmatter(path)
            self.assertNotIn("memory:", fm, f"{path.name} must not use Claude auto-memory under .claude")
            self.assertIn("Startup obligatorio del agente", text, path.name)
            for rule in RULES:
                self.assertIn(rule, text, f"{path.name} must explicitly load {rule}")
            self.assertIn("orchestrator-state/agent-memory/", text, path.name)
            self.assertIn(".claude/orchestrator-contract.json", text, path.name)
    def test_central_orchestrator_contract_exists(self):
        contract_path = ROOT / ".claude/orchestrator-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["dag_scope"]["task_id_env"], "CLAUDE_ACTIVE_TASK_ID")
        self.assertEqual(contract["dag_scope"]["task_pack_env"], "CLAUDE_TASK_PACK")
        self.assertIn("planner", contract["agent_write_contract"])
        self.assertIn("closer", contract["agent_write_contract"])
        self.assertIn("required_screen_states", contract["ux_contract"])
        rule = (ROOT / ".claude/rules/05-runtime-write-contract.md").read_text(encoding="utf-8")
        self.assertIn("orchestrator-contract.json", rule)
        self.assertIn("hook_write_scope_guard.py", rule)


    def test_parallel_dag_uses_per_task_packs(self):
        required = [
            ".claude/CLAUDE.md",
            ".claude/commands/next-slice.md",
            ".claude/commands/next-wave.md",
            ".claude/agents/planner.md",
            ".claude/agents/developer.md",
            ".claude/agents/tester.md",
            ".claude/agents/validator.md",
            ".claude/agents/closer.md",
            ".claude/skills/build-task-pack/SKILL.md",
            ".claude/skills/write-handoff/SKILL.md",
            ".claude/skills/close-task/SKILL.md",
            ".claude/bin/claim_task.py",
            ".claude/bin/next_wave.py",
        ]
        for rel in required:
            text = (ROOT / rel).read_text(encoding="utf-8")
            if rel.endswith("claim_task.py"):
                self.assertIn("task_pack_path", text, rel)
                self.assertIn("_ensure_minimal_task_pack", text, rel)
            else:
                self.assertIn("task-packs", text, rel)

        next_wave = (ROOT / ".claude/bin/next_wave.py").read_text(encoding="utf-8")
        self.assertIn("CLAUDE_TASK_PACK", next_wave)
        self.assertNotIn("claim_task.py", next_wave.split("def _terminal_command", 1)[1])

    def test_chatgpt_dag_generation_docs_exist(self):
        guide = (ROOT / "docs/CHATGPT_DAG_SOURCE_OF_TRUTH_GUIDE.md").read_text(encoding="utf-8")
        prompt = (ROOT / "docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md").read_text(encoding="utf-8")
        for text, name in [(guide, "guide"), (prompt, "prompt")]:
            self.assertIn("mode=explicit_dag", text, name)
            self.assertIn("Depends on", text, name)
            self.assertIn("check-wiring-contract.sh --strict --require-new-template-columns", text, name)
            self.assertIn("CLAUDE_TASK_PACK", text, name)


    def test_spawn_budget_is_twenty_not_six(self):
        files = [p for p in (ROOT / ".claude").rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json"} and p.name != "test_static_contracts.py"]
        corpus = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)
        self.assertIn("DEFAULT_SPAWN_BUDGET = 20", corpus)
        six = str(3 * 2)
        forbidden = [fr"max\s+{six}\s+spawns", six + r"-spawn", "0/" + six, "2/" + six, fr"range\({six}\)"]
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, corpus, re.IGNORECASE), pattern)

    def test_slice_verifier_has_mcp_browser_turn_budget(self):
        text = (ROOT / ".claude/agents/slice-verifier.md").read_text(encoding="utf-8")
        self.assertIn("maxTurns: 130", text)
        self.assertIn("Chrome DevTools MCP", text)
        self.assertIn("no cambia el `spawn_budget` global de 20 subagentes", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
