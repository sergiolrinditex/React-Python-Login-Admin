from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_validator_tester_must_register_out_of_scope_followups_formally() -> None:
    validator = read(".claude/agents/validator.md")
    tester = read(".claude/agents/tester.md")
    for rel, text in {
        "validator": validator,
        "tester": tester,
    }.items():
        assert "./scripts/register-followup-task.sh propose" in text, rel
        assert "no basta" in text or "no dejes el hallazgo sólo como prosa" in text, rel
        assert "FOLLOWUP_ID" in text, rel
        assert "scope_classification" in text, rel
        assert "why_not_debugger" in text, rel
        assert "no llames a `promote`" in text or "No llames a `promote`" in text, rel


def test_next_slice_blocks_out_of_scope_prose_without_formal_followup() -> None:
    text = read(".claude/commands/next-slice.md")
    assert "describen trabajo fuera de scope" in text
    assert "no hay `FOLLOWUP_ID` formal" in text
    assert "Un hallazgo productivo no puede quedar sólo como prosa" in text


def test_official_docs_researcher_is_conditional_not_always_on() -> None:
    text = read(".claude/commands/next-slice.md")
    assert "sólo si el `planner` marca `NEEDS_OFFICIAL_DOCS: yes`" in text
    assert "No lo llames para CRUD repetitivo" in text
    assert "Dale una lista de 1–5 preguntas concretas" in text
    claude = read(".claude/CLAUDE.md")
    assert "official-docs-researcher runs only" in claude
    assert "ALWAYS runs" not in claude


def test_hooks_do_not_parse_markdown_rules_at_runtime() -> None:
    for hook in (ROOT / ".claude" / "bin").glob("hook_*.py"):
        text = hook.read_text(encoding="utf-8")
        assert ".claude/rules" not in text, hook
        assert "rules/" not in text, hook
    claude = read(".claude/CLAUDE.md")
    assert "Hooks enforce code + `orchestrator-contract.json`" in claude
    assert "do not parse `.claude/rules/*.md`" in claude
