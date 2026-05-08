#!/usr/bin/env python3
"""Safely update journey verification state under orchestrator locks.

Slash commands should not hand-edit registry.json/runtime-state.json. This small
CLI wraps the same locked helpers used by the SubagentStop hook so
/verify-journey can mutate journey state without corrupting parallel DAG runs.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from common import (
    load_registry,
    load_runtime_state,
    remove_pending_journey_verification,
    waive_journey_verification,
)


def _known_journey_ids() -> set[str]:
    return {str(j.get("id")) for j in (load_registry().get("journeys", []) or []) if j.get("id")}


def update_journey(journey_id: str, outcome: str, *, waiver_reason: str | None = None) -> dict[str, Any]:
    journey_id = (journey_id or "").strip()
    outcome = (outcome or "").strip().lower()
    if not journey_id:
        return {"ok": False, "error": "missing JOURNEY_ID"}
    known = _known_journey_ids()
    if known and journey_id not in known:
        return {"ok": False, "error": f"unknown JOURNEY_ID: {journey_id}"}
    if outcome == "verified":
        remove_pending_journey_verification(journey_id, mark_verified=True)
    elif outcome == "waived":
        reason = (waiver_reason or "").strip()
        if not reason:
            return {"ok": False, "error": "waived requires --reason"}
        waive_journey_verification(journey_id, reason)
    else:
        return {"ok": False, "error": "outcome must be verified or waived"}
    runtime = load_runtime_state()
    registry = load_registry()
    journey = next((j for j in (registry.get("journeys", []) or []) if j.get("id") == journey_id), {})
    return {
        "ok": True,
        "journey_id": journey_id,
        "outcome": outcome,
        "verification_status": journey.get("verification_status"),
        "pending_journey_verifications": runtime.get("pending_journey_verifications", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Update journey verification state under locks")
    parser.add_argument("journey_id")
    parser.add_argument("--outcome", required=True, choices=["verified", "waived"])
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    result = update_journey(args.journey_id, args.outcome, waiver_reason=args.reason)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
