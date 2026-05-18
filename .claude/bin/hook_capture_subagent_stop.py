#!/usr/bin/env python3
"""SubagentStop hook — state synchronization.

Parses the trailer lines (TASK_ID / OUTCOME / NEXT_STATUS / HANDOFF / EVIDENCE)
and syncs the registry + runtime-state + ledger outside `.claude`. NEVER blocks the subagent,
NEVER denies the stop. If the trailer is missing the closer can catch it,
but the pipeline is free to continue.

Journey extension (added by journey-verification feature):
- Parses optional `JOURNEY_PENDING_VERIFY: <JID>` lines (closer emits one or more
  when a slice closes the last task of a journey). Adds them to
  runtime-state.pending_journey_verifications.
- Parses `JOURNEY_VERIFY_OUTCOME: verified|issues_found` + `JOURNEY_ID: <JID>`
  (emitted by /verify-journey command). On `verified`, removes the journey from
  pending and marks it verified in registry.journeys[].
- Parses `JOURNEY_VERIFY_WAIVED: <reason>` together with `JOURNEY_ID: <JID>`.
  On waiver, removes from pending and marks `verification_status: waived`.
All journey logic is best-effort and never blocks the hook.
"""
from __future__ import annotations

import json
import re
import sys

from common import (
    dag_worker_task_id,
    add_pending_journey_verification,
    reconcile_runtime_state,
    append_jsonl,
    bump_spawn_count,
    file_lock,
    find_task,
    get_spawn_budget,
    handoff_path,
    ledger_path,
    journeys_closing_at_task,
    load_registry,
    load_runtime_state,
    log_hook_error,
    now_iso,
    promote_ready_tasks,
    registry_path,
    remove_pending_journey_verification,
    runtime_state_path,
    save_registry,
    save_runtime_state,
    sync_runtime_state_from_registry,
    waive_journey_verification,
)

# Generic trailer key parser. Keep the parser schema-flexible: the schema
# controls which keys are required per role, while this parser accepts any
# UPPER_SNAKE_CASE key in the explicit CLAUDE_TRAILER block. This prevents
# new info-only fields such as VERIFY_OUTCOME, NEXT_ACTION or CONTEXT_READY
# from being silently dropped and then reported as missing by the hook.
TRAILER_LINE_RE = re.compile(r"^(?P<key>[A-Z][A-Z0-9_]*):\s*(?P<value>.*?)\s*$", re.MULTILINE)

def load_enum_contracts() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Load role enums from `.claude/orchestrator-contract.json`.

    The runtime schema is single-source. If the schema is unavailable or a role
    is missing, the hook logs a visible error and refuses lifecycle mutation
    rather than accepting stale enum copies.
    """
    roles = load_role_schema()
    outcomes: dict[str, set[str]] = {}
    statuses: dict[str, set[str]] = {}
    for role, spec in roles.items():
        outcome_values = spec.get("outcome_values") or []
        next_status_values = spec.get("next_status_values") or []
        if outcome_values:
            outcomes[str(role)] = {str(x).lower() for x in outcome_values}
        if next_status_values:
            statuses[str(role)] = {str(x).lower() for x in next_status_values}
    return outcomes, statuses

# Fenced JSON trailer fallback. Some agents emit code blocks more reliably
# than line-prefixed plain text; this lets them produce a structured trailer
# even when their narrative wraps long lines or indents the body.
JSON_TRAILER_RE = re.compile(
    r"```(?:json)?\s*\n(\{.*?\})\s*\n```",
    re.DOTALL,
)




def role_spec(agent_type: str | None) -> dict[str, object]:
    if not agent_type:
        return {}
    return load_role_schema().get(agent_type, {})


def role_is_info_only(agent_type: str | None) -> bool:
    return bool(role_spec(agent_type).get("info_only"))


def role_can_write_registry_metadata(agent_type: str | None) -> bool:
    spec = role_spec(agent_type)
    return bool(spec and (spec.get("info_only") or spec.get("mutates_registry_lifecycle")))


def role_mutates_lifecycle(agent_type: str | None) -> bool:
    return bool(role_spec(agent_type).get("mutates_registry_lifecycle"))


def parse_json_trailer(text: str) -> dict[str, str]:
    """Best-effort parse of a fenced JSON block that contains a
    ``claude_trailer`` object. Returns the same shape as parse_trailer.

    Accepted shapes (any of):
      ```json
      {"claude_trailer": {"TASK_ID": "...", "OUTCOME": "...", ...}}
      ```
      ```
      {"TASK_ID": "...", "OUTCOME": "..."}
      ```
    Keys are case-insensitive and normalized to the same lowercase keys
    parse_trailer uses.
    """
    if not text:
        return {}
    blocks = JSON_TRAILER_RE.findall(text)
    for raw in blocks:
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("claude_trailer"), dict):
            obj = obj["claude_trailer"]
        if not isinstance(obj, dict):
            continue
        # Normalize all explicit trailer keys to lowercase. Required/allowed
        # validation happens later from .claude/orchestrator-contract.json;
        # parsing must not have a stale allowlist.
        normalised: dict[str, str] = {}
        for k, v in obj.items():
            kk = str(k).strip().lower()
            if kk and v is not None:
                normalised[kk] = str(v).strip()
        if normalised:
            return normalised
    return {}


def load_role_schema() -> dict[str, dict[str, object]]:
    """Load role schema from the central orchestrator contract.

    Runtime validation follows exactly `.claude/orchestrator-contract.json ->
    trailer_schema.roles`. Missing schema is a configuration error, not an
    alternate runtime mode.
    """
    try:
        from common import project_root
        contract_path = project_root() / ".claude" / "orchestrator-contract.json"
        data = json.loads(contract_path.read_text(encoding="utf-8"))
        roles = ((data.get("trailer_schema") or {}).get("roles") or {})
        if isinstance(roles, dict) and roles:
            return {str(role): spec for role, spec in roles.items() if isinstance(spec, dict)}
    except Exception as exc:
        log_hook_error("hook_capture_subagent_stop.contract_schema", exc)
    return {}


def required_keys_for(agent_type: str | None) -> set[str]:
    if agent_type:
        role_schema = load_role_schema().get(agent_type)
        if role_schema:
            return {str(k).strip().lower() for k in role_schema.get("required_keys", []) if str(k).strip()}
    return set()


def trailer_missing_required(trailer: dict[str, str], agent_type: str | None) -> list[str]:
    """Return the list of REQUIRED keys missing for ``agent_type``.

    Empty list means the trailer is complete enough for the pipeline to
    move forward. Used by main() to decide whether to log to orchestrator-state/hook-errors.log.
    """
    required = required_keys_for(agent_type)
    if not required:
        return []
    return sorted(required - {k for k, v in trailer.items() if v})


def trailer_value_errors(trailer: dict[str, str], agent_type: str | None) -> list[str]:
    if not agent_type:
        return []
    errors: list[str] = []
    roles = load_role_schema()
    if not roles:
        return ["trailer_schema.roles unavailable; refusing schema-free lifecycle mutation"]
    if agent_type not in roles:
        return [f"agent_type={agent_type!r} missing from trailer_schema.roles"]
    allowed_outcomes, allowed_statuses = load_enum_contracts()
    outcome = str(trailer.get("outcome", "")).strip().lower()
    if outcome and outcome not in allowed_outcomes.get(agent_type, set()):
        errors.append(f"OUTCOME={outcome!r} not allowed for {agent_type}; allowed={sorted(allowed_outcomes.get(agent_type, set()))}")
    next_status = str(trailer.get("next_status", "")).strip().lower()
    if next_status and next_status not in allowed_statuses.get(agent_type, set()):
        errors.append(f"NEXT_STATUS={next_status!r} not allowed for {agent_type}; allowed={sorted(allowed_statuses.get(agent_type, set()))}")
    return errors


# Sentinel values agents emit for "no journey applies" — must NEVER be
# treated as a real Journey ID. Real JIDs look like J101, J203, J104A, etc.
# Without this filter, a closer emitting `JOURNEY_PENDING_VERIFY: none`
# would add the literal string to runtime-state.pending_journey_verifications,
# blocking /next-wave on a non-existent journey.
_INVALID_JID_VALUES = {
    "", "none", "null", "n/a", "na", "-", "—", "(none)",
    "<jid>", "<jid or none>", "tbd", "todo",
}

# Journey-related trailer patterns.
# JOURNEY_PENDING_VERIFY can appear MULTIPLE times in the same trailer if a
# single slice closes more than one journey (rare but legal). The other keys
# appear at most once per trailer.
JOURNEY_PENDING_RE        = re.compile(r"^JOURNEY_PENDING_VERIFY:\s*(\S+)\s*$", re.MULTILINE)
JOURNEY_INLINE_RE         = re.compile(r"^JOURNEY_VERIFIED_INLINE:\s*(\S+)\s*$", re.MULTILINE)
JOURNEY_REVERIFY_RE       = re.compile(r"^JOURNEY_REVERIFY_RECOMMENDED:\s*(\S+)\s*$", re.MULTILINE)
JOURNEY_ID_RE             = re.compile(r"^JOURNEY_ID:\s*(\S+)\s*$", re.MULTILINE)
JOURNEY_VERIFY_OUTCOME_RE = re.compile(r"^JOURNEY_VERIFY_OUTCOME:\s*(\S+)\s*$", re.MULTILINE)
JOURNEY_VERIFY_WAIVED_RE  = re.compile(r"^JOURNEY_VERIFY_WAIVED:\s*(.+?)\s*$", re.MULTILINE)


def parse_trailer(text: str) -> dict[str, str]:
    """Parse the plain-line trailer from the end of the agent response.

    Older versions scanned the full message and kept the first ``OUTCOME:``
    style line. That was fragile if an agent pasted a log or example containing
    the same words. Keep backwards compatibility with line trailers, but scope
    the scan to the explicit ``CLAUDE_TRAILER:`` section when present, otherwise
    only the final tail of the response. If duplicate keys appear, the last one
    wins because the final trailer should be authoritative.
    """
    text = text or ""
    marker = "CLAUDE_TRAILER:"
    if marker in text:
        text = text.rsplit(marker, 1)[-1]
    else:
        text = "\n".join(text.splitlines()[-80:])
    result: dict[str, str] = {}
    for match in TRAILER_LINE_RE.finditer(text):
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        if key:
            # Last occurrence wins: the final trailer block is authoritative
            # when an agent includes examples above the real result.
            result[key] = value
    return result


# Optional AGENT: line inside a handoff CLAUDE_TRAILER block. Agents that
# write a defensive recovery trailer to disk should include this marker so the
# fallback can verify that the recovered trailer belongs to the current
# subagent and not to an older one further up in the cumulative handoff.
_HANDOFF_AGENT_RE = re.compile(r"^AGENT:\s*(.+?)\s*$", re.MULTILINE)


def recover_trailer_from_handoff(
    task_id: str | None,
    agent_type: str | None,
) -> dict[str, str]:
    """Best-effort recovery: parse a ``CLAUDE_TRAILER`` block from the handoff
    file when the stdin trailer is empty or unusable.

    Rationale: the agent's chat message can be truncated (token cap, network
    drop, model stop) AFTER it has already written the handoff file to disk.
    "Disk > context" applies to the trailer itself — the handoff is the
    canonical record and a recovery source.

    Safeguards against picking up a stale trailer from the cumulative handoff:
      - Optional ``AGENT:`` line inside the last ``CLAUDE_TRAILER`` block must
        match ``agent_type`` when both are present.
      - ``TASK_ID`` inside the recovered trailer must match the requested
        ``task_id`` when both are present.

    Returns ``{}`` on any failure — never raises.
    """
    if not task_id:
        return {}
    try:
        # FW-024: per-slice files use workspace_root() via handoff_path().
        # In pr-flow this resolves to the worktree (where the agent's relative
        # Write actually landed). In push-to-main it's identical to canonical.
        from common import handoff_path as _handoff_path
        handoff_path = _handoff_path(task_id)
        if not handoff_path.exists():
            return {}
        text = handoff_path.read_text(encoding="utf-8", errors="replace")
        if "CLAUDE_TRAILER:" not in text:
            return {}

        trailer = parse_trailer(text)
        if not trailer:
            trailer = parse_json_trailer(text)
        if not trailer:
            return {}

        # Freshness guard: optional AGENT marker on the LAST trailer block
        # must agree with the agent that just stopped. The handoff is
        # cumulative — without this guard, a missing-message validator could
        # incorrectly pick up developer's earlier trailer.
        marker = "CLAUDE_TRAILER:"
        last_block = text.rsplit(marker, 1)[-1] if marker in text else text
        agent_match = _HANDOFF_AGENT_RE.search(last_block)
        agent_in_handoff = agent_match.group(1).strip() if agent_match else None
        if agent_in_handoff and agent_type and agent_in_handoff.lower() != agent_type.lower():
            log_hook_error(
                "hook_capture_subagent_stop.handoff_recovery_mismatch",
                RuntimeError(
                    f"handoff trailer reports AGENT={agent_in_handoff!r} but current "
                    f"agent={agent_type!r}; refusing recovery for task={task_id}"
                ),
            )
            return {}

        recovered_tid = trailer.get("task_id")
        if recovered_tid and recovered_tid != task_id:
            log_hook_error(
                "hook_capture_subagent_stop.handoff_recovery_mismatch",
                RuntimeError(
                    f"handoff trailer task_id={recovered_tid!r} != expected {task_id!r}"
                ),
            )
            return {}

        return trailer
    except Exception as exc:
        try:
            log_hook_error("hook_capture_subagent_stop.handoff_recovery", exc)
        except Exception:
            pass
        return {}


def parse_journey_trailer(text: str) -> dict[str, object]:
    """Parse journey-related trailer lines.

    Returns dict with:
      - pending: list[str]      — JOURNEY_IDs to add to pending_journey_verifications
      - verify_journey_id: str|None
      - verify_outcome: str|None — verified | issues_found
      - waiver_reason: str|None  — present iff JOURNEY_VERIFY_WAIVED was found
    """
    text = text or ""
    def _dedup_matches(regex: re.Pattern[str]) -> list[str]:
        values = [m.group(1).strip() for m in regex.finditer(text)]
        # Filter out sentinel "no journey" markers (none, null, "", -, etc.).
        # Real Journey IDs use the JNNN pattern; literals like "none" are
        # closer mistakes and pollute runtime-state if accepted.
        values = [v for v in values if v and v.lower() not in _INVALID_JID_VALUES]
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                out.append(value)
        return out

    pending_unique = _dedup_matches(JOURNEY_PENDING_RE)
    inline_unique = _dedup_matches(JOURNEY_INLINE_RE)
    reverify_unique = _dedup_matches(JOURNEY_REVERIFY_RE)

    jid_match = JOURNEY_ID_RE.search(text)
    out_match = JOURNEY_VERIFY_OUTCOME_RE.search(text)
    waiver_match = JOURNEY_VERIFY_WAIVED_RE.search(text)

    return {
        "pending": pending_unique,
        "verified_inline": inline_unique,
        "reverify_recommended": reverify_unique,
        "verify_journey_id": jid_match.group(1).strip() if jid_match else None,
        "verify_outcome": out_match.group(1).strip() if out_match else None,
        "waiver_reason": waiver_match.group(1).strip() if waiver_match else None,
    }


def apply_journey_mutations(journey_data: dict[str, object]) -> dict[str, object]:
    """Mutate runtime-state + registry based on the parsed journey trailer.

    Returns a summary dict for the ledger entry. Never raises — best-effort.
    """
    summary = {"pending_added": [], "verified": None, "verified_inline": [], "waived": None, "issues_found": None}
    try:
        # /verify-slice inline journey verification, reported by closer, is real
        # state now. Older instructions treated JOURNEY_VERIFIED_INLINE as
        # informational, which made phase-gate block despite human verification.
        inline_verified = {str(jid) for jid in (journey_data.get("verified_inline") or [])}
        for jid in inline_verified:
            try:
                remove_pending_journey_verification(str(jid), mark_verified=True)
                summary["verified_inline"].append(jid)
            except Exception:
                pass

        # Closer announced one or more journey closures that still need the
        # separate /verify-journey gate. Never add a journey to pending if the
        # same closer trailer already verified it inline.
        for jid in (journey_data.get("pending") or []):
            if str(jid) in inline_verified:
                continue
            try:
                result = add_pending_journey_verification(str(jid))
                if isinstance(result, dict) and result.get("ok"):
                    summary["pending_added"].append(jid)
                else:
                    summary.setdefault("pending_rejected", []).append(result)
            except Exception:
                pass

        # /verify-journey reports outcome
        verify_jid = journey_data.get("verify_journey_id")
        verify_outcome = journey_data.get("verify_outcome")
        if verify_jid and verify_outcome:
            if verify_outcome == "verified":
                try:
                    remove_pending_journey_verification(str(verify_jid), mark_verified=True)
                    summary["verified"] = verify_jid
                except Exception:
                    pass
            elif verify_outcome == "issues_found":
                # Don't mutate state — debugger needs to fix; pending stays.
                summary["issues_found"] = verify_jid

        # Waiver (explicit human-signed exception)
        waiver_reason = journey_data.get("waiver_reason")
        if verify_jid and waiver_reason:
            try:
                waive_journey_verification(str(verify_jid), str(waiver_reason))
                summary["waived"] = {"journey_id": verify_jid, "reason": waiver_reason}
            except Exception:
                pass
    except Exception:
        # Total best-effort — never re-raise from inside hook logic.
        pass
    return summary



def configured_git_workflow() -> str:
    """Return the normalized git workflow for close-time safety checks."""
    try:
        from common import project_root
        from stack_profile import load_stack_profile
        raw = str(load_stack_profile(project_root()).get("git_workflow") or "push-to-main")
    except Exception:
        raw = "push-to-main"
    workflow = "".join(ch for ch in raw if ch.isalnum() or ch in "_-")
    if workflow in {"direct-main", "direct-main-push", "push-main"}:
        return "push-to-main"
    if workflow == "gitflow":
        return "git-flow"
    return workflow or "push-to-main"


def enforce_closer_done_guardrail(trailer: dict[str, str], agent_type: str | None) -> dict[str, str]:
    """Never let a closer mark a task done without verify, commit/push/cleanup proof.

    Proposed follow-ups may travel in the PR, but close-time mechanics must be
    true on disk: report, baseline sync, Git workflow, worktree cleanup and a
    verified handoff section (or explicit human waiver). For pr-flow, a pushed
    PR is not enough: the PR must be MERGED and the canonical main checkout must
    be fast-forwarded before the DAG node can become done.
    """
    if agent_type != "closer":
        return trailer
    if str(trailer.get("next_status", "")).strip().lower() != "done":
        return trailer
    required_yes = ["report_ready", "baseline_sync_ready", "git_ready", "push_ready", "worktrees_cleaned"]
    if configured_git_workflow() == "pr-flow":
        required_yes.extend(["git_workflow_ready", "pr_ready", "merged", "canonical_main_synced"])
    bad = [k for k in required_yes if str(trailer.get(k, "")).strip().lower() != "yes"]
    if str(trailer.get("outcome", "")).strip().lower() != "committed":
        bad.append("outcome")
    if bad:
        log_hook_error(
            "hook_capture_subagent_stop.closer_guardrail",
            RuntimeError(
                "closer attempted NEXT_STATUS=done without closure proof: "
                + ", ".join(bad)
            ),
        )
        trailer = dict(trailer)
        trailer["next_status"] = "blocked"
        trailer["outcome"] = "blocked"
        trailer["closer_guardrail"] = "blocked_false_done"
        return trailer

    task_id = str(trailer.get("task_id", "")).strip()
    if task_id:
        try:
            from check_handoff_contract import validate as validate_handoff

            ok, errors, _details = validate_handoff(
                task_id,
                require_ready_for_close=True,
                require_verify_slice=True,
            )
            if not ok:
                waiver_ok = False
                try:
                    hp = handoff_path(task_id)
                    if hp.exists():
                        waiver_ok = bool(re.search(
                            r"(?im)^\s*-?\s*VERIFY_WAIVED\s*:\s*\S+",
                            hp.read_text(encoding="utf-8", errors="replace"),
                        ))
                except Exception:
                    waiver_ok = False
                if not waiver_ok:
                    log_hook_error(
                        "hook_capture_subagent_stop.closer_guardrail",
                        RuntimeError(
                            "closer attempted NEXT_STATUS=done without valid verify-slice handoff: "
                            + "; ".join(errors)
                        ),
                    )
                    trailer = dict(trailer)
                    trailer["next_status"] = "blocked"
                    trailer["outcome"] = "blocked"
                    trailer["blocker_reason"] = "closer_handoff_contract_failed"
                    trailer["closer_guardrail"] = "blocked_missing_verify_slice"
        except Exception as exc:
            log_hook_error("hook_capture_subagent_stop.closer_handoff_check", exc)
            trailer = dict(trailer)
            trailer["next_status"] = "blocked"
            trailer["outcome"] = "blocked"
            trailer["blocker_reason"] = "closer_handoff_check_error"
            trailer["closer_guardrail"] = "blocked_handoff_check_error"
    return trailer



def enforce_slice_verifier_guardrail(trailer: dict[str, str], agent_type: str | None) -> dict[str, str]:
    """Keep the verify-slice gate deterministic and mechanically safe."""
    if agent_type != "slice-verifier":
        return trailer

    outcome = str(trailer.get("outcome", "")).strip().lower()
    expected = {
        "verified": "verified_pending_close",
        "issues_found": "needs_debug",
        "blocked": "blocked",
    }
    if outcome in expected:
        wanted = expected[outcome]
        current = str(trailer.get("next_status", "")).strip().lower()
        if current != wanted:
            log_hook_error(
                "hook_capture_subagent_stop.slice_verifier_guardrail",
                RuntimeError(
                    f"slice-verifier OUTCOME={outcome!r} requires NEXT_STATUS={wanted!r}; "
                    f"got {current!r}. Rewriting to contract state."
                ),
            )
            trailer = dict(trailer)
            trailer["next_status"] = wanted
            trailer["slice_verifier_guardrail"] = "rewrote_status"

    if outcome == "verified":
        task_id = str(trailer.get("task_id", "")).strip()
        if task_id:
            try:
                from check_handoff_contract import validate as validate_handoff

                ok, errors, _details = validate_handoff(
                    task_id,
                    require_ready_for_close=True,
                    require_verify_slice=True,
                )
                if not ok:
                    log_hook_error(
                        "hook_capture_subagent_stop.slice_verifier_guardrail",
                        RuntimeError(
                            "slice-verifier attempted verified without valid handoff contract: "
                            + "; ".join(errors)
                        ),
                    )
                    trailer = dict(trailer)
                    trailer["outcome"] = "blocked"
                    trailer["next_status"] = "blocked"
                    trailer["blocker_reason"] = "slice_verifier_handoff_contract_failed"
                    trailer["slice_verifier_guardrail"] = "blocked_invalid_handoff"
            except Exception as exc:
                log_hook_error("hook_capture_subagent_stop.slice_verifier_handoff_check", exc)
                trailer = dict(trailer)
                trailer["outcome"] = "blocked"
                trailer["next_status"] = "blocked"
                trailer["blocker_reason"] = "slice_verifier_handoff_check_error"
                trailer["slice_verifier_guardrail"] = "blocked_handoff_check_error"
    return trailer


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        data = json.loads(raw)
        agent_type = data.get("agent_type")
        last_message = data.get("last_assistant_message", "") or ""
        trailer = parse_trailer(last_message)
        # If the line-prefixed parse came up empty (or partial), try the
        # fenced-JSON fallback. Merge: regex wins per-key when both define it,
        # because indented lines were intentional design.
        if not trailer or len(trailer) < 2:
            json_fallback = parse_json_trailer(last_message)
            if json_fallback:
                merged = dict(json_fallback)
                merged.update(trailer)
                trailer = merged
        # Third fallback: handoff recovery. If both stdin parses still came up
        # essentially empty, the agent's chat message was likely truncated
        # AFTER it wrote the handoff file. Read the trailer from disk. This
        # is "disco > contexto" applied at the mutation point: the message is
        # ephemeral, the handoff is canonical.
        if not trailer or len(trailer) < 2:
            recovery_tid = dag_worker_task_id() or trailer.get("task_id")
            handoff_recovered = recover_trailer_from_handoff(recovery_tid, agent_type)
            if handoff_recovered:
                log_hook_error(
                    "hook_capture_subagent_stop.recovered_from_handoff",
                    RuntimeError(
                        f"trailer recovered from handoff for task={recovery_tid} "
                        f"agent={agent_type} keys={sorted(handoff_recovered.keys())}; "
                        f"stdin trailer was empty (message likely truncated)"
                    ),
                )
                # Merge order: anything stdin DID emit takes precedence over
                # the disk copy. The recovery only fills in the gaps so a
                # partial-but-valid stdin trailer is never overruled.
                merged = dict(handoff_recovered)
                merged.update(trailer)
                trailer = merged
        # Normalize placeholders agents may emit during bootstrap or docs checks.
        if str(trailer.get("task_id", "")).strip().lower() in {"none", "null", "n/a", "-", "<task_id or none>"}:
            trailer.pop("task_id", None)

        journey_data = parse_journey_trailer(last_message)
        override_task_id = dag_worker_task_id()
        effective_task_id = override_task_id or trailer.get("task_id")
        allow_registry_mutation = True
        reported_task_id = trailer.get("task_id")
        if override_task_id:
            # In parallel DAG workers the terminal scope is authoritative.
            # A mismatched trailer must never update another node's lifecycle.
            if reported_task_id and reported_task_id != override_task_id:
                log_hook_error(
                    "hook_capture_subagent_stop.task_scope",
                    RuntimeError(
                        f"TASK_ID mismatch under CLAUDE_ACTIVE_TASK_ID: "
                        f"reported={reported_task_id} effective={override_task_id} "
                        f"agent={agent_type}"
                    ),
                )
                trailer["reported_task_id"] = reported_task_id
                trailer["task_id_mismatch"] = "true"
                allow_registry_mutation = False
            trailer["task_id"] = override_task_id

        trailer = enforce_closer_done_guardrail(trailer, agent_type)
        trailer = enforce_slice_verifier_guardrail(trailer, agent_type)

        # Noisy trailer check: if a lifecycle/reporting agent forgot required
        # keys, surface it via orchestrator-state/hook-errors.log so SessionStart shows the
        # issue. The hook itself does not block — silence here was the bug.
        try:
            missing = trailer_missing_required(trailer, agent_type)
            if missing:
                log_hook_error(
                    "hook_capture_subagent_stop.trailer",
                    RuntimeError(
                        f"trailer incomplete for agent={agent_type}: "
                        f"missing={missing} got={sorted(trailer.keys())}"
                    ),
                )
        except Exception as _trailer_check_exc:
            log_hook_error("hook_capture_subagent_stop.trailer_check",
                           _trailer_check_exc)

        enum_errors = trailer_value_errors(trailer, agent_type)
        if enum_errors:
            log_hook_error("hook_capture_subagent_stop.trailer_schema", RuntimeError("; ".join(enum_errors)))
            trailer["trailer_schema_error"] = "; ".join(enum_errors)
            if role_can_write_registry_metadata(agent_type):
                allow_registry_mutation = False

        append_jsonl(ledger_path(), {
            "ts": now_iso(),
            "event": "subagent_stop",
            "agent_type": agent_type,
            "task_id": effective_task_id,
            "trailer": trailer,
            "journey_trailer": {
                k: v for k, v in journey_data.items() if v
            },
        })

        # Spawn-budget bookkeeping (Fix #4). Increment BEFORE the registry
        # critical section so the count is visible even if the registry
        # branch returns early (e.g. trailer missing NEXT_STATUS). Best-effort.
        spawn_count = 0
        spawn_budget = 20
        try:
            tid = trailer.get("task_id") or effective_task_id
            spawn_count = bump_spawn_count(tid, agent_type)
            spawn_budget = get_spawn_budget()
            if spawn_count > spawn_budget:
                # Surface visibly via orchestrator-state/hook-errors.log so SessionStart shows it.
                log_hook_error(
                    "hook_capture_subagent_stop",
                    RuntimeError(
                        f"spawn budget exceeded: task={tid} count={spawn_count} "
                        f"budget={spawn_budget} agent={agent_type}"
                    ),
                )
        except Exception as exc:
            log_hook_error("hook_capture_subagent_stop.bump_spawn_count", exc)

        # Single ordered critical section.
        #
        # Lock order convention (project-wide): registry FIRST, runtime-state
        # SECOND. Holding both for the full duration of the hook guarantees:
        #   (a) no parallel hook (validator + tester finishing simultaneously)
        #       can observe half-updated state — they queue on the outer locks;
        #   (b) the registry advance and the runtime-state "last event" land
        #       together, so the SessionStart context never shows a registry
        #       that has moved past a runtime-state still pointing at the
        #       previous worker;
        #   (c) inner helpers (sync_runtime_state_from_registry,
        #       apply_journey_mutations) keep their own file_lock(...) calls
        #       — those become reentrant under file_lock's depth counter and
        #       cost nothing extra.
        with file_lock(registry_path()):
            can_apply_trailer = bool(
                trailer.get("task_id")
                and (trailer.get("next_status") or (role_is_info_only(agent_type) and trailer.get("outcome")))
            )
            if allow_registry_mutation and role_can_write_registry_metadata(agent_type) and can_apply_trailer:
                registry = load_registry()
                task = find_task(registry, trailer["task_id"])
                if task:
                    if role_is_info_only(agent_type):
                        # Informational write — capture as metadata, do NOT
                        # mutate the lifecycle status. This guarantees that
                        # when validator and tester race on the same task,
                        # the tester's pass/fail decides task.status.
                        task[f"{agent_type}_outcome"] = trailer.get("outcome")
                        if trailer.get("next_status"):
                            task[f"{agent_type}_next_status"] = trailer.get("next_status")
                        task["last_updated_by"] = agent_type
                        task["last_stop_at"] = now_iso()
                    else:
                        task["status"] = trailer["next_status"]
                        task["last_outcome"] = trailer.get("outcome")
                        task["last_updated_by"] = agent_type
                        task["last_stop_at"] = now_iso()
                        # FW-018: debugger cycle counter on the registry. Debugger
                        # reads this (not handoff prose) to honor max-3-cycles.
                        if agent_type == "debugger":
                            task["debug_cycles"] = int(task.get("debug_cycles") or 0) + 1
                        if trailer.get("next_status") == "blocked":
                            task["last_blocker"] = {
                                "reason": trailer.get("blocker_reason") or trailer.get("closer_guardrail") or trailer.get("outcome") or "blocked_by_agent",
                                "agent": agent_type,
                                "at": now_iso(),
                            }
                    if trailer.get("handoff"):
                        task["handoff_path"] = trailer["handoff"]
                    if trailer.get("evidence"):
                        task["evidence_dir"] = trailer["evidence"]
                    if trailer.get("report"):
                        task["report_path"] = trailer["report"]
                    save_registry(promote_ready_tasks(registry))
                    sync_runtime_state_from_registry(load_registry())

            # Journey mutations + final runtime-state update share the same
            # outer registry lock so the whole hook commits as one unit. In
            # parallel DAG mode, a TASK_ID mismatch means the trailer belongs
            # to a different node, so we skip journey side-effects too.
            if allow_registry_mutation and agent_type == "closer" and str(trailer.get("next_status", "")).strip().lower() == "done":
                # Mechanical safety net: if the closer forgot to classify a
                # journey, infer it after the task has been marked done. This is
                # status-based (all journey tasks done), not task_ids[-1]-based.
                try:
                    current_tid = str(trailer.get("task_id") or "")
                    inferred = journeys_closing_at_task(load_registry(), current_tid)
                    inline = set(str(x) for x in (journey_data.get("verified_inline") or []))
                    pending = list(journey_data.get("pending") or [])
                    for jid in inferred:
                        if jid in inline:
                            continue
                        if jid not in pending:
                            pending.append(jid)
                    journey_data["pending"] = pending
                    if inferred:
                        journey_data["inferred_closing"] = inferred
                except Exception as exc:
                    log_hook_error("hook_capture_subagent_stop.infer_journey_closure", exc)

            if allow_registry_mutation:
                journey_summary = apply_journey_mutations(journey_data)
            else:
                journey_summary = {
                    "pending_added": [],
                    "verified": None,
                    "waived": None,
                    "issues_found": None,
                    "skipped_due_task_scope": True,
                }

            # FW-003/004/006/007/017: reconcile drift continuously.
            try:
                reconcile_runtime_state(load_registry(), apply=True)
            except Exception as _rec_exc:
                log_hook_error("hook_capture_subagent_stop.reconcile", _rec_exc)

            with file_lock(runtime_state_path()):
                runtime = load_runtime_state()
                runtime["last_worker"] = agent_type
                # Don't clobber last_event if apply_journey_mutations set a
                # journey-specific one.
                if not (journey_summary.get("pending_added") or
                        journey_summary.get("verified") or
                        journey_summary.get("verified_inline") or
                        journey_summary.get("waived")):
                    runtime["last_event"] = "subagent_stop"
                runtime["last_trailer"] = trailer
                runtime["last_stop_at"] = now_iso()
                save_runtime_state(runtime)
    except Exception as exc:
        # Never block on hook failures — but don't disappear either.
        log_hook_error("hook_capture_subagent_stop", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
