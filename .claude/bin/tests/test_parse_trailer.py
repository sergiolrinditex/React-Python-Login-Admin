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
