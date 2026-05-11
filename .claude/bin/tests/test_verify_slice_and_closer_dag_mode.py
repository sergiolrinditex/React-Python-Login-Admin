from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_verify_slice_repeats_dag_mode_and_passes_dag_context_to_spawns() -> None:
    text = (ROOT / ".claude/commands/verify-slice.md").read_text(encoding="utf-8")
    assert "## Production DAG mode" in text
    assert "MODO DAG ACTIVO: production = explicit_dag" in text
    assert "Unidad verificable = TASK_ID canónico del registry" in text
    assert "TASK_ID explícito" in text
    assert "Todo Agent spawn desde verify-slice debe recibir TASK_ID, CLAUDE_TASK_PACK" in text
    assert "ausencia de `Depends on` es error operativo" in text
    assert "spawnea `closer`" in text
    assert "CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md" in text
    assert "cierra sólo el TASK_ID explícito" in text
    assert "spawnea `debugger`" in text


def test_closer_repeats_dag_mode_before_precheck_and_blocks_missing_dependency_column_close() -> None:
    text = (ROOT / ".claude/agents/closer.md").read_text(encoding="utf-8")
    assert "## Production DAG mode" in text
    assert "MODO DAG ACTIVO: production = explicit_dag" in text
    assert "Unidad que se cierra = TASK_ID canónico del registry" in text
    assert "No cierres por global state" in text
    assert "task_dag.mode == explicit_dag" in text
    assert "DAG explícito" in text
    assert "TASK_ID explícito" in text
    assert "no edites registry/runtime/task-dag directamente" in text


def test_verify_slice_uses_configured_git_workflow_not_direct_push_wording() -> None:
    text = (ROOT / ".claude/commands/verify-slice.md").read_text(encoding="utf-8")
    assert "workflow Git configurado" in text
    assert "./scripts/git-workflow.sh" in text
    assert "push origin/main" not in text
    assert "push main" not in text
