from __future__ import annotations

from pathlib import Path

TASK_ID = "P00-S01-T001"


def _seed(tmp_project: Path, *, status: str = "ready_for_close", last_updated_by: str | None = None) -> None:
    import common

    task: dict[str, object] = {
        "id": TASK_ID,
        "title": "slice under verify",
        "phase_id": "P00",
        "step_id": "P00-S01",
        "status": status,
        "depends_on": [],
    }
    if last_updated_by:
        task["last_updated_by"] = last_updated_by
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "TEST",
        "phase_order": ["P00"],
        "phases": [{"id": "P00", "title": "Phase", "status": "active", "task_ids": [TASK_ID]}],
        "tasks": [task],
        "journeys": [],
    })
    common.save_runtime_state({
        "generated_at": common.now_iso(),
        "last_worker": last_updated_by,
        "last_event": None,
        "pending_journey_verifications": [],
        "last_journey_verified": None,
    })
    pack = tmp_project / "orchestrator-state" / "tasks" / "task-packs" / f"{TASK_ID}.md"
    pack.parent.mkdir(parents=True, exist_ok=True)
    pack.write_text(f"# Pack\n\nTASK_ID: {TASK_ID}\n", encoding="utf-8")


def _write_handoff(tmp_project: Path, body: str) -> None:
    path = tmp_project / "orchestrator-state" / "tasks" / "handoffs" / f"{TASK_ID}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")



def _verified_block(heading: str = "## verify-slice") -> str:
    return f"""{heading}
- TASK_ID: {TASK_ID}
- AGENT: slice-verifier
- MCP_BROWSER: chrome-devtools
- VERIFY_OUTCOME: verified
- DATA_CONTRACT_ROWS: VDC-001
- DATA_SETUP: sandbox-user-1 + seeded record A
- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active
- FLOWS_TESTED: login happy path
- EVIDENCE: orchestrator-state/tasks/evidence/{TASK_ID}/verify-*
"""

def _ready_handoff(extra: str = "") -> str:
    return f"""# Handoff {TASK_ID}

## validator
- TASK_ID: {TASK_ID}
- OUTCOME: approved

## tester
- TASK_ID: {TASK_ID}
- OUTCOME: pass
{extra}
"""


def test_router_invokes_slice_verifier_when_validator_tester_are_ready(tmp_project):
    import verify_slice_state

    _seed(tmp_project)
    _write_handoff(tmp_project, _ready_handoff())

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_slice_verifier"
    assert result["ready_for_close_contract_ok"] is True
    assert result["verify_contract_ok"] is False


def test_router_relaunches_closer_after_premature_closer_block_and_verified_handoff(tmp_project):
    import verify_slice_state

    _seed(tmp_project, status="blocked", last_updated_by="closer")
    _write_handoff(tmp_project, _ready_handoff(f"""
{_verified_block()}"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_closer"
    assert "early_closer" in result["reason"]


def test_router_accepts_slice_verifier_heading_alias(tmp_project):
    import verify_slice_state

    _seed(tmp_project, status="verified_pending_close", last_updated_by="slice-verifier")
    _write_handoff(tmp_project, _ready_handoff(f"""
{_verified_block("### slice-verifier (cycle 2)")}"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_closer"
    assert result["verify_outcome"] == "verified"


def test_router_reads_verify_outcome_after_h3_machine_keys(tmp_project):
    import verify_slice_state

    _seed(tmp_project, status="verified_pending_close", last_updated_by="slice-verifier")
    _write_handoff(tmp_project, _ready_handoff(f"""
## verify-slice
### AGENT: slice-verifier
### TASK_ID: {TASK_ID}
### MCP_BROWSER: chrome-devtools
### VERIFY_OUTCOME: verified
### DATA_CONTRACT_ROWS: VDC-001
### DATA_SETUP: sandbox-user-1 + seeded record A
### PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active
### FLOWS_TESTED: login happy path
### EVIDENCE: orchestrator-state/tasks/evidence/{TASK_ID}/verify-*
"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_closer"
    assert result["verify_outcome"] == "verified"

def test_router_keeps_verify_section_through_h3_prose_subheading(tmp_project):
    import verify_slice_state

    _seed(tmp_project, status="verified_pending_close", last_updated_by="slice-verifier")
    _write_handoff(tmp_project, _ready_handoff(f"""
## verify-slice
### Evidence summary
- TASK_ID: {TASK_ID}
- AGENT: slice-verifier
- MCP_BROWSER: chrome-devtools
- VERIFY_OUTCOME: verified
- DATA_CONTRACT_ROWS: VDC-001
- DATA_SETUP: sandbox-user-1 + seeded record A
- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active
- FLOWS_TESTED: login happy path
- EVIDENCE: orchestrator-state/tasks/evidence/{TASK_ID}/verify-*
"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_closer"
    assert result["verify_outcome"] == "verified"



def test_router_accepts_agent360_browser_mcp_alias(tmp_project):
    import verify_slice_state

    _seed(tmp_project, status="verified_pending_close", last_updated_by="slice-verifier")
    _write_handoff(tmp_project, _ready_handoff(f"""
## verify-slice
- TASK_ID: {TASK_ID}
- AGENT: slice-verifier
- MCP_BROWSER: browser-mcp
- VERIFY_OUTCOME: verified
- DATA_CONTRACT_ROWS: VDC-001
- DATA_SETUP: sandbox-user-1 + seeded record A
- PERSISTED_DATA_OBSERVED: users/sandbox-user-1 active
- FLOWS_TESTED: login happy path with MFA
- EVIDENCE: orchestrator-state/tasks/evidence/{TASK_ID}/verify-*
"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_closer"
    assert result["verify_outcome"] == "verified"

def test_router_sends_verify_issues_to_debugger_or_followup_triage(tmp_project):
    import verify_slice_state

    _seed(tmp_project, status="needs_debug", last_updated_by="slice-verifier")
    _write_handoff(tmp_project, _ready_handoff(f"""
## verify-slice
- TASK_ID: {TASK_ID}
- VERIFY_OUTCOME: issues_found
"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_debugger_or_register_followup"


def test_router_blocks_when_task_pack_is_missing(tmp_project):
    import verify_slice_state

    _seed(tmp_project)
    (tmp_project / "orchestrator-state" / "tasks" / "task-packs" / f"{TASK_ID}.md").unlink()
    _write_handoff(tmp_project, _ready_handoff())

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "blocked"
    assert result["reason"] == "precondition_failed"


def test_router_blocks_when_verify_slice_blocked_by_mcp(tmp_project):
    import verify_slice_state

    _seed(tmp_project, status="blocked", last_updated_by="slice-verifier")
    _write_handoff(tmp_project, _ready_handoff(f"""
## verify-slice
- TASK_ID: {TASK_ID}
- VERIFY_OUTCOME: blocked
- BLOCKER_KIND: browser_mcp_unavailable
"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "blocked"
    assert "blocked" in result["reason"]


def test_router_relaunches_slice_verifier_for_pending_skeleton(tmp_project):
    import verify_slice_state

    _seed(tmp_project)
    _write_handoff(tmp_project, _ready_handoff(f"""
## verify-slice
- TASK_ID: {TASK_ID}
- VERIFY_OUTCOME: pending
"""))

    result = verify_slice_state.classify(TASK_ID)
    assert result["action"] == "invoke_slice_verifier"
    assert "pending" in result["reason"]
