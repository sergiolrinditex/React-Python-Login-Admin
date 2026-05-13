#!/usr/bin/env python3
"""Validate per-task handoff contract before verify/close.

This is intentionally small and text-based: handoffs are Markdown written by
agents, but closer depends on a few machine-readable result lines surviving
`/clear`. The chat trailer is not enough for close-time audit.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from common import handoff_path as _handoff_path_resolver, project_root

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
KEY_RE = re.compile(r"^\s*-?\s*(?P<key>[A-Za-z][A-Za-z0-9_]*):\s*(?P<value>.*?)\s*$")

VALIDATOR_OUTCOMES = {"approved", "changes_requested", "blocked"}
TESTER_OUTCOMES = {"pass", "fail", "blocked"}
VERIFY_OUTCOMES = {"verified", "issues_found"}
SCREEN_JOURNEY_OUTCOMES = {"approved", "changes_requested", "blocked"}
FOLLOWUP_ID_RE = re.compile(r"\bFU-[A-Za-z0-9_.:-]+\b")
FOLLOWUP_CANDIDATE_RE = re.compile(r"(?im)^\s*-?\s*(followup_candidate|FOLLOWUP_REQUIRED)\s*:\s*(yes|true|si|sí)\s*$")


def _has_unregistered_followup_candidate(text: str) -> bool:
    """Return True when a handoff says work needs FU but no FU id exists.

    In DAG-only flow, productive work outside the current TASK_ID must be a
    formal proposed FU before close. It must not remain as prose in validator,
    tester, debugger, verify-slice or screen/journey review sections.
    """
    if not FOLLOWUP_CANDIDATE_RE.search(text):
        return False
    if FOLLOWUP_ID_RE.search(text):
        return False
    if re.search(r"(?im)^\s*-?\s*FOLLOWUP_ID\s*:\s*FU-", text):
        return False
    return True


def _handoff_path(task_id: str) -> Path:
    # FW-024: per-slice files (handoff) live in workspace_root, which is the
    # per-TASK_ID worktree in pr-flow and the canonical repo in push-to-main.
    return _handoff_path_resolver(task_id)


def _parse_sections(text: str) -> Dict[str, List[Tuple[str, str]]]:
    sections: Dict[str, List[Tuple[str, str]]] = {}
    current = "__preamble__"
    sections[current] = []
    for line in text.splitlines():
        sec = SECTION_RE.match(line)
        if sec:
            current = sec.group(1).strip().lower()
            sections.setdefault(current, [])
            continue
        key = KEY_RE.match(line)
        if key:
            sections.setdefault(current, []).append((key.group("key"), key.group("value").strip()))
    return sections


def _latest(sections: Dict[str, List[Tuple[str, str]]], name: str) -> Dict[str, str]:
    """Return last key occurrence in a named section."""
    out: Dict[str, str] = {}
    for key, value in sections.get(name.lower(), []):
        out[key] = value
    return out


def _all_task_ids(sections: Dict[str, List[Tuple[str, str]]]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for section, pairs in sections.items():
        for key, value in pairs:
            if key == "TASK_ID":
                found.append((section, value))
    return found


def validate(task_id: str, *, require_ready_for_close: bool, require_verify_slice: bool, require_screen_journey_review: bool = False) -> tuple[bool, list[str], dict[str, object]]:
    path = _handoff_path(task_id)
    errors: list[str] = []
    details: dict[str, object] = {"task_id": task_id, "handoff": str(path.relative_to(project_root()))}
    if not path.exists():
        return False, [f"missing handoff: {path.relative_to(project_root())}"], details
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = _parse_sections(text)

    if _has_unregistered_followup_candidate(text):
        errors.append(
            "handoff contains followup_candidate/FOLLOWUP_REQUIRED=yes but no formal FOLLOWUP_ID; "
            "register it with ./scripts/register-followup-task.sh propose before close"
        )

    mismatches = [(sec, val) for sec, val in _all_task_ids(sections) if val and val != task_id and not val.startswith("<")]
    if mismatches:
        errors.append("handoff contains TASK_ID lines for another task: " + ", ".join(f"{sec}={val}" for sec, val in mismatches))

    validator = _latest(sections, "validator review")
    tester = _latest(sections, "tester run")
    verify = _latest(sections, "verify-slice")
    screen_review = _latest(sections, "screen/journey review")
    details["validator"] = validator
    details["tester"] = tester
    details["verify_slice"] = verify
    details["screen_journey_review"] = screen_review

    if require_ready_for_close:
        val_outcome = validator.get("OUTCOME")
        if not val_outcome:
            errors.append("missing Validator review OUTCOME line in handoff; chat trailer is not enough for closer")
        elif val_outcome not in VALIDATOR_OUTCOMES:
            errors.append(f"invalid Validator review OUTCOME={val_outcome!r}")
        elif val_outcome != "approved":
            errors.append(f"validator did not approve: OUTCOME={val_outcome}")

        tester_outcome = tester.get("OUTCOME")
        if not tester_outcome:
            errors.append("missing Tester run OUTCOME line in handoff; chat trailer is not enough for closer")
        elif tester_outcome not in TESTER_OUTCOMES:
            errors.append(f"invalid Tester run OUTCOME={tester_outcome!r}")
        elif tester_outcome != "pass":
            errors.append(f"tester did not pass: OUTCOME={tester_outcome}")

    if require_verify_slice:
        verify_outcome = verify.get("VERIFY_OUTCOME")
        if not verify:
            errors.append("missing ## verify-slice section in handoff")
        else:
            verify_tid = verify.get("TASK_ID")
            if not verify_tid:
                errors.append("missing verify-slice TASK_ID line in handoff")
            elif verify_tid != task_id and not verify_tid.startswith("<"):
                errors.append(f"verify-slice TASK_ID mismatch: {verify_tid} != {task_id}")
            if not verify_outcome:
                errors.append("missing verify-slice VERIFY_OUTCOME line in handoff")
            elif verify_outcome not in VERIFY_OUTCOMES:
                errors.append(f"invalid verify-slice VERIFY_OUTCOME={verify_outcome!r}")
            elif verify_outcome != "verified":
                errors.append(f"verify-slice not verified: VERIFY_OUTCOME={verify_outcome}")


    if require_screen_journey_review:
        if not screen_review:
            errors.append("missing ## Screen/Journey review section in handoff")
        else:
            review_tid = screen_review.get("TASK_ID")
            if not review_tid:
                errors.append("missing Screen/Journey review TASK_ID line in handoff")
            elif review_tid != task_id and not review_tid.startswith("<"):
                errors.append(f"Screen/Journey review TASK_ID mismatch: {review_tid} != {task_id}")
            review_outcome = screen_review.get("OUTCOME")
            if not review_outcome:
                errors.append("missing Screen/Journey review OUTCOME line in handoff")
            elif review_outcome not in SCREEN_JOURNEY_OUTCOMES:
                errors.append(f"invalid Screen/Journey review OUTCOME={review_outcome!r}")
            elif review_outcome != "approved":
                errors.append(f"screen/journey reviewer did not approve: OUTCOME={review_outcome}")
            for key in ("visual_contract_checked", "required_states_covered", "real_data_or_backend_used", "visual_evidence_present"):
                if key not in screen_review:
                    errors.append(f"missing Screen/Journey review {key} line in handoff")

    return not errors, errors, details


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TASK_ID handoff before verify/close.")
    parser.add_argument("task_id")
    parser.add_argument("--require-ready-for-close", action="store_true", help="Require Validator review OUTCOME=approved and Tester run OUTCOME=pass.")
    parser.add_argument("--require-verify-slice", action="store_true", help="Require ## verify-slice with matching TASK_ID and VERIFY_OUTCOME=verified.")
    parser.add_argument("--require-screen-journey-review", action="store_true", help="Require ## Screen/Journey review with matching TASK_ID and OUTCOME=approved.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    ok, errors, details = validate(
        args.task_id,
        require_ready_for_close=args.require_ready_for_close,
        require_verify_slice=args.require_verify_slice,
        require_screen_journey_review=args.require_screen_journey_review,
    )
    payload = {"ok": ok, "errors": errors, **details}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if ok:
            print(f"Handoff contract OK — {args.task_id}")
        else:
            print(f"Handoff contract FAILED — {args.task_id}", file=sys.stderr)
            for err in errors:
                print(f"- {err}", file=sys.stderr)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
