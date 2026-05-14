from __future__ import annotations

import sys

TASK_ID = "P00-S01-T001"


def test_init_verify_slice_handoff_writes_pending_skeleton(tmp_project):
    import init_verify_slice_handoff

    old = sys.argv
    try:
        sys.argv = ["init_verify_slice_handoff.py", TASK_ID]
        assert init_verify_slice_handoff.main() == 0
    finally:
        sys.argv = old

    path = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / f"{TASK_ID}.md"
    text = path.read_text(encoding="utf-8")
    assert "## verify-slice" in text
    assert f"TASK_ID: {TASK_ID}" in text
    assert "VERIFY_OUTCOME: pending" in text
    assert "MCP_BROWSER: pending" in text
    assert "CLAUDE_TRAILER:" in text
    assert "OUTCOME: blocked" in text


def test_init_verify_slice_handoff_is_idempotent_for_latest_pending(tmp_project):
    import init_verify_slice_handoff

    old = sys.argv
    try:
        sys.argv = ["init_verify_slice_handoff.py", TASK_ID]
        assert init_verify_slice_handoff.main() == 0
        assert init_verify_slice_handoff.main() == 0
    finally:
        sys.argv = old

    path = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / f"{TASK_ID}.md"
    assert path.read_text(encoding="utf-8").count("## verify-slice") == 1
