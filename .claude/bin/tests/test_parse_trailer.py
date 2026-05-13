"""Trailer parsing — pieza más crítica del SubagentStop hook.

Si el regex se rompe o silenciosamente ignora una línea, todo el state-management
del registry se desincroniza. Cubrimos los casos canónicos + edge cases que han
mordido en el pasado (espacios al final, líneas en medio del mensaje, mayúsculas).
"""
from __future__ import annotations

import hook_capture_subagent_stop as hook


def test_parse_trailer_canonical():
    # IMPORTANTE: las claves del trailer deben ir AL INICIO DE LÍNEA (regex
    # `^TASK_ID:` con re.MULTILINE). Si el agente indenta el trailer, no
    # matchea — comportamiento intencional para distinguir trailer real de
    # texto narrativo que mencione "TASK_ID" en medio de un párrafo.
    text = (
        "Some narrative text from the agent.\n"
        "\n"
        "TASK_ID: P02-S03-T004\n"
        "OUTCOME: pass\n"
        "NEXT_STATUS: ready_for_close\n"
        "HANDOFF: orchestrator-state/tasks/handoffs/P02-S03-T004.md\n"
        "EVIDENCE: orchestrator-state/tasks/evidence/P02-S03-T004\n"
    )
    out = hook.parse_trailer(text)
    assert out == {
        "task_id": "P02-S03-T004",
        "outcome": "pass",
        "next_status": "ready_for_close",
        "handoff": "orchestrator-state/tasks/handoffs/P02-S03-T004.md",
        "evidence": "orchestrator-state/tasks/evidence/P02-S03-T004",
    }


def test_parse_trailer_indented_lines_are_ignored_by_design():
    """Si el agente accidentalmente indenta el trailer, el hook NO lo parsea.
    Documentado como comportamiento intencional: evita falsos positivos cuando
    el agente menciona 'TASK_ID:' en medio de un párrafo."""
    text = "    TASK_ID: P00-S01-T001\n    OUTCOME: pass\n"
    assert hook.parse_trailer(text) == {}


def test_parse_trailer_handles_trailing_whitespace():
    text = "TASK_ID: P00-S01-T001   \nOUTCOME: approved\t\nNEXT_STATUS: ready_for_close \n"
    out = hook.parse_trailer(text)
    assert out["task_id"] == "P00-S01-T001"
    assert out["outcome"] == "approved"
    assert out["next_status"] == "ready_for_close"


def test_parse_trailer_partial_trailer():
    """Un agente puede emitir solo TASK_ID + OUTCOME (ej. researcher)."""
    text = "TASK_ID: P00-S01-T001\nOUTCOME: ok\n"
    out = hook.parse_trailer(text)
    assert out == {"task_id": "P00-S01-T001", "outcome": "ok"}


def test_parse_trailer_empty_returns_empty_dict():
    assert hook.parse_trailer("") == {}
    assert hook.parse_trailer(None) == {}


def test_parse_journey_pending_single():
    text = "JOURNEY_PENDING_VERIFY: J101\n"
    out = hook.parse_journey_trailer(text)
    assert out["pending"] == ["J101"]
    assert out["verify_journey_id"] is None


def test_parse_journey_pending_multiple_dedup_preserves_order():
    """Una slice puede cerrar varios journeys; debe deduplicar manteniendo orden."""
    text = (
        "JOURNEY_PENDING_VERIFY: J101\n"
        "JOURNEY_PENDING_VERIFY: J203\n"
        "JOURNEY_PENDING_VERIFY: J101\n"
    )
    out = hook.parse_journey_trailer(text)
    assert out["pending"] == ["J101", "J203"]


def test_parse_journey_verify_outcome():
    text = "JOURNEY_ID: J101\nJOURNEY_VERIFY_OUTCOME: verified\n"
    out = hook.parse_journey_trailer(text)
    assert out["verify_journey_id"] == "J101"
    assert out["verify_outcome"] == "verified"
    assert out["waiver_reason"] is None


def test_parse_journey_waiver_with_reason_with_spaces():
    text = "JOURNEY_ID: J101\nJOURNEY_VERIFY_WAIVED: explicit human override 2026-04-26\n"
    out = hook.parse_journey_trailer(text)
    assert out["verify_journey_id"] == "J101"
    assert out["waiver_reason"] == "explicit human override 2026-04-26"


def test_parse_journey_no_lines_returns_empty_pending():
    out = hook.parse_journey_trailer("nothing journey here")
    assert out["pending"] == []
    assert out["verify_journey_id"] is None
    assert out["verify_outcome"] is None
    assert out["waiver_reason"] is None


def test_parse_journey_ignores_inline_substring():
    """JOURNEY_PENDING_VERIFY tiene que estar al inicio de línea (^), no inline."""
    text = "Antes de cerrar (JOURNEY_PENDING_VERIFY: J999) revisa esto."
    out = hook.parse_journey_trailer(text)
    assert out["pending"] == []


# ---------------------------------------------------------------------------
# Handoff fallback recovery
# ---------------------------------------------------------------------------
# Caso real: el agente edita el handoff (170 líneas, decisiones, evidencia)
# y se queda a mitad del mensaje final SIN llegar a emitir el bloque
# CLAUDE_TRAILER en stdin. El SubagentStop hook no recibe trailer → registry
# nunca avanza. La recuperación desde el handoff cierra esa grieta sin
# violar el resto del contrato.


def test_recover_trailer_from_handoff_when_stdin_empty(tmp_project, monkeypatch):
    """Si stdin trailer vacío pero el handoff tiene CLAUDE_TRAILER, recuperar."""
    import hook_capture_subagent_stop as h
    monkeypatch.setenv("CLAUDE_ACTIVE_TASK_ID", "P02-S03-T001")

    handoff = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / "P02-S03-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "# Handoff P02-S03-T001\n\n"
        "## developer\n"
        "...170 líneas de decisión, código, tests, evidencia...\n\n"
        "CLAUDE_TRAILER:\n"
        "AGENT: developer\n"
        "TASK_ID: P02-S03-T001\n"
        "OUTCOME: success\n"
        "NEXT_STATUS: validator_tester_pending\n"
        "HANDOFF: orchestrator-state/tasks/handoffs/P02-S03-T001.md\n"
        "EVIDENCE: orchestrator-state/tasks/evidence/P02-S03-T001\n",
        encoding="utf-8",
    )

    recovered = h.recover_trailer_from_handoff("P02-S03-T001", "developer")
    assert recovered["task_id"] == "P02-S03-T001"
    assert recovered["outcome"] == "success"
    assert recovered["next_status"] == "validator_tester_pending"


def test_recover_trailer_returns_empty_when_no_handoff_file(tmp_project):
    """Si el handoff aún no existe, devuelve {} sin error."""
    import hook_capture_subagent_stop as h
    assert h.recover_trailer_from_handoff("P99-S99-T999", "developer") == {}


def test_recover_trailer_returns_empty_when_no_trailer_marker(tmp_project):
    """Handoff existe pero no contiene CLAUDE_TRAILER → devuelve {}."""
    import hook_capture_subagent_stop as h
    handoff = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / "P02-S03-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("# Handoff sin trailer\n\nsólo notas humanas\n", encoding="utf-8")
    assert h.recover_trailer_from_handoff("P02-S03-T001", "developer") == {}


def test_recover_trailer_rejects_when_agent_mismatch(tmp_project):
    """El handoff es acumulativo. Si el último bloque CLAUDE_TRAILER fue
    escrito por developer pero ahora termina validator (que no ha escrito su
    propio bloque), el fallback NO debe devolver el trailer de developer."""
    import hook_capture_subagent_stop as h
    handoff = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / "P02-S03-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "## developer\n"
        "CLAUDE_TRAILER:\n"
        "AGENT: developer\n"
        "TASK_ID: P02-S03-T001\n"
        "OUTCOME: success\n",
        encoding="utf-8",
    )
    # validator pide recuperar pero el último trailer es de developer →
    # mismatch → {}
    assert h.recover_trailer_from_handoff("P02-S03-T001", "validator") == {}


def test_recover_trailer_rejects_when_task_id_mismatch(tmp_project):
    """Defensa adicional: si el trailer del handoff declara otro TASK_ID,
    es señal de que se está leyendo un handoff equivocado. Rechazar."""
    import hook_capture_subagent_stop as h
    handoff = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / "P02-S03-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "CLAUDE_TRAILER:\n"
        "AGENT: developer\n"
        "TASK_ID: P99-S99-T999\n"        # WRONG task
        "OUTCOME: success\n",
        encoding="utf-8",
    )
    assert h.recover_trailer_from_handoff("P02-S03-T001", "developer") == {}


def test_recover_trailer_picks_last_block_in_cumulative_handoff(tmp_project):
    """Cuando hay varios bloques CLAUDE_TRAILER (developer, validator, tester),
    parse_trailer toma el último — el del subagente que acaba de terminar."""
    import hook_capture_subagent_stop as h
    handoff = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / "P02-S03-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "## developer\n"
        "CLAUDE_TRAILER:\n"
        "AGENT: developer\n"
        "TASK_ID: P02-S03-T001\n"
        "OUTCOME: success\n"
        "NEXT_STATUS: validator_tester_pending\n\n"
        "## tester\n"
        "CLAUDE_TRAILER:\n"
        "AGENT: tester\n"
        "TASK_ID: P02-S03-T001\n"
        "OUTCOME: pass\n"
        "NEXT_STATUS: ready_for_close\n",
        encoding="utf-8",
    )
    recovered = h.recover_trailer_from_handoff("P02-S03-T001", "tester")
    assert recovered["outcome"] == "pass"
    assert recovered["next_status"] == "ready_for_close"


def test_recover_trailer_works_without_agent_marker(tmp_project):
    """AGENT: es opcional. Si no está, no se puede verificar pero tampoco
    se rechaza — el lock de stdin trailer ya hizo su trabajo de scope check."""
    import hook_capture_subagent_stop as h
    handoff = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / "P02-S03-T001.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "CLAUDE_TRAILER:\n"
        "TASK_ID: P02-S03-T001\n"
        "OUTCOME: success\n"
        "NEXT_STATUS: validator_tester_pending\n",
        encoding="utf-8",
    )
    recovered = h.recover_trailer_from_handoff("P02-S03-T001", "developer")
    assert recovered["outcome"] == "success"


def test_recover_trailer_empty_task_id_returns_empty(tmp_project):
    """Sin task_id no hay cómo localizar el handoff → {} sin tocar disco."""
    import hook_capture_subagent_stop as h
    assert h.recover_trailer_from_handoff(None, "developer") == {}
    assert h.recover_trailer_from_handoff("", "developer") == {}
