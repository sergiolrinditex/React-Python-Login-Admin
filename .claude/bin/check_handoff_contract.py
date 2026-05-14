#!/usr/bin/env python3
"""Validate per-task handoff contract before verify/close.

Slice: P02-S03-T007 — Fix check_handoff_contract.py worktree path bug in pr-flow.
Phase: P02 / P02-S03.

This is intentionally small and text-based: handoffs are Markdown written by
agents, but closer depends on a few machine-readable result lines surviving
`/clear`. The chat trailer is not enough for close-time audit.

Key dependency: ``common.py`` — provides ``handoff_path``, ``project_root``,
``workspace_root``, ``workspace_relpath`` and ``STATE_DIR_NAME``.

In pr-flow every TASK_ID runs in a dedicated git worktree. The handoff lives
in the worktree during the slice and in canonical after squash-merge + cleanup.
``_resolve_handoff_path`` tries both locations so the close-gate works
regardless of *when* and *from where* ``check-handoff-contract.sh`` is called.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from common import (
    STATE_DIR_NAME,
    handoff_path as _handoff_path_from_workspace,
    project_root,
    workspace_relpath,
)

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
KEY_RE = re.compile(r"^\s*-?\s*(?P<key>[A-Za-z][A-Za-z0-9_]*):\s*(?P<value>.*?)\s*$")
CYCLE_SUFFIX_RE = re.compile(r"\s*\((?:cycle|ciclo)\s+\d+\)\s*$", re.IGNORECASE)

VALIDATOR_OUTCOMES = {"approved", "changes_requested", "blocked"}
TESTER_OUTCOMES = {"pass", "fail", "blocked"}
VERIFY_OUTCOMES = {"verified", "issues_found"}
SCREEN_JOURNEY_OUTCOMES = {"approved", "changes_requested", "blocked"}
FOLLOWUP_ID_RE = re.compile(r"\bFU-[A-Za-z0-9_.:-]+\b")
FOLLOWUP_CANDIDATE_RE = re.compile(
    r"(?im)^\s*-?\s*(followup_candidate|FOLLOWUP_REQUIRED)\s*:\s*(yes|true|si|sí)\s*$"
)

_VERBOSE = os.environ.get("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def _vlog(msg: str) -> None:
    """Write a verbose-mode diagnostic line to stderr.

    Guarded by ENABLE_VERBOSE_LOGGING env. The script is a CLI invoked by
    hooks; BEFORE/AFTER semantics are carried by docstrings and these calls
    so the ledger can reconstruct the full resolution trace when debugging.
    """
    if _VERBOSE:
        print(f"[check_handoff_contract] {msg}", file=sys.stderr)


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


def _resolve_handoff_path(task_id: str) -> Path:
    """Locate the handoff file for *task_id* using a two-candidate fallback.

    BEFORE: looks up workspace candidate A (per-slice worktree path via
    ``common.handoff_path``), then canonical candidate B (canonical repo root
    via ``common.project_root``).  Returns the first path that exists.

    Resolution order (workspace-authoritative during slice, canonical after
    squash-merge + worktree cleanup):

    1. **Candidate A — workspace**: ``common.handoff_path(task_id)`` which
       resolves through ``workspace_root()`` (honours ``CLAUDE_WORKTREE_ROOT``,
       ``CLAUDE_WORKSPACE_ROOT``, ``CLAUDE_PROJECT_DIR``, or cwd).
    2. **Candidate B — canonical**: ``project_root() / STATE_DIR_NAME /
       "tasks" / "handoffs" / "{task_id}.md"``.  ``project_root()`` honours
       ``CLAUDE_ORCHESTRATOR_ROOT`` so an explicit override always wins.
    3. **Fallback**: returns Candidate A (preserves the existing "missing
       handoff: <workspace-path>" error message the closer gate expects).

    AFTER: returns a ``Path`` that exists, or Candidate A if neither exists.
    Side effect: none (read-only lookup).

    Args:
        task_id: The TASK_ID string (e.g. ``"P02-S03-T007"``).

    Returns:
        ``Path`` to the first existing handoff, or the workspace candidate
        path as the canonical "where it should be" placeholder.
    """
    candidate_a = _handoff_path_from_workspace(task_id)
    _vlog(f"BEFORE _resolve_handoff_path task_id={task_id!r} candidate_A={candidate_a}")

    if candidate_a.exists():
        _vlog(f"AFTER _resolve_handoff_path: resolved via workspace A={candidate_a}")
        return candidate_a

    # Candidate B: canonical root (may equal workspace if not in a worktree).
    try:
        canonical_dir = project_root() / STATE_DIR_NAME / "tasks" / "handoffs"
        candidate_b = canonical_dir / f"{task_id}.md"
        _vlog(f"candidate_A miss → trying canonical B={candidate_b}")
        if candidate_b.exists():
            _vlog(
                f"AFTER _resolve_handoff_path: resolved via canonical B={candidate_b}"
            )
            return candidate_b
    except Exception as exc:
        # project_root() is best-effort; swallow and fall through to Candidate A.
        _vlog(f"canonical candidate resolution failed: {type(exc).__name__}: {exc}")

    _vlog(
        f"AFTER _resolve_handoff_path: neither candidate exists; "
        f"returning workspace A={candidate_a} for missing-message"
    )
    return candidate_a


def _canonical_section_name(raw: str) -> str:
    """Normalize agent-written handoff headings to the contract keys.

    Claude agents sometimes append cycle labels or use short headings, e.g.
    ``## validator`` and ``## validator (cycle 2)``. The contract should read
    the latest logical section, not fail on harmless heading decoration.
    """
    value = CYCLE_SUFFIX_RE.sub("", raw.strip().lower()).replace("_", " ")
    value = re.sub(r"\s+", " ", value).strip()
    compact = re.sub(r"[\s/_-]+", " ", value).strip()

    if compact.startswith("validator") or compact.startswith("validation"):
        return "validator review"
    if (
        compact.startswith("tester")
        or compact.startswith("test run")
        or compact in {"tests", "test"}
    ):
        return "tester run"
    if compact.startswith("verify slice"):
        return "verify-slice"
    if compact.startswith("verify journey"):
        return "verify-journey"
    if "screen" in compact and "journey" in compact and "review" in compact:
        return "screen/journey review"
    return value


def _display_path(path: Path) -> str:
    return workspace_relpath(path)


def _parse_sections(text: str) -> Dict[str, List[Tuple[str, str]]]:
    sections: Dict[str, List[Tuple[str, str]]] = {}
    current = "__preamble__"
    sections[current] = []
    for line in text.splitlines():
        sec = SECTION_RE.match(line)
        if sec:
            current = _canonical_section_name(sec.group(1))
            sections.setdefault(current, [])
            continue
        key = KEY_RE.match(line)
        if key:
            sections.setdefault(current, []).append(
                (key.group("key"), key.group("value").strip())
            )
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


def validate(
    task_id: str,
    *,
    require_ready_for_close: bool,
    require_verify_slice: bool,
    require_screen_journey_review: bool = False,
) -> tuple[bool, list[str], dict[str, object]]:
    path = _resolve_handoff_path(task_id)
    errors: list[str] = []
    details: dict[str, object] = {"task_id": task_id, "handoff": _display_path(path)}
    if not path.exists():
        return False, [f"missing handoff: {_display_path(path)}"], details
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = _parse_sections(text)

    if _has_unregistered_followup_candidate(text):
        errors.append(
            "handoff contains followup_candidate/FOLLOWUP_REQUIRED=yes but no formal FOLLOWUP_ID; "
            "register it with ./scripts/register-followup-task.sh propose before close"
        )

    mismatches = [
        (sec, val)
        for sec, val in _all_task_ids(sections)
        if val and val != task_id and not val.startswith("<")
    ]
    if mismatches:
        errors.append(
            "handoff contains TASK_ID lines for another task: "
            + ", ".join(f"{sec}={val}" for sec, val in mismatches)
        )

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
            errors.append(
                "missing Validator review OUTCOME line in handoff; chat trailer is not enough for closer"
            )
        elif val_outcome not in VALIDATOR_OUTCOMES:
            errors.append(f"invalid Validator review OUTCOME={val_outcome!r}")
        elif val_outcome != "approved":
            errors.append(f"validator did not approve: OUTCOME={val_outcome}")

        tester_outcome = tester.get("OUTCOME")
        if not tester_outcome:
            errors.append(
                "missing Tester run OUTCOME line in handoff; chat trailer is not enough for closer"
            )
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
                errors.append(
                    f"verify-slice TASK_ID mismatch: {verify_tid} != {task_id}"
                )
            if not verify_outcome:
                errors.append("missing verify-slice VERIFY_OUTCOME line in handoff")
            elif verify_outcome not in VERIFY_OUTCOMES:
                errors.append(f"invalid verify-slice VERIFY_OUTCOME={verify_outcome!r}")
            elif verify_outcome != "verified":
                errors.append(
                    f"verify-slice not verified: VERIFY_OUTCOME={verify_outcome}"
                )

    if require_screen_journey_review:
        if not screen_review:
            errors.append("missing ## Screen/Journey review section in handoff")
        else:
            review_tid = screen_review.get("TASK_ID")
            if not review_tid:
                errors.append("missing Screen/Journey review TASK_ID line in handoff")
            elif review_tid != task_id and not review_tid.startswith("<"):
                errors.append(
                    f"Screen/Journey review TASK_ID mismatch: {review_tid} != {task_id}"
                )
            review_outcome = screen_review.get("OUTCOME")
            if not review_outcome:
                errors.append("missing Screen/Journey review OUTCOME line in handoff")
            elif review_outcome not in SCREEN_JOURNEY_OUTCOMES:
                errors.append(
                    f"invalid Screen/Journey review OUTCOME={review_outcome!r}"
                )
            elif review_outcome != "approved":
                errors.append(
                    f"screen/journey reviewer did not approve: OUTCOME={review_outcome}"
                )
            for key in (
                "visual_contract_checked",
                "required_states_covered",
                "real_data_or_backend_used",
                "visual_evidence_present",
            ):
                if key not in screen_review:
                    errors.append(
                        f"missing Screen/Journey review {key} line in handoff"
                    )

    return not errors, errors, details


def main() -> int:
    """CLI entry point for the handoff contract checker.

    Exit codes:
      0 — contract satisfied (ok=True).
      1 — argument error (argparse).
      2 — contract failed OR missing handoff OR internal error.

    The body is wrapped in ``try/except Exception`` so any unexpected crash
    (e.g. filesystem permission error, encoding edge-case, import side-effect)
    produces a clean ``internal error`` line on stderr rather than a Python
    traceback that could confuse the closer gate. ``SystemExit`` and
    ``KeyboardInterrupt`` are intentionally NOT caught — they propagate normally.
    """
    parser = argparse.ArgumentParser(
        description="Validate TASK_ID handoff before verify/close."
    )
    parser.add_argument("task_id")
    parser.add_argument(
        "--require-ready-for-close",
        action="store_true",
        help="Require Validator review OUTCOME=approved and Tester run OUTCOME=pass.",
    )
    parser.add_argument(
        "--require-verify-slice",
        action="store_true",
        help="Require ## verify-slice with matching TASK_ID and VERIFY_OUTCOME=verified.",
    )
    parser.add_argument(
        "--require-screen-journey-review",
        action="store_true",
        help="Require ## Screen/Journey review with matching TASK_ID and OUTCOME=approved.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
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
    except Exception as exc:  # noqa: BLE001 — intentional: CLI must never traceback
        print(f"Handoff contract FAILED — {args.task_id}", file=sys.stderr)
        print(f"- internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
