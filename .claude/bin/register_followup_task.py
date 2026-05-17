#!/usr/bin/env python3
"""Register validator/tester findings as first-class DAG follow-up tasks.

A finding found during validation can be either:
  * in-scope for the current TASK_ID -> debugger fixes the same slice; or
  * real but out-of-scope / missing coverage -> it must become a formal
    follow-up, not a loose note in a handoff.

This script implements the second path under locks. Agents may create a
proposal during a task. The main-orchestrator promotes it only after explicit
human approval; promotion appends a canonical Coverage Registry amendment to
source-of-truth docs, updates registry.json, regenerates the DAG adjacency, and
writes work-items/<TASK_ID>.yaml.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

from bootstrap_source_of_truth import (
    build_task_dag,
    enrich_journey_completion_metadata,
    render_task_dag_markdown,
    write_phase_yaml,
    write_task_yaml,
)
from generate_api_contracts import generate_contracts
from common import (
    append_jsonl,
    canonical_source_docs_dir,
    discover_source_docs,
    file_lock,
    find_phase,
    find_task,
    ledger_path,
    load_registry,
    load_runtime_state,
    memory_dir,
    now_iso,
    promote_ready_tasks,
    active_conflict_blockers,
    registry_path,
    relpath,
    runtime_state_path,
    save_registry,
    save_runtime_state,
    sync_runtime_state_from_registry,
    task_conflict_groups,
    task_write_set,
    tasks_dir,
    write_json,
    write_text,
)

BLOCKING_SEVERITIES = {"blocker", "critical", "high"}
FOLLOWUP_SCOPE_CLASSIFICATIONS = {
    "out_of_scope",
    "missing_coverage",
    "missing_real_data",
    "external_dependency",
    "future_enhancement",
    "scope_expansion",
    "blocked_by_human_decision",
    "in_scope_defect",
    "unspecified",
}
DEFAULT_COLUMNS = [
    "Slice ID", "Tipo", "Target", "Step", "Product increment", "Build state",
    "Risk level", "Verify mode",
    "Depends on", "Conflict group", "Write set", "Journey refs", "Pantalla/Ruta", "Endpoint",
    "Tablas DB", "Origen-Instr", "Origen-TechGuide", "Acceptance mínimo", "Verify mínimo",
]


def followups_dir() -> Path:
    return tasks_dir() / "follow-ups"


def source_doc_patches_dir() -> Path:
    return tasks_dir() / "source-doc-patches"


def _identity() -> str:
    for key in ("USER", "LOGNAME", "USERNAME"):
        if os.environ.get(key):
            return str(os.environ[key])
    return "unknown"


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return value[:48] or "followup"


def _now_id(title: str) -> str:
    ts = re.sub(r"[^0-9]", "", now_iso())[:14]
    return f"FU-{ts}-{_slug(title)}"


def _as_list(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        for part in re.split(r"[,;\n]", str(raw)):
            item = part.strip().strip("`")
            if item and item not in {"—", "-", "none", "n/a"} and item not in out:
                out.append(item)
    return out


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    else:  # pragma: no cover
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    write_text(path, text)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
    else:  # pragma: no cover
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid follow-up YAML: {path}")
    return data


def _proposal_path(fid: str) -> Path:
    return followups_dir() / f"{fid}.yaml"



def _unique_followup_id(title: str) -> str:
    base = _now_id(title)
    fid = base
    counter = 2
    while _proposal_path(fid).exists():
        fid = f"{base}-{counter}"
        counter += 1
    return fid

def _normalise_severity(value: str | None) -> str:
    value = str(value or "medium").strip().lower()
    aliases = {"critico": "critical", "crítico": "critical", "alto": "high", "media": "medium", "bajo": "low"}
    return aliases.get(value, value)


def _normalise_scope_classification(value: str | None) -> str:
    value = str(value or "unspecified").strip().lower().replace("-", "_")
    aliases = {
        "outside_scope": "out_of_scope",
        "outofscope": "out_of_scope",
        "coverage_gap": "missing_coverage",
        "missing_data": "missing_real_data",
        "real_data_missing": "missing_real_data",
        "external": "external_dependency",
        "enhancement": "future_enhancement",
        "scope_change": "scope_expansion",
        "human_decision": "blocked_by_human_decision",
        "in_scope": "in_scope_defect",
        "slice_defect": "in_scope_defect",
        "debugger": "in_scope_defect",
    }
    value = aliases.get(value, value)
    if value not in FOLLOWUP_SCOPE_CLASSIFICATIONS:
        raise SystemExit(
            "invalid --scope-classification: "
            f"{value}. Use one of: {', '.join(sorted(FOLLOWUP_SCOPE_CLASSIFICATIONS - {'unspecified'}))}"
        )
    return value


def _validate_followup_triage(severity: str, classification: str, why_not_debugger: str | None) -> list[str]:
    """Return warnings; raise for proposals that should be handled in-slice.

    A follow-up is source-of-truth work, not a substitute for debugger/retest.
    Blocking follow-ups must explicitly explain why they cannot be repaired inside
    the active TASK_ID.
    """
    why = str(why_not_debugger or "").strip()
    if classification == "in_scope_defect":
        raise SystemExit(
            "Refusing follow-up proposal classified as in_scope_defect. "
            "Use validator/tester -> debugger -> retest inside the same TASK_ID instead. "
            "Only propose FU for work outside the current task pack/write_set or missing coverage/data."
        )
    warnings: list[str] = []
    if classification == "unspecified":
        msg = (
            "follow-up triage is unspecified; add --scope-classification and --why-not-debugger "
            "so this does not become FU spam"
        )
        if severity in BLOCKING_SEVERITIES:
            raise SystemExit(msg)
        warnings.append(msg)
    if severity in BLOCKING_SEVERITIES and not why:
        raise SystemExit(
            "blocking follow-up proposals require --why-not-debugger explaining why debugger/retest "
            "cannot resolve the finding inside the current slice"
        )
    if not why:
        warnings.append("missing --why-not-debugger; reviewers must confirm this is not an in-scope defect")
    return warnings


def _append_open_followup(runtime: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    runtime.setdefault("open_followups", [])
    entry = {
        "id": proposal["id"],
        "status": proposal.get("status", "proposed"),
        "severity": proposal.get("severity", "medium"),
        "origin_task_id": proposal.get("origin_task_id"),
        "title": proposal.get("title"),
        "path": proposal.get("proposal_path"),
        "created_at": proposal.get("created_at"),
        "scope_classification": (proposal.get("triage") or {}).get("scope_classification"),
        "why_not_debugger": (proposal.get("triage") or {}).get("why_not_debugger"),
    }
    runtime["open_followups"] = [x for x in runtime.get("open_followups", []) if x.get("id") != proposal["id"]]
    runtime["open_followups"].append(entry)
    runtime["last_followup_id"] = proposal["id"]
    runtime["last_event"] = "followup_proposed"
    runtime["generated_at"] = now_iso()
    return runtime


def _set_open_followup_status(runtime: dict[str, Any], fid: str, status: str, **extra: Any) -> dict[str, Any]:
    items = []
    found = False
    for item in runtime.get("open_followups", []) or []:
        if item.get("id") == fid:
            item = dict(item)
            item["status"] = status
            item.update({k: v for k, v in extra.items() if v is not None})
            found = True
        items.append(item)
    if not found:
        item = {"id": fid, "status": status}
        item.update({k: v for k, v in extra.items() if v is not None})
        items.append(item)
    runtime["open_followups"] = items
    runtime["last_followup_id"] = fid
    runtime["last_event"] = f"followup_{status}"
    runtime["generated_at"] = now_iso()
    return runtime


def blocking_open_followups(runtime: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    runtime = runtime or load_runtime_state()
    out: list[dict[str, Any]] = []
    for item in runtime.get("open_followups", []) or []:
        if str(item.get("status") or "proposed") == "proposed" and _normalise_severity(item.get("severity")) in BLOCKING_SEVERITIES:
            out.append(item)
    return out



def _norm_duplicate_key(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


def _followup_duplicate_key(data: dict[str, Any]) -> tuple[str, str, str, str]:
    triage = data.get("triage") or {}
    scope = data.get("scope_classification") or triage.get("scope_classification") or ""
    target = data.get("endpoint") or data.get("screen_route") or ",".join(str(t) for t in data.get("tables") or [])
    return (
        _norm_duplicate_key(data.get("kind") or "followup"),
        _norm_duplicate_key(data.get("title")),
        _norm_duplicate_key(scope),
        _norm_duplicate_key(target),
    )


def _possible_duplicate_followups(candidate: dict[str, Any], *, ignore_id: str | None = None) -> list[dict[str, Any]]:
    key = _followup_duplicate_key(candidate)
    if not key[1]:
        return []
    matches: list[dict[str, Any]] = []
    directory = followups_dir()
    if not directory.is_dir():
        return []
    for path in sorted(directory.glob("*.y*ml")):
        try:
            data = _read_yaml(path)
        except Exception:
            continue
        if ignore_id and data.get("id") == ignore_id:
            continue
        other_key = _followup_duplicate_key(data)
        exact_title = other_key[1] == key[1]
        same_target = bool(key[3]) and key[3] == other_key[3]
        same_scope_kind = key[0] == other_key[0] and key[2] == other_key[2]
        if exact_title or (same_target and same_scope_kind):
            matches.append({
                "id": data.get("id"),
                "status": data.get("status"),
                "origin_task_id": data.get("origin_task_id"),
                "promoted_task_id": data.get("promoted_task_id"),
                "title": data.get("title"),
                "proposal_path": relpath(path),
            })
    return matches


def _task_status(registry: dict[str, Any], task_id: str | None) -> str:
    if not task_id:
        return ""
    task = find_task(registry, task_id)
    return str((task or {}).get("status") or "")

def propose(args: argparse.Namespace) -> dict[str, Any]:
    registry = load_registry()
    origin_task = find_task(registry, args.origin_task) if args.origin_task else None
    if args.origin_task and not origin_task:
        raise SystemExit(f"origin TASK_ID not found: {args.origin_task}")
    severity = _normalise_severity(args.severity)
    scope_classification = _normalise_scope_classification(getattr(args, "scope_classification", None))
    why_not_debugger = getattr(args, "why_not_debugger", None)
    triage_warnings = _validate_followup_triage(severity, scope_classification, why_not_debugger)
    fid = args.id or _unique_followup_id(args.title)
    proposal = {
        "id": fid,
        "schema_version": 1,
        "status": "proposed",
        "created_at": now_iso(),
        "created_by": _identity(),
        "origin_task_id": args.origin_task,
        "origin_phase_id": args.phase or (origin_task or {}).get("phase_id"),
        "origin_step_id": args.step or (origin_task or {}).get("step_id"),
        "kind": args.kind,
        "product_increment": getattr(args, "product_increment", None) or os.environ.get("PRODUCT_INCREMENT") or "current",
        "build_state": getattr(args, "build_state", None) or "planned",
        "severity": severity,
        "title": args.title,
        "description": args.description or "",
        "journey_refs": _as_list(args.journey_ref),
        "screen_route": args.screen_route or "—",
        "endpoint": args.endpoint or "—",
        "tables": _as_list(args.table),
        "depends_on": _as_list(args.depends_on) or ([args.origin_task] if args.origin_task else []),
        "conflict_groups": _as_list(args.conflict_group) or (task_conflict_groups(origin_task) if origin_task else []),
        "write_set": _as_list(args.write_set) or (task_write_set(origin_task) if origin_task else []),
        "acceptance": _as_list(args.acceptance) or [args.title],
        "verify": _as_list(args.verify) or ["Reproducir con datos reales/proporcionados según Verification Data Contract"],
        "notes": _as_list(args.note),
        "triage": {
            "scope_classification": scope_classification,
            "why_not_debugger": str(why_not_debugger or "").strip(),
            "decision": "followup_only_when_outside_current_slice",
            "debugger_path": "in_scope_defects_use_validator_tester_debugger_retest",
            "warnings": triage_warnings,
        },
    }
    duplicates = _possible_duplicate_followups(proposal, ignore_id=fid)
    proposal["possible_duplicates"] = duplicates
    path = _proposal_path(fid)
    proposal["proposal_path"] = relpath(path)
    _write_yaml(path, proposal)
    with file_lock(runtime_state_path()):
        runtime = _append_open_followup(load_runtime_state(), proposal)
        save_runtime_state(runtime)
    append_jsonl(ledger_path(), {"ts": now_iso(), "event": "followup_proposed", "followup_id": fid, "origin_task_id": args.origin_task, "severity": severity, "scope_classification": scope_classification, "path": relpath(path)})
    return {"ok": True, "followup_id": fid, "proposal_path": relpath(path), "blocking": severity in BLOCKING_SEVERITIES, "scope_classification": scope_classification, "triage_warnings": triage_warnings, "possible_duplicates": duplicates}


def _normalise_step_id(phase_id: str, step_id: str | None) -> str:
    raw = str(step_id or "").strip()
    if re.match(r"^P\d{2}-S\d{2}$", raw):
        return raw
    if re.match(r"^S\d{2}$", raw):
        return f"{phase_id}-{raw}"
    return f"{phase_id}-S99"


def _next_task_id(registry: dict[str, Any], phase_id: str, step_id: str) -> str:
    prefix = _normalise_step_id(phase_id, step_id)
    max_n = 0
    for task in registry.get("tasks", []) or []:
        tid = str(task.get("id") or "")
        m = re.match(re.escape(prefix) + r"-T(\d+)$", tid)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{prefix}-T{max_n + 1:03d}"


def _clean_optional(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in {"", "—", "-", "none", "n/a"} else text


def _risk_level_for_severity(value: Any) -> str:
    severity = _normalise_severity(str(value or "medium"))
    if severity in {"critical", "blocker"}:
        return "critical"
    if severity == "high":
        return "high"
    if severity == "low":
        return "low"
    return "medium"


def _verify_mode_for_followup(proposal: dict[str, Any], risk_level: str) -> str:
    if risk_level in {"medium", "high", "critical"}:
        return "human"
    if _clean_optional(proposal.get("screen_route")) or proposal.get("journey_refs"):
        return "human"
    return "auto"


def _validate_followup_references(registry: dict[str, Any], proposal: dict[str, Any], deps: list[str]) -> None:
    task_ids = {str(t.get("id")) for t in registry.get("tasks", []) or [] if t.get("id")}
    missing_deps = [dep for dep in deps if dep not in task_ids]
    if missing_deps:
        raise SystemExit(
            "cannot promote follow-up with unknown dependencies: "
            + ", ".join(missing_deps)
        )

    known_journeys = {str(j.get("id")) for j in registry.get("journeys", []) or [] if j.get("id")}
    journey_refs = [str(j) for j in proposal.get("journey_refs") or [] if str(j).strip()]
    missing_journeys = [jid for jid in journey_refs if jid not in known_journeys]
    if missing_journeys:
        raise SystemExit(
            "cannot promote follow-up with unknown journey_refs: "
            + ", ".join(missing_journeys)
            + ". Add/update UX_CONTRACT.md and bootstrap first, or omit --journey-ref for a source-of-truth follow-up that defines the new journey."
        )


def _write_phase_yamls(registry: dict[str, Any]) -> None:
    phases_root = tasks_dir() / "phases"
    phases_root.mkdir(parents=True, exist_ok=True)
    for phase in registry.get("phases", []) or []:
        if phase.get("id"):
            phase.setdefault("title", f"Runtime follow-ups {phase['id']}")
            phase.setdefault("status", "blocked")
            phase.setdefault("depends_on", [])
            phase.setdefault("source_ref", "runtime-followup")
            write_phase_yaml(phases_root / f"{phase['id']}.yaml", phase)


def _md_cell(value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(str(x) for x in value if str(x).strip())
    text = str(value if value is not None else "—").strip() or "—"
    text = text.replace("\n", " ").replace("|", "\\|")
    return text


def _row_for_task(task: dict[str, Any], proposal: dict[str, Any]) -> str:
    severity = str(proposal.get("severity") or "medium").lower()
    risk_level = "critical" if severity in {"critical", "blocker", "critico", "crítico"} else ("high" if severity in {"high", "alto"} else ("low" if severity in {"low", "bajo"} else "medium"))
    verify_mode = "human" if risk_level in {"medium", "high", "critical"} or proposal.get("screen_route") or proposal.get("journey_refs") else "auto"
    values = [
        task["id"],
        proposal.get("kind") or "followup",
        task.get("title") or proposal.get("title"),
        proposal.get("step_label") or f"Runtime follow-up {proposal.get('origin_task_id') or ''}".strip(),
        task.get("product_increment") or proposal.get("product_increment") or "current",
        task.get("build_state") or proposal.get("build_state") or "planned",
        risk_level,
        verify_mode,
        task.get("depends_on") or [],
        task.get("conflict_groups") or [],
        task.get("write_set") or [],
        proposal.get("journey_refs") or [],
        proposal.get("screen_route") or "—",
        proposal.get("endpoint") or "—",
        proposal.get("tables") or [],
        f"runtime-followup#{proposal.get('id')}",
        f"runtime-followup#{proposal.get('id')}",
        task.get("acceptance") or [],
        task.get("verification_commands") or [],
    ]
    return "| " + " | ".join(_md_cell(v) for v in values) + " |"


def _append_source_registry_row(task: dict[str, Any], proposal: dict[str, Any]) -> str | None:
    docs = discover_source_docs()
    checklist_candidates = docs.get("checklist") or []
    if not checklist_candidates:
        return None
    checklist = checklist_candidates[0]
    row = _row_for_task(task, proposal)
    heading = "## Runtime Follow-up Coverage Registry"
    heading_re = re.compile(r"^#{2,4}\s+Runtime Follow-up Coverage Registry\s*$")
    header = "| " + " | ".join(DEFAULT_COLUMNS) + " |"
    sep = "|" + "|".join("---" for _ in DEFAULT_COLUMNS) + "|"
    with file_lock(checklist):
        text = checklist.read_text(encoding="utf-8") if checklist.exists() else ""
        if not any(heading_re.match(line.strip()) for line in text.splitlines()):
            block = [
                "",
                heading,
                "",
                "> Auto-appended by `.claude/bin/register_followup_task.py` after human approval.",
                "> These rows are source-of-truth amendments. Keep them; future bootstrap runs parse them like any other Coverage Registry row.",
                "",
                header,
                sep,
                row,
                "",
            ]
            text = text.rstrip() + "\n" + "\n".join(block)
        else:
            lines = text.splitlines()
            hidx = next(i for i, line in enumerate(lines) if heading_re.match(line.strip()))
            next_heading = len(lines)
            for i in range(hidx + 1, len(lines)):
                if lines[i].startswith("## "):
                    next_heading = i
                    break
            section = lines[hidx:next_heading]
            header_idx = None
            for offset, line in enumerate(section):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if cells and cells[0] == "Slice ID":
                    header_idx = hidx + offset
                    break
            if header_idx is None:
                insert = ["", header, sep, row]
                lines[next_heading:next_heading] = insert
            else:
                insert_at = header_idx + 2
                while insert_at < next_heading and lines[insert_at].strip().startswith("|"):
                    insert_at += 1
                lines.insert(insert_at, row)
            text = "\n".join(lines).rstrip() + "\n"
        checklist.write_text(text, encoding="utf-8")
    patch_path = source_doc_patches_dir() / f"{proposal['id']}.md"
    write_text(patch_path, f"# Source-of-truth amendment — {proposal['id']}\n\nAppended to `{relpath(checklist)}`:\n\n```md\n{row}\n```\n")
    return relpath(checklist)


def _insert_task_after_origin(registry: dict[str, Any], task: dict[str, Any], origin_task_id: str | None) -> None:
    tasks = registry.setdefault("tasks", [])
    if any(t.get("id") == task["id"] for t in tasks):
        raise ValueError(f"TASK_ID already exists: {task['id']}")
    index = len(tasks)
    if origin_task_id:
        for i, existing in enumerate(tasks):
            if existing.get("id") == origin_task_id:
                index = i + 1
                break
    tasks.insert(index, task)
    phase = find_phase(registry, task["phase_id"])
    if not phase:
        phase = {"id": task["phase_id"], "title": f"Runtime follow-ups {task['phase_id']}", "status": "blocked", "task_ids": []}
        registry.setdefault("phases", []).append(phase)
        registry.setdefault("phase_order", []).append(task["phase_id"])
    ids = phase.setdefault("task_ids", [])
    if origin_task_id in ids:
        ids.insert(ids.index(origin_task_id) + 1, task["id"])
    elif task["id"] not in ids:
        ids.append(task["id"])


def _recompute_registry_graph(registry: dict[str, Any]) -> dict[str, Any]:
    task_dag = build_task_dag(registry.get("tasks", []) or [])
    registry["task_dag"] = task_dag
    registry["journeys"] = enrich_journey_completion_metadata(registry.get("journeys", []) or [], registry.get("tasks", []) or [], task_dag)
    write_json(memory_dir() / "task-dag.json", task_dag)
    write_text(memory_dir() / "task-dag.md", render_task_dag_markdown(task_dag, registry.get("tasks", []) or []))
    execution_graph_path = memory_dir() / "execution-graph.json"
    if execution_graph_path.exists():
        data = json.loads(execution_graph_path.read_text(encoding="utf-8"))
        data["generated_at"] = now_iso()
        data["phases"] = registry.get("phases", [])
        data["tasks"] = registry.get("tasks", [])
        data["journeys"] = registry.get("journeys", [])
        data["task_dag"] = task_dag
        write_json(execution_graph_path, data)
    return registry


def promote(args: argparse.Namespace) -> dict[str, Any]:
    proposal = _read_yaml(_proposal_path(args.followup_id))
    if proposal.get("status") == "promoted" and proposal.get("promoted_task_id"):
        return {"ok": True, "already_promoted": True, "task_id": proposal.get("promoted_task_id"), "proposal_path": relpath(_proposal_path(args.followup_id))}
    with file_lock(registry_path()):
        registry = load_registry()
        duplicates = _possible_duplicate_followups(proposal, ignore_id=proposal.get("id"))
        blocking_duplicates = []
        for dup in duplicates:
            status = str(dup.get("status") or "").lower()
            task_status = _task_status(registry, dup.get("promoted_task_id"))
            if status == "promoted" or task_status in {"ready", "claimed", "in_progress", "ready_for_close", "verified_pending_close", "done"}:
                dup = dict(dup)
                dup["promoted_task_status"] = task_status
                blocking_duplicates.append(dup)
        if blocking_duplicates and not getattr(args, "allow_duplicate", False):
            raise SystemExit(
                "possible duplicate follow-up already exists/promoted; do not promote another one without human override. "
                "Use waive --reason duplicate_of:<ID> or rerun promote with --allow-duplicate if this is intentionally distinct. "
                + json.dumps(blocking_duplicates, ensure_ascii=False)
            )
        origin = find_task(registry, args.origin_task or proposal.get("origin_task_id")) if (args.origin_task or proposal.get("origin_task_id")) else None
        phase_id = args.phase or proposal.get("origin_phase_id") or (origin or {}).get("phase_id")
        if not phase_id:
            raise SystemExit("phase is required when origin task is unknown")
        phase_id = str(phase_id)
        raw_step_id = args.step or proposal.get("origin_step_id") or (origin or {}).get("step_id")
        step_id = _normalise_step_id(phase_id, raw_step_id)
        task_id = args.task_id or _next_task_id(registry, phase_id, step_id)
        deps = _as_list(args.depends_on) or list(proposal.get("depends_on") or []) or ([origin["id"]] if origin else [])
        _validate_followup_references(registry, proposal, deps)
        done = {t["id"] for t in registry.get("tasks", []) if t.get("status") == "done"}
        deps_ready = all(dep in done for dep in deps)
        status = "ready" if deps_ready else "blocked"
        write_set = list(proposal.get("write_set") or [])
        risk_level = _risk_level_for_severity(proposal.get("severity"))
        task = {
            "id": task_id,
            "phase_id": phase_id,
            "step_id": step_id,
            "title": proposal.get("title") or task_id,
            "status": status,
            "kind": proposal.get("kind") or "followup",
            "target": proposal.get("title") or task_id,
            "build_state": proposal.get("build_state") or "planned",
            "product_increment": proposal.get("product_increment") or os.environ.get("PRODUCT_INCREMENT") or "current",
            "risk_level": risk_level,
            "verify_mode": _verify_mode_for_followup(proposal, risk_level),
            "depends_on": deps,
            "source_ref": f"runtime-followup:{proposal.get('id')}",
            "acceptance": list(proposal.get("acceptance") or []),
            "verification_commands": list(proposal.get("verify") or []),
            "allowed_paths": write_set[:],
            "conflict_groups": list(proposal.get("conflict_groups") or []),
            "write_set": write_set,
            "journey_refs": list(proposal.get("journey_refs") or []),
            "route": _clean_optional(proposal.get("screen_route")),
            "endpoint": _clean_optional(proposal.get("endpoint")),
            "tables": list(proposal.get("tables") or []),
            "handoff_path": f"orchestrator-state/tasks/handoffs/{task_id}.md",
            "evidence_dir": f"orchestrator-state/tasks/evidence/{task_id}",
            "origin": {"type": "runtime_followup", "followup_id": proposal.get("id"), "origin_task_id": proposal.get("origin_task_id"), "severity": proposal.get("severity"), "kind": proposal.get("kind"), "triage": proposal.get("triage") or {}},
            "notes": [f"Runtime follow-up promoted from {proposal.get('id')}", f"Description: {proposal.get('description') or '—'}", f"Triage: {(proposal.get('triage') or {}).get('scope_classification') or 'unspecified'}; why_not_debugger={(proposal.get('triage') or {}).get('why_not_debugger') or '—'}"],
        }
        if deps_ready:
            conflict_blockers = active_conflict_blockers(registry, task)
            if conflict_blockers:
                task["status"] = "blocked"
                status = "blocked"
                task["blocked_reason"] = "conflict_with_worker_task"
                task["blocked_by"] = [str(item.get("task_id")) for item in conflict_blockers if item.get("task_id")]
                task["last_blocker"] = {
                    "type": "conflict_with_worker_task",
                    "blockers": conflict_blockers,
                    "ts": now_iso(),
                }
                task.setdefault("notes", []).append(
                    "Promoted follow-up held blocked because its conflict group/write set overlaps an active DAG task."
                )
        checklist_path = None if args.no_source_doc_update else _append_source_registry_row(task, proposal)
        if checklist_path:
            task["source_ref"] = f"{checklist_path}#Runtime Follow-up Coverage Registry"
        _insert_task_after_origin(registry, task, proposal.get("origin_task_id"))
        # Attach to affected journeys so verify/phase-gate wait for the repair.
        for journey in registry.get("journeys", []) or []:
            if journey.get("id") in set(task.get("journey_refs") or []):
                if task_id not in journey.setdefault("task_ids", []):
                    journey["task_ids"].append(task_id)
                if journey.get("verification_status") in {"verified", "waived"}:
                    journey["verification_status"] = "pending"
                    journey["verified_at"] = None
        registry = _recompute_registry_graph(promote_ready_tasks(registry))
        save_registry(registry)
        _write_phase_yamls(registry)
        write_task_yaml(tasks_dir() / "work-items" / f"{task_id}.yaml", task)
        # Promotion mutates the registry and may introduce/modify endpoints.
        # Keep generated API contracts coherent so immediate validate-only checks
        # in /promote-followup and CI do not fail on stale artifacts.
        generate_contracts(validate_only=False)
        sync_runtime_state_from_registry(load_registry())
    proposal["status"] = "promoted"
    proposal["promoted_at"] = now_iso()
    proposal["promoted_task_id"] = task_id
    proposal["source_doc_updated"] = checklist_path
    _write_yaml(_proposal_path(args.followup_id), proposal)
    with file_lock(runtime_state_path()):
        runtime = _set_open_followup_status(load_runtime_state(), proposal["id"], "promoted", promoted_task_id=task_id)
        save_runtime_state(runtime)
    append_jsonl(ledger_path(), {"ts": now_iso(), "event": "followup_promoted", "followup_id": proposal["id"], "task_id": task_id, "source_doc_updated": checklist_path})
    return {"ok": True, "followup_id": proposal["id"], "task_id": task_id, "status": status, "source_doc_updated": checklist_path}


def waive(args: argparse.Namespace) -> dict[str, Any]:
    proposal = _read_yaml(_proposal_path(args.followup_id))
    proposal["status"] = "waived"
    proposal["waived_at"] = now_iso()
    proposal["waived_by"] = _identity()
    proposal["waiver_reason"] = args.reason
    _write_yaml(_proposal_path(args.followup_id), proposal)
    with file_lock(runtime_state_path()):
        runtime = _set_open_followup_status(load_runtime_state(), proposal["id"], "waived", reason=args.reason)
        save_runtime_state(runtime)
    append_jsonl(ledger_path(), {"ts": now_iso(), "event": "followup_waived", "followup_id": proposal["id"], "reason": args.reason})
    return {"ok": True, "followup_id": proposal["id"], "status": "waived"}


def list_followups(args: argparse.Namespace) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if followups_dir().is_dir():
        for path in sorted(followups_dir().glob("*.yaml")):
            try:
                data = _read_yaml(path)
                if args.status and data.get("status") != args.status:
                    continue
                data["proposal_path"] = relpath(path)
                items.append(data)
            except Exception as exc:
                items.append({"proposal_path": relpath(path), "error": str(exc)})
    return {"ok": True, "count": len(items), "followups": items, "blocking": blocking_open_followups()}


def print_human(result: dict[str, Any]) -> None:
    if "followups" in result:
        print(f"FOLLOWUPS count={result.get('count')}")
        for item in result.get("followups", []):
            triage = item.get("triage") or {}
            classification = item.get("scope_classification") or triage.get("scope_classification") or "unspecified"
            print(f"- {item.get('id')} status={item.get('status')} severity={item.get('severity')} scope={classification} origin={item.get('origin_task_id')} title={item.get('title')}")
        blocking = result.get("blocking") or []
        if blocking:
            print("BLOCKING_FOLLOWUPS:")
            for item in blocking:
                print(f"- {item.get('id')} severity={item.get('severity')} scope={item.get('scope_classification') or 'unspecified'} origin={item.get('origin_task_id')} title={item.get('title')}")
        return
    if result.get("ok"):
        print("OK " + " ".join(f"{k}={v}" for k, v in result.items() if k != "ok"))
    else:
        print("ERROR " + json.dumps(result, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create/promote DAG follow-up tasks from validator/tester findings.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose", help="Write a follow-up proposal YAML only; no registry/source-doc mutation.")
    p.add_argument("--id")
    p.add_argument("--origin-task", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--kind", default="followup")
    p.add_argument("--product-increment", default=None, help="v1/v2/current; stored in Coverage Registry for cumulative product docs.")
    p.add_argument("--build-state", default="planned", help="planned|ready|done; promoted follow-ups normally stay planned.")
    p.add_argument("--severity", default="medium", choices=["low", "medium", "high", "critical", "blocker", "bajo", "media", "alto", "critico", "crítico"])
    p.add_argument("--scope-classification", choices=sorted(FOLLOWUP_SCOPE_CLASSIFICATIONS), default="unspecified", help="Why this is a FU instead of debugger/retest: out_of_scope|missing_coverage|missing_real_data|external_dependency|future_enhancement|scope_expansion|blocked_by_human_decision. in_scope_defect is rejected.")
    p.add_argument("--why-not-debugger", default="", help="Required for blocking FU; explain why validator/tester -> debugger -> retest cannot fix this inside the current TASK_ID.")
    p.add_argument("--phase")
    p.add_argument("--step")
    p.add_argument("--depends-on", action="append")
    p.add_argument("--conflict-group", action="append")
    p.add_argument("--write-set", action="append")
    p.add_argument("--journey-ref", action="append")
    p.add_argument("--screen-route")
    p.add_argument("--endpoint")
    p.add_argument("--table", action="append")
    p.add_argument("--acceptance", action="append")
    p.add_argument("--verify", action="append")
    p.add_argument("--note", action="append")

    pp = sub.add_parser("promote", help="Promote a proposal into source-of-truth + registry + work-item YAML.")
    pp.add_argument("followup_id")
    pp.add_argument("--task-id")
    pp.add_argument("--origin-task")
    pp.add_argument("--phase")
    pp.add_argument("--step")
    pp.add_argument("--depends-on", action="append")
    pp.add_argument("--no-source-doc-update", action="store_true")
    pp.add_argument("--allow-duplicate", action="store_true", help="Override duplicate follow-up guard after human review")

    w = sub.add_parser("waive", help="Waive a proposal after human decision.")
    w.add_argument("followup_id")
    w.add_argument("--reason", required=True)

    l = sub.add_parser("list", help="List follow-up proposals.")
    l.add_argument("--status")

    parser.add_argument("--json", action="store_true", help="Print JSON. May appear before the subcommand.")
    for sp in (p, pp, w, l):
        sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print JSON. May appear after the subcommand.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "propose":
        result = propose(args)
    elif args.command == "promote":
        result = promote(args)
    elif args.command == "waive":
        result = waive(args)
    elif args.command == "list":
        result = list_followups(args)
    else:  # pragma: no cover
        parser.error("unknown command")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
