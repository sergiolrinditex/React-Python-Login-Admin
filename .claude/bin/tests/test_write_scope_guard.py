from __future__ import annotations

import json
import os
import sys
from io import StringIO
from unittest import mock


def _payload(tool_name: str, path: str) -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": {"file_path": path}})


def _run_hook(stdin_text: str) -> str:
    import hook_write_scope_guard as hook
    buf = StringIO()
    with mock.patch.object(sys, "stdin", StringIO(stdin_text)), mock.patch.object(sys, "stdout", buf):
        assert hook.main() == 0
    return buf.getvalue()


def _denied(output: str) -> str:
    data = json.loads(output)
    out = data["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    return out["permissionDecisionReason"]


def test_blocks_static_claude_writes_by_default(tmp_project):
    reason = _denied(_run_hook(_payload("Write", ".claude/agents/developer.md")))
    assert "static orchestrator config" in reason


def test_allows_static_claude_writes_with_explicit_override(tmp_project, monkeypatch):
    monkeypatch.setenv("CLAUDE_ALLOW_STATIC_CONFIG_WRITES", "1")
    assert _run_hook(_payload("Write", ".claude/agents/developer.md")) == ""


def test_blocks_cross_task_handoff_write_in_dag_terminal(tmp_project, monkeypatch):
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    reason = _denied(_run_hook(_payload("Edit", "orchestrator-state/tasks/handoffs/P00-S01-T002.md")))
    assert "cross-task write" in reason
    assert "P00-S01-T001" in reason
    assert "P00-S01-T002" in reason


def test_allows_same_task_evidence_write_in_dag_terminal(tmp_project, monkeypatch):
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    assert _run_hook(_payload("MultiEdit", "orchestrator-state/tasks/evidence/P00-S01-T001/backend-tests.txt")) == ""


def test_blocks_source_truth_edit_while_task_active(tmp_project, monkeypatch):
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    reason = _denied(_run_hook(_payload("Write", "docs/source-of-truth/instrucciones.md")))
    assert "source-of-truth edit" in reason


def test_blocks_direct_generated_core_state_edit(tmp_project):
    reason = _denied(_run_hook(_payload("Edit", "orchestrator-state/tasks/registry.json")))
    assert "generated core orchestrator state" in reason


def test_logs_nonblocking_write_set_warning(tmp_project, monkeypatch):
    import common
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "P0", "status": "active", "task_ids": ["P00-S01-T001"]}],
        "tasks": [{
            "id": "P00-S01-T001",
            "title": "A",
            "phase_id": "P00",
            "step_id": "P00-S01",
            "status": "claimed",
            "depends_on": [],
            "write_set": ["app/lib/features/a/**"],
        }],
        "journeys": [],
    })
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    assert _run_hook(_payload("Write", "app/lib/features/b/page.dart")) == ""
    ledger = (tmp_project / "orchestrator-state" / "tasks" / "ledger.jsonl").read_text(encoding="utf-8")
    assert "write_scope_warning" in ledger
    assert "outside declared Write set" in ledger


def test_blocks_product_baseline_baseline_edit_while_task_active(tmp_project, monkeypatch):
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    reason = _denied(_run_hook(_payload("Write", "docs/product-baseline/instrucciones.md")))
    assert "baseline edit" in reason


def test_blocks_direct_followup_yaml_write_while_task_active(tmp_project, monkeypatch):
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    reason = _denied(_run_hook(_payload("Write", "orchestrator-state/tasks/follow-ups/FU-123.yaml")))
    assert "direct follow-up" in reason


# ---------------------------------------------------------------------------
# Stack-specific dev profile protection (regression: c4c91ae-style squash)
# ---------------------------------------------------------------------------
# Real incident: a closer running in push-to-main with parallel terminals
# rewrote scripts/dev-restart.profile.sh from a concrete app profile back to
# the neutral AnyStack stub, breaking dev-restart for every parallel terminal
# at once. The write_scope_guard now treats the profile as stack-specific
# config owned by the generated app, not by any single slice.


def test_blocks_dev_restart_profile_edit_while_task_active(tmp_project, monkeypatch):
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    reason = _denied(_run_hook(_payload("Write", "scripts/dev-restart.profile.sh")))
    assert "stack-specific dev profile" in reason
    assert "CLAUDE_ALLOW_DEV_PROFILE_WRITES" in reason


def test_blocks_dev_restart_dispatcher_edit_while_task_active(tmp_project, monkeypatch):
    """El dispatcher dev-restart.sh es código estático del orquestador. Tampoco
    se toca durante slice salvo override explícito."""
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    reason = _denied(_run_hook(_payload("Edit", "scripts/dev-restart.sh")))
    assert "stack-specific dev profile" in reason


def test_allows_dev_profile_edit_with_explicit_override(tmp_project, monkeypatch):
    """Mantenimiento intencional: generar/actualizar la app desde templates
    fuera del DAG → permitido con flag explícito."""
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P00-S01-T001")
    monkeypatch.setenv("CLAUDE_ALLOW_DEV_PROFILE_WRITES", "1")
    assert _run_hook(_payload("Write", "scripts/dev-restart.profile.sh")) == ""


def test_allows_dev_profile_edit_when_no_active_task(tmp_project, monkeypatch):
    """Sin TASK_ID activo el repo está en modo mantenimiento — el profile se
    puede editar libremente. El bloqueo aplica sólo durante slices."""
    monkeypatch.delenv("CLAUDE_ACTIVE_TASK_ID", raising=False)
    assert _run_hook(_payload("Write", "scripts/dev-restart.profile.sh")) == ""
