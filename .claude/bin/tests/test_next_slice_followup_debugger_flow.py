from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_next_slice_routes_validator_and_tester_failures_to_debugger_before_followup():
    text = read(".claude/commands/next-slice.md")
    assert "tester falla O `validator` pide cambios" in text or "tester falla O validator pide cambios" in text
    assert "validator OUTCOME=changes_requested" in text
    assert "tester OUTCOME=fail" in text
    assert "Invoca `debugger` con el mismo `TASK_ID`" in text
    assert "in_scope_defect` está prohibido" in text
    assert "Nunca promociones FU desde un worker terminal" in text


def test_validator_and_tester_do_not_claim_they_spawn_debugger():
    validator = read(".claude/agents/validator.md")
    tester = read(".claude/agents/tester.md")
    for text in (validator, tester):
        assert "Como subagente, no spawnees otros subagentes" in text
        assert "El **main-orchestrator** invocará `debugger`" in text
        assert "scope-classification out_of_scope|missing_coverage|missing_real_data" in text
    assert "llama a `debugger`" not in tester
    assert "deja que `debugger` arregle" not in validator


def test_runtime_rule_names_main_orchestrator_as_debugger_owner():
    text = read(".claude/rules/05-runtime-write-contract.md")
    assert "the main-orchestrator runs `debugger`" in text
    assert "Subagents must not spawn subagents" in text


def test_next_slice_never_invokes_closer_directly():
    text = read(".claude/commands/next-slice.md")
    assert "Este comando NO invoca closer" in text
    assert "La única ruta de cierre es `/verify-slice`" in text
    assert "No cierro desde `/next-slice`" in text
    assert "Closer directo SIN verify-slice" not in text
    assert "Spawnea `closer`" not in text
    assert "push a origin/main" not in text
