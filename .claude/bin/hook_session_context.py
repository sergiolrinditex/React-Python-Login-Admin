#!/usr/bin/env python3
"""SessionStart hook — pure observability.

Injects lightweight context about project state at session start, so the first
turn already knows the pinned DAG worker task, whether the five-file source-of-truth contract
is healthy, and what was the last worker to finish. NEVER blocks. NEVER fails
the session — if anything goes wrong it emits an empty context.

Output format follows the official Claude Code hooks spec:

    {
      "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "<markdown>"
      }
    }

See: https://code.claude.com/docs/en/hooks

Journey extension (added by journey-verification feature):
- If runtime-state.pending_journey_verifications is non-empty, surfaces a
  WARNING block listing the pending journeys and instructing the user to run
  /verify-journey before /next-slice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from common import (
        claude_dir,
        dag_worker_task_id,
        hook_error_log_path,
        hook_info_log_path,
        handoff_path,
        task_pack_path,
        workspace_relpath,
        load_registry,
        load_runtime_state,
        log_hook_error,
        now_iso,
        project_root,
        has_resolved_doc_discrepancy_marker,
    )
except Exception:
    def _noop():  # type: ignore[no-redef]
        return {}
    load_registry = load_runtime_state = _noop  # type: ignore[assignment]
    dag_worker_task_id = lambda: None  # type: ignore[assignment]
    now_iso = lambda: ""  # type: ignore[assignment]
    project_root = lambda: Path(".")  # type: ignore[assignment]
    has_resolved_doc_discrepancy_marker = lambda text: __import__("re").search(r"(?im)^\s*(?:[-*+]\s+|#{1,6}\s+|>\s*)*RESOLVED(?:\s*:|\s+\d{4}-\d{2}-\d{2}\b|\s+[-–—])", text or "") is not None  # type: ignore[assignment]
    claude_dir = lambda: Path(".claude")  # type: ignore[assignment]
    hook_error_log_path = lambda: Path("orchestrator-state/hook-errors.log")  # type: ignore[assignment]
    hook_info_log_path = lambda: Path("orchestrator-state/hook-info.log")  # type: ignore[assignment]
    handoff_path = lambda task_id: Path(f"orchestrator-state/tasks/handoffs/{task_id}.md")  # type: ignore[assignment]
    task_pack_path = lambda task_id: Path(f"orchestrator-state/tasks/task-packs/{task_id}.md")  # type: ignore[assignment]
    workspace_relpath = lambda path: str(path)  # type: ignore[assignment]
    def log_hook_error(name, exc):  # type: ignore[no-redef]
        return None

MAX_CHARS = 9500  # leave headroom under the 10 000 char cap (official)
PROGRESS_HEAD_BUDGET = 3000  # chars reserved for the PROGRESS.md head block

# Pressure thresholds — only emit a 💡 suggestion when these are exceeded.
PROGRESS_BIG_BYTES = 8000          # PROGRESS.md > 8KB → suggest /slice-maintain compact
MEMORY_BIG_LINES = 250             # any agent-memory MEMORY.md > 250 lines → next-wave auto-compacts
LEDGER_BIG_BYTES = 200 * 1024      # ledger.jsonl > 200KB → suggest /slice-maintain clean


def _safe_read(path: Path, max_lines: int = 40) -> str:
    try:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = []
            for i, line in enumerate(fh):
                if i >= max_lines:
                    lines.append("... (truncated)\n")
                    break
                lines.append(line)
            return "".join(lines).rstrip()
    except Exception:
        return ""


def _progress_head_compact(path: Path, budget: int = PROGRESS_HEAD_BUDGET) -> str:
    """Return the most useful prefix of PROGRESS.md within `budget` chars.

    Strategy: always include the file header up to (and including) the
    `## Current State` section, then as many of the most recent slice
    entries as fit in the budget. If still too large, truncate by char
    count. Never returns more than `budget` chars.
    """
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) <= budget:
            return text.rstrip()

        # Try to keep header + Current State block intact, then as many
        # subsequent ## sections as fit (in original order — those are the
        # most recent if PROGRESS.md is maintained well; the developer always
        # appends to the top of the slice list, but we don't enforce that).
        lines = text.splitlines(keepends=True)
        header_end = 0
        for i, line in enumerate(lines):
            if line.startswith("## ") and "Current State" not in line:
                # The first ## that is NOT Current State marks the end of header.
                header_end = i
                break
        # Header includes everything up to (and inc.) the Current State section
        # if it exists, else the first ~30 lines.
        if header_end == 0:
            header_end = min(30, len(lines))
        head = "".join(lines[:header_end])
        if len(head) > budget:
            return head[:budget].rstrip() + "\n... (truncated to PROGRESS_HEAD_BUDGET)"

        # Add subsequent sections until budget runs out.
        remaining = budget - len(head)
        rest = "".join(lines[header_end:])
        if len(rest) <= remaining:
            return (head + rest).rstrip()
        return (head + rest[:remaining]).rstrip() + "\n... (truncated to PROGRESS_HEAD_BUDGET; full file at orchestrator-state/memory/PROGRESS.md)"
    except Exception:
        return ""


def _detect_pressure(root: Path) -> list[str]:
    """Return a list of 💡 suggestion lines when state on disk crosses
    pressure thresholds. Empty list when everything is fine.
    """
    suggestions: list[str] = []
    try:
        progress = Path(root) / "orchestrator-state/memory/PROGRESS.md"
        if progress.exists() and progress.stat().st_size > PROGRESS_BIG_BYTES:
            kb = progress.stat().st_size // 1024
            suggestions.append(
                f"💡 PROGRESS.md tiene {kb} KB (>{PROGRESS_BIG_BYTES // 1024} KB). "
                f"Considera `/slice-maintain compact` antes de la siguiente slice."
            )
    except Exception:
        pass

    try:
        memdir = Path(root) / "orchestrator-state/agent-memory"
        if memdir.is_dir():
            big = []
            for memfile in sorted(memdir.glob("*/MEMORY.md")):
                try:
                    n = sum(1 for _ in memfile.open("r", encoding="utf-8", errors="replace"))
                except Exception:
                    continue
                if n > MEMORY_BIG_LINES:
                    big.append(f"{memfile.parent.name} ({n} líneas)")
            if big:
                suggestions.append(
                    f"💡 Memoria de agentes >{MEMORY_BIG_LINES} líneas: "
                    f"{', '.join(big)}. Se compactará automáticamente al inicio de `./scripts/next-wave.sh`; usa `/slice-maintain compact-agent-memory` si quieres revisarlo manualmente."
                )
    except Exception:
        pass

    try:
        ledger = Path(root) / "orchestrator-state/tasks/ledger.jsonl"
        if ledger.exists() and ledger.stat().st_size > LEDGER_BIG_BYTES:
            kb = ledger.stat().st_size // 1024
            suggestions.append(
                f"💡 ledger.jsonl tiene {kb} KB (>{LEDGER_BIG_BYTES // 1024} KB). "
                f"`/slice-maintain clean --apply` lo rotará automáticamente."
            )
    except Exception:
        pass

    return suggestions


def build_context() -> str:
    # Best-effort post-reset repair: committed lifecycle-events are the durable
    # PR signal; replay them before SessionStart displays scheduler state.
    try:
        from sync_lifecycle_events import apply_events
        apply_events(dry_run=False)
    except Exception as exc:
        try:
            log_hook_error("hook_session_context.lifecycle_events", exc)
        except Exception:
            pass

    runtime = load_runtime_state() or {}
    registry = load_registry() or {}

    worker_override = dag_worker_task_id() if callable(dag_worker_task_id) else None
    worker_task = worker_override or "—"
    worker_phase = "—"
    active_status = "—"
    if worker_override and isinstance(registry.get("tasks"), list):
        for task in registry.get("tasks", []):
            if isinstance(task, dict) and task.get("id") == worker_override:
                worker_phase = task.get("phase_id") or "—"
                active_status = task.get("status") or "—"
                break
    next_ready_phase = runtime.get("next_ready_phase_id") or "—"
    next_ready_task = runtime.get("next_ready_task_id") or "—"
    if (next_ready_task == "—" or next_ready_phase == "—") and isinstance(registry.get("tasks"), list):
        for candidate in registry.get("tasks", []):
            if isinstance(candidate, dict) and candidate.get("status") == "ready":
                next_ready_task = next_ready_task if next_ready_task != "—" else (candidate.get("id") or "—")
                next_ready_phase = next_ready_phase if next_ready_phase != "—" else (candidate.get("phase_id") or "—")
                break
    last_worker = runtime.get("last_worker") or "—"
    last_event = runtime.get("last_event") or "—"
    last_journey_verified = runtime.get("last_journey_verified") or "—"

    # Spawn-budget bookkeeping (Fix #4). Read-only display so the user sees
    # how many spawns the current slice has consumed against the budget.
    spawn_budget = 20
    try:
        spawn_budget = int(runtime.get("spawn_budget", 20))
    except (TypeError, ValueError):
        spawn_budget = 20
    spawn_counts_raw = runtime.get("spawns_in_current_slice") or {}
    if not isinstance(spawn_counts_raw, dict):
        spawn_counts_raw = {}
    spawn_count_for_active = 0
    if worker_task and worker_task != "—":
        try:
            spawn_count_for_active = int(spawn_counts_raw.get(worker_task, 0))
        except (TypeError, ValueError):
            spawn_count_for_active = 0

    root = project_root() if callable(project_root) else Path(".")
    progress_path = Path(root) / "orchestrator-state/memory/PROGRESS.md"
    progress_head = _progress_head_compact(progress_path, budget=PROGRESS_HEAD_BUDGET)
    pressure_suggestions = _detect_pressure(Path(root))
    sot_dir = Path(root) / "docs/source-of-truth"
    sot_status = "ok" if sot_dir.is_dir() else "missing (bootstrap required)"

    handoff_note = ""
    if worker_task and worker_task != "—":
        try:
            handoff = handoff_path(worker_task)
            if handoff.exists():
                handoff_note = f"- Handoff activo: `{workspace_relpath(handoff)}`"
        except Exception:
            handoff = Path(root) / f"orchestrator-state/tasks/handoffs/{worker_task}.md"
            if handoff.exists():
                handoff_note = f"- Handoff activo: `orchestrator-state/tasks/handoffs/{worker_task}.md`"

    # Pending journey verifications — block /next-slice from planner until cleared.
    pending_journeys: list[str] = []
    try:
        raw_pending = runtime.get("pending_journey_verifications", []) or []
        if isinstance(raw_pending, list):
            pending_journeys = [str(j) for j in raw_pending if j]
    except Exception:
        pending_journeys = []

    # Surface any hook failures from previous runs so the user sees them
    # immediately instead of discovering corruption later.
    hook_errors = ""
    try:
        err_path = hook_error_log_path() if callable(hook_error_log_path) else Path(root) / "orchestrator-state/hook-errors.log"
        if err_path.exists() and err_path.stat().st_size > 0:
            tail = _safe_read(err_path, max_lines=20)
            hook_errors = tail

    except Exception:
        hook_errors = ""

    # Surface unresolved docs discrepancies — if any, developer must NOT run.
    doc_discrepancies: list[str] = []
    try:
        notes_dir = Path(root) / "orchestrator-state/memory/official-doc-notes"
        if notes_dir.is_dir():
            for note in sorted(notes_dir.glob("*.md")):
                try:
                    body = note.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if not has_resolved_doc_discrepancy_marker(body):
                    try:
                        rel = note.resolve().relative_to(Path(root).resolve()).as_posix()
                    except Exception:
                        rel = note.as_posix()
                    doc_discrepancies.append(rel)
    except Exception:
        doc_discrepancies = []

    spawn_marker = ""
    if spawn_count_for_active >= spawn_budget:
        spawn_marker = " ⚠️ over budget — planner must refuse CONTEXT_READY"
    elif spawn_count_for_active >= max(1, spawn_budget - 1):
        spawn_marker = " ⚠️ at budget"
    lines = [
        "## Project state (auto-injected at session start)",
        f"- Next ready hint: phase `{next_ready_phase}`, task `{next_ready_task}`",
        f"- DAG worker task: `{worker_task}` (phase: `{worker_phase}`, status: `{active_status}`)",
        f"- Spawns this slice: {spawn_count_for_active}/{spawn_budget}{spawn_marker}",
        f"- Last worker:  `{last_worker}` (event: `{last_event}`)",
        f"- Last journey verified: `{last_journey_verified}`",
        f"- Source-of-truth docs: {sot_status}",
        "- Mutable state root: `orchestrator-state/`",
        "- Write contract: `.claude/orchestrator-contract.json` (hooks enforce machine contract; markdown rules are agent instructions)",
    ]
    if worker_override:
        lines.append(f"- Worker task override: `{worker_override}` (DAG terminal scope)")
        try:
            pack = task_pack_path(worker_override)
            pack_display = workspace_relpath(pack)
        except Exception:
            pack = Path(root) / f"orchestrator-state/tasks/task-packs/{worker_override}.md"
            pack_display = f"orchestrator-state/tasks/task-packs/{worker_override}.md"
        pack_status = "exists" if pack.exists() else "missing — planner must create/enrich before developer"
        lines.append(f"- DAG task pack: `{pack_display}` ({pack_status})")
    else:
        lines.append("- DAG mode: no worker task pinned. Export `CLAUDE_ACTIVE_TASK_ID` + `CLAUDE_TASK_PACK` or run `claude --agent main-orchestrator --permission-mode bypassPermissions \"/next-slice <TASK_ID>\"` from a task terminal.")
    if handoff_note:
        lines.append(handoff_note)

    if pending_journeys:
        lines.append("")
        lines.append("### ⚠️ Pending journey verifications (BLOQUEAN /next-slice)")
        for jid in pending_journeys[:10]:
            lines.append(f"- `{jid}` — lanza `/verify-journey {jid}`")
        lines.append(
            "El `planner` devolverá `CONTEXT_READY: no` mientras haya journeys pendientes. "
            "Resuelve cada uno con `/verify-journey <JID>` (o waiver explícito "
            "`JOURNEY_VERIFY_WAIVED: <motivo>` en el journey-handoff) antes de continuar."
        )

    # Pressure suggestions — only when real thresholds are exceeded.
    if pressure_suggestions:
        lines.append("")
        lines.append("### 💡 Sugerencias de mantenimiento (umbrales reales superados)")
        for s in pressure_suggestions:
            lines.append(f"- {s}")

    if doc_discrepancies:
        lines.append("")
        lines.append("### ⚠️ Unresolved docs discrepancies (reconcile before implementing)")
        for path in doc_discrepancies[:10]:
            lines.append(f"- `{path}`")
        lines.append(
            "Recommend: reconcile the source-of-truth pack with the official "
            "docs, then add a `RESOLVED: <how>` line to each note (`RESOLVED 2026-...` date-prefixed notes are also accepted). The "
            "PreToolUse hook will keep warning (warn-only, never blocks) until "
            "every note is resolved."
        )

    if hook_errors:
        lines.append("")
        lines.append("### ⚠️ Recent hook errors (see `orchestrator-state/hook-errors.log`)")
        lines.append("")
        lines.append("```")
        lines.append(hook_errors)
        lines.append("```")

    lines.append("")
    lines.append("### PROGRESS.md (head)")
    lines.append("")
    lines.append("```md")
    lines.append(progress_head or "(PROGRESS.md not found or empty)")
    lines.append("```")
    lines.append("")
    lines.append(
        "Autonomous mode: run one controlled slice at a time. Use `/next-slice`, "
        "then optional `/clear`, then `/verify-slice`. After /clear, read "
        "PROGRESS.md FIRST. `planner` before developer. See CLAUDE.md."
    )
    out = "\n".join(lines)
    return out[:MAX_CHARS]


def main() -> int:
    try:
        _ = sys.stdin.read()
        context = build_context()
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        }
        print(json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        # Never fail the session — but leave a visible trail.
        try:
            log_hook_error("hook_session_context", exc)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
