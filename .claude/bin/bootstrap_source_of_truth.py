#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import (
    PHASE_RE,
    append_jsonl,
    claude_dir,
    canonical_source_docs_dir,
    discover_source_docs,
    docs_are_in_canonical_dir,
    ensure_parent,
    extract_headings,
    extract_items,
    load_registry,
    load_runtime_state,
    memory_dir,
    now_iso,
    phase_headings,
    project_root,
    read_text,
    relpath,
    save_registry,
    save_runtime_state,
    sha256_file,
    slugify,
    tasks_dir,
    write_json,
    write_text,
)
from stack_profile import load_stack_profile, find_stack_profile

PHASE_KEYWORD_RE = re.compile(r"(?i)\b(?:fase|phase)\b")
CONSTRAINT_RE = re.compile(r"(?i)\b(?:must|must not|should|required|constraint|invariant|never|regla|obligatorio|prohibido|debe|no debe)\b")
UNFILLED_TEMPLATE_MARKERS_RE = re.compile(r">>> MODELO:|📋 SI APLICA")

# Journey Coverage Matrix parsing (added by journey-verification feature).
# Matches a markdown table row whose first cell is a journey ID like "J101".
JOURNEY_ROW_RE = re.compile(r"^\|\s*(J\d+)\s*\|", re.MULTILINE)
# Section heading: "## 3.5 Journey Coverage Matrix" (case-insensitive, accepts variations).
JOURNEY_SECTION_RE = re.compile(r"(?i)\bJourney\s+Coverage\s+Matrix\b")
# Slice range: "P03-S02-T001..T004" → expands to T001, T002, T003, T004.
SLICE_RANGE_RE = re.compile(r"^([A-Z]\d+-[A-Z]\d+-[A-Z])(\d+)\.\.([A-Z]?)(\d+)$")
# Step ref: "P00-S05" → expand to all tasks under that step.
STEP_REF_RE = re.compile(r"^([A-Z]\d+-S\d+)$")
# Phase ref: "P00" → expand to all tasks under that phase.
PHASE_REF_RE = re.compile(r"^([A-Z]\d+)$")
# Full TASK_ID: "P00-S05-T001".
TASK_ID_RE = re.compile(r"^[A-Z]\d+-S\d+-T\d+$")

# A synthetic step task whose acceptance count exceeds this threshold is
# almost certainly too coarse for a single slice (recall: each slice runs
# through the 20-spawn pipeline and must be verifiable in localhost). When
# crossed, the bootstrap surfaces a validation warning so the user adds
# either canonical Slice IDs in the registry or `###` sub-headings inside
# the step body to drive a sensible split.
SYNTHETIC_COARSE_THRESHOLD = 10
# Placeholder for escaped pipes inside a markdown table cell (`\|`). Using NUL
# bytes guarantees the placeholder cannot collide with real cell content.
_ESC_PIPE = "\x00ESCAPED_PIPE\x00"


# Coverage Registry parsing (Fix B1).
#
# A "Coverage Registry" is any markdown table whose header row's first cell
# is exactly "Slice ID". Each row's first cell is then a TASK_ID like
# "P00-S01-T001". The bootstrap treats these tables as the AUTHORITATIVE
# source of canonical task IDs, instead of regenerating them positionally
# from the order in which steps appear in the document body. This is what
# closes the gap between the IDs declared in the docs (and referenced from
# every other table + journey) and the IDs the bootstrap actually emits.
#
# The canonical column name is "Slice ID", but the parser also accepts the
# common synonyms "Slice", "Task ID", and "TaskID" (case-insensitive). It
# does NOT accept a bare "ID" — that header is too generic and would
# spuriously match unrelated tables that happen to start with "| ID |".
# Tables whose first column header looks like an ID column variant we did
# NOT recognize are reported as warnings by
# detect_unrecognized_coverage_registries, so silent drift is impossible.
COVERAGE_HEADER_RE = re.compile(
    r"^\|\s*(?:Slice\s*ID|Task\s*ID|TaskID|Slice)\s*\|", re.IGNORECASE
)
# Lower-cased header cells that should be treated as the ID column when
# normalizing cell_by_header keys (used to skip the ID column when looking
# for the acceptance cell, etc.).
_ID_HEADER_KEYS = frozenset({"slice id", "task id", "taskid", "slice"})
_DEPENDENCY_HEADER_RE = re.compile(
    r"(?i)^(?:depends?\s*on|dependencies?|deps|after|blocked\s*by|dependencias?|depende\s*de)$"
)
_DEPENDENCY_NONE_VALUES = {"", "-", "—", "none", "n/a", "na", "null", "sin dependencias", "ninguna"}
_CONFLICT_HEADER_RE = re.compile(r"(?i)^(?:conflict\s*groups?|conflict\s*group|grupo(?:s)?\s*de\s*conflicto|seriali[sz]e\s*group)$")
_WRITE_SET_HEADER_RE = re.compile(r"(?i)^(?:write\s*set|writes?|expected\s*files\s*touched|files\s*touched|touches|ficheros\s*esperados|archivos\s*esperados)$")
_DELETE_SET_HEADER_RE = re.compile(r"(?i)^(?:delete\s*set|allowed\s*deletions?|delete\s*paths?|remove\s*set|removes?|expected\s*deletions?|borrados?|eliminaciones?)$")
_PRODUCT_INCREMENT_HEADER_RE = re.compile(r"(?i)^(?:product\s*increment|increment|version|release|m[óo]dulo|modulo|producto\s*versi[óo]n)$")
_BUILD_STATE_HEADER_RE = re.compile(r"(?i)^(?:build\s*state|estado\s*build|estado|lifecycle|baseline\s*state|status\s*inicial)$")
_RISK_LEVEL_HEADER_RE = re.compile(r"(?i)^(?:risk\s*level|risk|riesgo|nivel\s*de\s*riesgo)$")
_VERIFY_MODE_HEADER_RE = re.compile(r"(?i)^(?:verify\s*mode|verification\s*mode|modo\s*verify|modo\s*verificaci[óo]n)$")

_VERIFY_MINIMUM_HEADER_RE = re.compile(r"(?i)^(?:verify\s*m[ií]nimo|verify\s*minimum|verification\s*minimum|minimum\s*verify|verificaci[oó]n\s*m[ií]nima|comandos?\s*de\s*verificaci[oó]n)$")
_META_NONE_VALUES = {"", "-", "—", "none", "n/a", "na", "null", "sin conflicto", "sin conflictos", "read-only", "readonly", "no-write", "no-write-set"}




def _normalize_header_alias(key: str) -> str:
    """Normalize markdown table headers for semantic lookup.

    This is intentionally small/local: Coverage Registry parsing should be
    tolerant to Spanish/English labels and spacing, but strict enough not to
    guess unrelated columns.
    """
    value = _strip_md_inline(key).strip().lower()
    trans = str.maketrans({
        "á":"a", "é":"e", "í":"i", "ó":"o", "ú":"u", "ü":"u", "ñ":"n",
        "Á":"a", "É":"e", "Í":"i", "Ó":"o", "Ú":"u", "Ü":"u", "Ñ":"n",
    })
    value = value.translate(trans)
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _cell_by_alias(cell_by_header: dict[str, str], aliases: set[str]) -> str:
    norm_aliases = {_normalize_header_alias(a) for a in aliases}
    for key, value in cell_by_header.items():
        if _normalize_header_alias(key) in norm_aliases:
            return _strip_md_inline(value)
    return ""


def _registry_optional(value: str) -> str:
    clean = _strip_md_inline(value)
    if clean.strip().lower() in _META_NONE_VALUES or clean.strip().lower() in _DEPENDENCY_NONE_VALUES:
        return ""
    return clean


def _is_id_header_key(key: str) -> bool:
    """True for any header cell that should be treated as the canonical ID
    column. The parser uses this to skip the ID column when scanning for
    acceptance/verify cells."""
    return key.strip().lower() in _ID_HEADER_KEYS


def _is_dependency_header_key(key: str) -> bool:
    """True for the optional Coverage Registry dependency column.

    The source of truth is an adjacency list, not a hand-maintained NxN matrix:
    each row declares the predecessors that must be ``done`` before this slice
    can become ready. The bootstrap derives the adjacency matrix from it.
    """
    return bool(_DEPENDENCY_HEADER_RE.match(key.strip().lower()))


def _is_conflict_header_key(key: str) -> bool:
    """True for the optional scheduling conflict group column."""
    return bool(_CONFLICT_HEADER_RE.match(key.strip().lower()))


def _is_write_set_header_key(key: str) -> bool:
    """True for the optional expected write-set column."""
    return bool(_WRITE_SET_HEADER_RE.match(key.strip().lower()))


def _is_delete_set_header_key(key: str) -> bool:
    """True for the optional explicit deletion-set column.

    write_set permits edits/creates; destructive removals must be declared
    separately so broad globs cannot erase unrelated product modules.
    """
    return bool(_DELETE_SET_HEADER_RE.match(key.strip().lower()))


def _is_product_increment_header_key(key: str) -> bool:
    """True for the optional product increment/version column.

    This lets one cumulative source-of-truth represent existing baseline + v1 + v2 +
    ... without losing context. The bootstrap stores it on each task and uses
    Build state to keep already-built baseline tasks closed.
    """
    return bool(_PRODUCT_INCREMENT_HEADER_RE.match(key.strip().lower()))


def _is_build_state_header_key(key: str) -> bool:
    """True for the optional initial build-state column."""
    return bool(_BUILD_STATE_HEADER_RE.match(key.strip().lower()))


def _is_risk_level_header_key(key: str) -> bool:
    """True for the risk level column used by verify gating."""
    return bool(_RISK_LEVEL_HEADER_RE.match(key.strip().lower()))


def _is_verify_mode_header_key(key: str) -> bool:
    """True for the verify mode column used by /verify-slice vs /auto-verify-slice."""
    return bool(_VERIFY_MODE_HEADER_RE.match(key.strip().lower()))


def _is_verify_minimum_header_key(key: str) -> bool:
    """True for the verification commands/minimum column, not Verify mode.

    This prevents the Coverage Registry parser from accidentally treating
    `Verify mode=auto|human` as the task's verification command when the
    mode column appears before `Verify mínimo`.
    """
    return bool(_VERIFY_MINIMUM_HEADER_RE.match(key.strip().lower()))


_DONE_BUILD_STATES = {"done", "built", "closed", "verified", "shipped", "released", "baseline", "construida", "construido", "hecha", "hecho", "cerrada", "cerrado"}
_BLOCKED_BUILD_STATES = {"blocked", "bloqueada", "bloqueado"}
_READY_BUILD_STATES = {"ready", "lista", "listo"}


def _normalise_build_state(value: str) -> str:
    return _strip_md_inline(value).strip().lower()


def _status_from_build_state(value: str, default: str) -> str:
    state = _normalise_build_state(value)
    if state in _DONE_BUILD_STATES:
        return "done"
    if state in _BLOCKED_BUILD_STATES:
        return "blocked"
    if state in _READY_BUILD_STATES:
        return "ready"
    return default


def _split_meta_refs(value: str) -> list[str]:
    """Split conflict group / write-set cells into stable scheduler hints."""
    clean = _strip_md_inline(value)
    if clean.lower().strip() in _META_NONE_VALUES:
        return []
    refs: list[str] = []
    for chunk in re.split(r"[,;\n]", clean):
        ref = _strip_md_inline(chunk)
        if ref and ref.lower() not in _META_NONE_VALUES and ref not in refs:
            refs.append(ref)
    return refs


_INFRA_SCOPE_RULES: tuple[tuple[re.Pattern[str], tuple[str, ...], tuple[str, ...]], ...] = (
    (re.compile(r"(?i)\bdocker-compose\.ya?ml\b|\bcompose\.ya?ml\b"), ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"), ("infra:compose",)),
    (re.compile(r"(?i)\bdockerfile\b"), ("Dockerfile*",), ("infra:docker",)),
    (re.compile(r"(?i)(?<![\w])\.env\.example(?![\w])|\benv overrides?\b|\benvironment overrides?\b"), (".env.example",), ("infra:env",)),
    (re.compile(r"(?i)\bgithub actions?\b|\bworkflow\b|\bci/cd\b"), (".github/workflows/**",), ("ci:workflows",)),
)


def _append_unique(values: list[str], additions: tuple[str, ...]) -> list[str]:
    out = list(values or [])
    for item in additions:
        if item and item not in out:
            out.append(item)
    return out


def _augment_task_scope_from_text(tasks: list[dict[str, Any]]) -> None:
    """Add exact shared-config paths when acceptance text names them.

    The Coverage Registry remains authoritative, but large-app generation can
    drift by saying e.g. "docker-compose.yml env overrides updated" while the
    row's Write set only contains a broad feature path. Without this small
    repair, the developer prompt sees an impossible task: acceptance requires a
    root config edit but `allowed_paths` omits that file. The inferred paths are
    also added to `write_set`, so DAG wave selection serializes shared infra.
    """
    for task in tasks:
        text = "\n".join([
            str(task.get("title") or ""),
            *[str(x) for x in (task.get("acceptance") or [])],
            *[str(x) for x in (task.get("verification_commands") or [])],
        ])
        inferred_paths: list[str] = []
        inferred_groups: list[str] = []
        for regex, paths, groups in _INFRA_SCOPE_RULES:
            if not regex.search(text):
                continue
            inferred_paths = _append_unique(inferred_paths, paths)
            inferred_groups = _append_unique(inferred_groups, groups)
        if not inferred_paths and not inferred_groups:
            continue
        task["allowed_paths"] = _append_unique(list(task.get("allowed_paths") or []), tuple(inferred_paths))
        task["write_set"] = _append_unique(list(task.get("write_set") or []), tuple(inferred_paths))
        task["conflict_groups"] = _append_unique(list(task.get("conflict_groups") or []), tuple(inferred_groups))
        task.setdefault("scope_inferred_from_acceptance", [])
        task["scope_inferred_from_acceptance"] = _append_unique(list(task.get("scope_inferred_from_acceptance") or []), tuple(inferred_paths + inferred_groups))


# A canonical TASK_ID column value: "P00-S01-T001" (no backticks).
# Accepts any number of digits per segment to match the broader TASK_ID_RE
# above — projects in early stages may use single-digit IDs (P0-S1-T1) and
# the framework should not silently fall back to positional generation just
# because the user did not zero-pad. The recommended canonical format is
# still 2-2-3 digits, but a stricter regex here than at TASK_ID_RE produced
# silent drift between Coverage Registry parsing and journey expansion.
COVERAGE_ROW_ID_RE = re.compile(r"^[A-Z]\d+-S\d+-T\d+$")
# "Step 0.1", "Step 2.4", etc. (case-insensitive, accepts trailing punctuation).
STEP_HEADING_RE = re.compile(
    r"(?i)^\s*Step\s+(\d+)(?:\.(\d+))?\s*[-—:]?\s*(.*)$"
)


def _strip_md_inline(value: str) -> str:
    """Remove markdown noise (backticks) and whitespace from a cell value.

    Markdown tables routinely wrap codey content in backticks; the bootstrap
    used to keep them verbatim, which broke every regex match downstream.
    Used by both the registry parser and the journey slice expander.
    """
    if not value:
        return ""
    return value.replace("`", "").replace("\\|", "|").strip()


def _split_registry_cell_items(value: str) -> list[str]:
    """Split a compact registry cell into task-level bullet criteria.

    The templates ask ChatGPT to keep Coverage Registry rows compact, so a
    single table cell may contain multiple checks separated by semicolons or
    line breaks. We keep it deterministic and intentionally do not split on
    commas because endpoints, table lists and route names often contain commas.
    """
    items: list[str] = []
    for chunk in re.split(r"[;\n]", value or ""):
        chunk = _strip_md_inline(chunk)
        if chunk and chunk not in {"—", "-"}:
            items.append(chunk)
    return items


def _split_dependency_refs(value: str) -> list[str]:
    """Split a Coverage Registry ``Depends on`` cell into dependency refs."""
    clean = _strip_md_inline(value)
    if clean.lower().strip() in _DEPENDENCY_NONE_VALUES:
        return []
    refs: list[str] = []
    for chunk in re.split(r"[,;\n]", clean):
        ref = _strip_md_inline(chunk)
        if ref and ref.lower() not in _DEPENDENCY_NONE_VALUES:
            refs.append(ref)
    return refs



def _normalize_step_ref(value: str, implicit_step_ref: str) -> str:
    """Normalize common Coverage Registry step-cell forms to ``Step N.M``.

    Templates ask for values like ``Step 2.1``. Users often write compact
    forms such as ``S01`` or ``P02-S01``; normalizing them prevents the
    bootstrap from treating the body step as uncovered and emitting duplicate
    synthetic tasks before the canonical registry rows.
    """
    clean = _strip_md_inline(value)
    if not clean:
        return implicit_step_ref
    m = re.match(r"^P(\d+)-S(\d+)$", clean, re.IGNORECASE)
    if m:
        return f"Step {int(m.group(1))}.{int(m.group(2))}"
    m = re.match(r"^S(\d+)$", clean, re.IGNORECASE)
    if m and implicit_step_ref:
        phase_match = re.match(r"(?i)^Step\s+(\d+)\.", implicit_step_ref)
        phase_n = int(phase_match.group(1)) if phase_match else 0
        return f"Step {phase_n}.{int(m.group(1))}"
    m = re.match(r"^(\d+)\.(\d+)$", clean)
    if m:
        return f"Step {int(m.group(1))}.{int(m.group(2))}"
    return clean

def parse_coverage_registry(checklist_text: str) -> list[dict[str, Any]]:
    """Parse every Coverage Registry table in the checklist.

    Returns a list of canonical task dicts in document order, each with:
      - id, phase_id, step_id (derived from id)
      - title (best-effort: method+path for endpoint registry, otherwise
        the most informative target/screen/table/topic column)
      - acceptance (row-specific criteria from Acceptance/Criterios/DoD cells;
        synthesized from the row title + verify cell when omitted)
      - verification_commands (Verify/Verificación cell split on ';' / newline)
      - step_ref (the "Step X.Y" reference cell, used to locate the matching
        body section). Empty string if no such column exists.
      - depends_on_raw / dependency_column_present (optional DAG adjacency)
      - conflict_groups / write_set / delete_set (optional DAG guardrails)
      - source_columns (raw cells, kept for traceability/debugging)

    Multiple tables may declare overlapping IDs (rare but legal) — the FIRST
    occurrence wins, later duplicates are merged additively. Robust to
    backslash-escaped pipes inside cells (uses _split_md_table_row).
    """
    if not checklist_text:
        return []

    lines = checklist_text.splitlines()
    canonical: dict[str, dict[str, Any]] = {}
    canonical_order: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if not COVERAGE_HEADER_RE.match(line):
            i += 1
            continue
        header_cells = _split_md_table_row(line)
        j = i + 1
        if j < len(lines) and re.match(r"^\|[\s:\-|]+\|?\s*$", lines[j]):
            j += 1
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            row_cells = _split_md_table_row(lines[j])
            if not row_cells:
                j += 1
                continue
            raw_id = _strip_md_inline(row_cells[0])
            if not COVERAGE_ROW_ID_RE.match(raw_id):
                j += 1
                continue
            phase_id = raw_id.split("-")[0]
            step_id = "-".join(raw_id.split("-")[:2])

            try:
                phase_n = int(phase_id[1:])
                step_n = int(step_id.rsplit("-S", 1)[1])
                implicit_step_ref = f"Step {phase_n}.{step_n}"
            except Exception:
                implicit_step_ref = ""

            cell_by_header: dict[str, str] = {}
            for h, c in zip(header_cells, row_cells):
                cell_by_header[_strip_md_inline(h).lower()] = _strip_md_inline(c)

            dependency_column_present = False
            depends_on_raw = ""
            for k, v in cell_by_header.items():
                if _is_dependency_header_key(k):
                    dependency_column_present = True
                    depends_on_raw = v
                    break

            conflict_groups_raw = ""
            write_set_raw = ""
            delete_set_raw = ""
            product_increment_raw = ""
            build_state_raw = ""
            risk_level_raw = ""
            verify_mode_raw = ""
            for k, v in cell_by_header.items():
                if _is_conflict_header_key(k):
                    conflict_groups_raw = v
                if _is_write_set_header_key(k):
                    write_set_raw = v
                if _is_delete_set_header_key(k):
                    delete_set_raw = v
                if _is_product_increment_header_key(k):
                    product_increment_raw = v
                if _is_build_state_header_key(k):
                    build_state_raw = v
                if _is_risk_level_header_key(k):
                    risk_level_raw = v
                if _is_verify_mode_header_key(k):
                    verify_mode_raw = v

            # Production wiring metadata. These fields let planner/developer/tester
            # reason from the task record itself instead of scraping free text or
            # relying on the unsafe global singleton.
            kind_raw = _cell_by_alias(cell_by_header, {"tipo", "kind", "type"})
            target_raw = _cell_by_alias(cell_by_header, {"target", "objetivo", "scope", "deliverable", "entregable", "page/widget", "page / widget"})
            journey_refs_raw = _cell_by_alias(cell_by_header, {"journey refs", "journeys", "journey", "recorridos", "referencias journey"})
            screen_route_raw = _cell_by_alias(cell_by_header, {"pantalla/ruta", "pantalla / ruta", "screen/route", "screen / route", "ruta", "route", "page", "screen", "pantalla"})
            endpoint_raw = _cell_by_alias(cell_by_header, {"endpoint", "endpoints", "api", "path"})
            tables_raw = _cell_by_alias(cell_by_header, {"tablas db", "tablas", "tables", "db tables", "tablas/objetos", "tablas / objetos"})
            origin_instr_raw = _cell_by_alias(cell_by_header, {"origen-instr", "origen instr", "source instr", "instructions source", "source instrucciones"})
            origin_techguide_raw = _cell_by_alias(cell_by_header, {"origen-techguide", "origen techguide", "source techguide", "technical guide source"})

            step_ref = ""
            # Prefer explicit Step-like columns. A separate Phase column is not
            # a body-step reference; using it here would prevent canonical rows
            # from matching their Step headings and cause duplicate synthetic
            # tasks.
            for k, v in cell_by_header.items():
                if "step" in k:
                    step_ref = v
                    break
            step_ref = _normalize_step_ref(step_ref, implicit_step_ref)

            verify = ""
            for k, v in cell_by_header.items():
                if _is_verify_minimum_header_key(k):
                    verify = v
                    break
            if not verify:
                # Compatibility for older checklist tables that had a
                # generic Verify/Verificación column but no Verify mode column.
                for k, v in cell_by_header.items():
                    if _is_verify_mode_header_key(k):
                        continue
                    if k in {"verify", "verification", "verificación", "verificacion"}:
                        verify = v
                        break

            acceptance_raw = ""
            for k, v in cell_by_header.items():
                if _is_id_header_key(k):
                    continue
                if (
                    "acceptance" in k
                    or "criterio" in k
                    or "criterios" in k
                    or "dod" in k
                    or "done" in k
                    or "entregable" in k
                ):
                    acceptance_raw = v
                    break

            method = cell_by_header.get("method", "")
            path = cell_by_header.get("path", "")
            if method and path:
                title = f"{method} {path}".strip()
            else:
                title = ""
                for k in (
                    "target", "objetivo", "deliverable", "entregable",
                    "page / widget", "page", "widget",
                    "screen / feature", "screen", "feature",
                    "table", "tables", "migration", "migration / objeto",
                    "objeto", "scope", "name", "topic",
                ):
                    if cell_by_header.get(k):
                        title = cell_by_header[k]
                        break
                if not title:
                    title = (row_cells[1] if len(row_cells) > 1 else raw_id).strip()
                    title = _strip_md_inline(title)

            verification_commands = _split_registry_cell_items(verify)
            row_acceptance = _split_registry_cell_items(acceptance_raw)
            if not row_acceptance:
                row_acceptance = [f"Deliver {title}."]
                if verify:
                    row_acceptance.append(f"Verify: {verify}.")

            existing = canonical.get(raw_id)
            if existing is None:
                canonical[raw_id] = {
                    "id": raw_id,
                    "phase_id": phase_id,
                    "step_id": step_id,
                    "title": title,
                    "acceptance": row_acceptance,
                    "verification_commands": verification_commands,
                    "step_ref": step_ref,
                    "depends_on_raw": depends_on_raw,
                    "dependency_column_present": dependency_column_present,
                    "conflict_groups": _split_meta_refs(conflict_groups_raw),
                    "write_set": _split_meta_refs(write_set_raw),
                    "delete_set": _split_meta_refs(delete_set_raw),
                    "product_increment": _strip_md_inline(product_increment_raw) or "unspecified",
                    "build_state": _strip_md_inline(build_state_raw) or "planned",
                    "risk_level": (_strip_md_inline(risk_level_raw) or "medium").lower(),
                    "verify_mode": (_strip_md_inline(verify_mode_raw) or "human").lower(),
                    "kind": _registry_optional(kind_raw).lower() or "unspecified",
                    "target": _registry_optional(target_raw),
                    "journey_refs": _split_meta_refs(journey_refs_raw),
                    "route": _registry_optional(screen_route_raw),
                    "endpoint": _registry_optional(endpoint_raw),
                    "tables": _split_meta_refs(tables_raw),
                    "origin_instr": _registry_optional(origin_instr_raw),
                    "origin_techguide": _registry_optional(origin_techguide_raw),
                    "kind_raw": kind_raw,
                    "target_raw": target_raw,
                    "journey_refs_raw": journey_refs_raw,
                    "screen_route_raw": screen_route_raw,
                    "endpoint_raw": endpoint_raw,
                    "tables_raw": tables_raw,
                    "origin_instr_raw": origin_instr_raw,
                    "origin_techguide_raw": origin_techguide_raw,
                    "source_cells_by_header": dict(cell_by_header),
                    "conflict_groups_raw": conflict_groups_raw,
                    "write_set_raw": write_set_raw,
                    "delete_set_raw": delete_set_raw,
                    "product_increment_raw": product_increment_raw,
                    "build_state_raw": build_state_raw,
                    "risk_level_raw": risk_level_raw,
                    "verify_mode_raw": verify_mode_raw,
                    "source_columns": row_cells,
                }
                canonical_order.append(raw_id)
            else:
                if not existing.get("title"):
                    existing["title"] = title
                if not existing.get("step_ref"):
                    existing["step_ref"] = step_ref
                if not existing.get("verification_commands"):
                    existing["verification_commands"] = verification_commands
                if not existing.get("acceptance"):
                    existing["acceptance"] = row_acceptance
                if dependency_column_present:
                    existing["dependency_column_present"] = True
                    if depends_on_raw and not existing.get("depends_on_raw"):
                        existing["depends_on_raw"] = depends_on_raw
                for key, raw_value in (("conflict_groups", conflict_groups_raw), ("write_set", write_set_raw), ("delete_set", delete_set_raw)):
                    existing_items = list(existing.get(key) or [])
                    for item in _split_meta_refs(raw_value):
                        if item not in existing_items:
                            existing_items.append(item)
                    existing[key] = existing_items
                if conflict_groups_raw and not existing.get("conflict_groups_raw"):
                    existing["conflict_groups_raw"] = conflict_groups_raw
                if write_set_raw and not existing.get("write_set_raw"):
                    existing["write_set_raw"] = write_set_raw
                if delete_set_raw and not existing.get("delete_set_raw"):
                    existing["delete_set_raw"] = delete_set_raw
                if product_increment_raw and not existing.get("product_increment_raw"):
                    existing["product_increment_raw"] = product_increment_raw
                    existing["product_increment"] = _strip_md_inline(product_increment_raw) or existing.get("product_increment") or "unspecified"
                if build_state_raw and not existing.get("build_state_raw"):
                    existing["build_state_raw"] = build_state_raw
                    existing["build_state"] = _strip_md_inline(build_state_raw) or existing.get("build_state") or "planned"
                if risk_level_raw and not existing.get("risk_level_raw"):
                    existing["risk_level_raw"] = risk_level_raw
                    existing["risk_level"] = (_strip_md_inline(risk_level_raw) or existing.get("risk_level") or "medium").lower()
                if verify_mode_raw and not existing.get("verify_mode_raw"):
                    existing["verify_mode_raw"] = verify_mode_raw
                    existing["verify_mode"] = (_strip_md_inline(verify_mode_raw) or existing.get("verify_mode") or "human").lower()
                for key, value in (
                    ("kind", _registry_optional(kind_raw).lower()),
                    ("target", _registry_optional(target_raw)),
                    ("route", _registry_optional(screen_route_raw)),
                    ("endpoint", _registry_optional(endpoint_raw)),
                    ("origin_instr", _registry_optional(origin_instr_raw)),
                    ("origin_techguide", _registry_optional(origin_techguide_raw)),
                ):
                    if value and not existing.get(key):
                        existing[key] = value
                for key, raw_value in (("journey_refs", journey_refs_raw), ("tables", tables_raw)):
                    existing_items = list(existing.get(key) or [])
                    for item in _split_meta_refs(raw_value):
                        if item not in existing_items:
                            existing_items.append(item)
                    existing[key] = existing_items
                for key, value in (
                    ("kind_raw", kind_raw), ("target_raw", target_raw), ("journey_refs_raw", journey_refs_raw),
                    ("screen_route_raw", screen_route_raw), ("endpoint_raw", endpoint_raw), ("tables_raw", tables_raw),
                    ("origin_instr_raw", origin_instr_raw), ("origin_techguide_raw", origin_techguide_raw),
                ):
                    if value and not existing.get(key):
                        existing[key] = value
                existing.setdefault("source_cells_by_header", {}).update(cell_by_header)
            j += 1
        i = j

    return [canonical[tid] for tid in canonical_order]


def detect_unrecognized_coverage_registries(checklist_text: str) -> list[str]:
    """Find tables that look like Coverage Registries but use an unrecognized
    header. Returns human-readable warnings; empty list when everything is fine.

    A table is flagged when:
      * It is a markdown table (header row + ``|---|`` separator + data row).
      * The first cell of the first data row matches the canonical TASK_ID
        shape (``P00-S01-T001``).
      * The table header is NOT matched by ``COVERAGE_HEADER_RE``.

    This catches the silent-drift case where a user wrote "| Task |" or
    "| ID |" instead of "| Slice ID |": the bootstrap would otherwise fall
    back to positional task generation and emit IDs that don't line up with
    the journey matrix or any other doc reference.

    Called by ``build_phases_and_tasks`` and surfaced via the validation
    warnings list, so the user sees the issue at the next bootstrap run
    rather than discovering it weeks later when /next-slice picks the wrong
    task.
    """
    warnings: list[str] = []
    if not checklist_text:
        return warnings
    lines = checklist_text.splitlines()
    sep_re = re.compile(r"^\|[\s:\-|]+\|?\s*$")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("|"):
            i += 1
            continue
        # Already-recognized: skip — those are parsed properly.
        if COVERAGE_HEADER_RE.match(line):
            i += 1
            continue
        # Need a separator row right below to qualify as a markdown table.
        if i + 1 >= len(lines) or not sep_re.match(lines[i + 1]):
            i += 1
            continue
        # First data row.
        k = i + 2
        if k >= len(lines) or not lines[k].lstrip().startswith("|"):
            i += 1
            continue
        cells = _split_md_table_row(lines[k])
        if not cells:
            i += 1
            continue
        first = _strip_md_inline(cells[0])
        if not COVERAGE_ROW_ID_RE.match(first):
            i += 1
            continue
        # Looks like a coverage registry by content but the header is wrong.
        header_cells = _split_md_table_row(line)
        header_label = _strip_md_inline(header_cells[0]) if header_cells else line.strip()
        warnings.append(
            f"Line {i + 1}: table looks like a Coverage Registry (first row "
            f"is `{first}`) but its header `{header_label}` is not one of: "
            f"'Slice ID', 'Slice', 'Task ID', 'TaskID'. The bootstrap will "
            f"NOT pick up its IDs — rename the header to 'Slice ID' to make "
            f"it authoritative, or remove the table if it is unrelated."
        )
        i += 1
    return warnings


def _step_headings_only(child_headings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter (Fix B2): keep only headings shaped like ``## Step N.M ...``.

    Rejects PRE-GATE, PHASE GATE, "Phase 2 canonical slices", emoji headings,
    and any meta-section that pollutes the step indexing. The original
    bootstrap counted every shallowest heading under a phase as a step,
    silently shifting every step number relative to the human-readable
    Step X.Y referenced in the rest of the docs.
    """
    return [h for h in child_headings if STEP_HEADING_RE.match(h["title"])]


def _step_section_lines(checklist_text: str, headings: list[dict[str, Any]],
                        target: dict[str, Any], phase_end: int) -> list[str]:
    """Return the body lines for a single ## Step heading."""
    next_line = phase_end
    for h in headings:
        if h["line"] > target["line"] and h["level"] <= target["level"]:
            next_line = h["line"]
            break
    return checklist_text.splitlines()[target["line"] - 1 : max(0, next_line - 1)]


def _find_step_heading_for_ref(step_headings: list[dict[str, Any]],
                               step_ref: str) -> dict[str, Any] | None:
    """Match a registry's `step_ref` (e.g. "Step 0.1") to a body heading.

    Tolerates "Step 0.1", "step 0.1 — title", "step0.1", with or without
    surrounding noise. Returns None if no match is found (the canonical task
    still gets generated, just without acceptance from the body).
    """
    if not step_ref:
        return None
    target = re.sub(r"\s+", "", step_ref).lower()
    target_match = re.search(r"step(\d+(?:\.\d+)?)", target)
    if not target_match:
        return None
    target_num = target_match.group(1)
    for h in step_headings:
        m = STEP_HEADING_RE.match(h["title"])
        if not m:
            continue
        major = m.group(1)
        minor = m.group(2)
        full = f"{major}.{minor}" if minor else major
        if full == target_num:
            return h
    return None


def _split_md_table_row(line: str) -> list[str]:
    """Split a markdown table row by '|', respecting backslash-escaped pipes.

    A literal pipe inside a cell is written as '\\|' in markdown — the renderer
    treats it as content, not as a column separator. Naive `line.split("|")`
    breaks the row whenever a cell uses this escape (the J2 OAuth row in the
    baseline snapshot matrix is the canonical case). Replace the escape with a NUL
    placeholder, split, then restore.
    """
    safe = (line or "").replace("\\|", _ESC_PIPE)
    fields = [f.replace(_ESC_PIPE, "|").strip() for f in safe.split("|")]
    while fields and fields[0] == "":
        fields.pop(0)
    while fields and fields[-1] == "":
        fields.pop()
    return fields


def _expand_slice_ref(ref: str, all_tasks: list[dict[str, Any]]) -> list[str]:
    """Expand one slice cell entry to a list of TASK_IDs.

    Accepted forms:
      - Full TASK_ID:  "P00-S05-T001"          → kept as-is.
      - Range:         "P00-S05-T001..T003"    → enumerated.
      - Step ref:      "P00-S05"               → all tasks of that step.
      - Phase ref:     "P00"                   → all tasks of that phase.
      - Anything else (descriptive text)       → returned verbatim as a single
        entry, so the validator can flag it as drift instead of silently
        dropping it.
    """
    s = (ref or "").strip()
    if not s:
        return []
    if TASK_ID_RE.match(s):
        return [s]
    rng = SLICE_RANGE_RE.match(s)
    if rng:
        prefix = rng.group(1)
        start_n = int(rng.group(2))
        end_n = int(rng.group(4))
        width = len(rng.group(2))
        return [f"{prefix}{str(n).zfill(width)}" for n in range(start_n, end_n + 1)]
    step_match = STEP_REF_RE.match(s)
    if step_match:
        step_id = step_match.group(1)
        return [t["id"] for t in all_tasks if t.get("step_id") == step_id]
    phase_match = PHASE_REF_RE.match(s)
    if phase_match:
        phase_id = phase_match.group(1)
        return [t["id"] for t in all_tasks if t.get("phase_id") == phase_id]
    return [s]



def resolve_coverage_dependencies(canonical_tasks: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Resolve Coverage Registry dependencies into TASK_ID lists.

    Production is DAG-only. A valid checklist must provide a Coverage Registry
    with a dependency column. Blank dependency cells mean independent root nodes.
    """
    errors: list[str] = []
    if not canonical_tasks:
        return False, ["Coverage Registry with Slice ID rows is required; DAG-only mode requires registry rows"]
    dag_mode = any(bool(t.get("dependency_column_present")) for t in canonical_tasks)
    if not dag_mode:
        return False, ["Coverage Registry must include a Depends on/Dependencies column; DAG-only mode requires dependency cells"]

    known_ids = {t["id"] for t in canonical_tasks}
    previous_id: str | None = None
    for task in canonical_tasks:
        tid = task["id"]
        deps: list[str] = []
        for ref in _split_dependency_refs(str(task.get("depends_on_raw") or "")):
            ref_key = ref.strip().lower()
            if ref_key in {"previous", "prev", "anterior"}:
                expanded = [previous_id] if previous_id else []
                if not expanded:
                    errors.append(f"{tid}: dependency ref '{ref}' has no previous task")
            else:
                expanded = _expand_slice_ref(ref, canonical_tasks)
                if not expanded:
                    errors.append(f"{tid}: dependency ref '{ref}' resolved to no tasks")
            for dep in expanded:
                if not dep:
                    continue
                if dep == tid:
                    errors.append(f"{tid}: self dependency is not allowed")
                    continue
                if dep not in known_ids:
                    errors.append(f"{tid}: dependency '{dep}' is not a known Coverage Registry task")
                    continue
                if dep not in deps:
                    deps.append(dep)
        task["depends_on"] = deps
        task["dependency_mode"] = "explicit_dag"
        previous_id = tid
    return True, errors


def build_task_dag(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive graph metadata, including adjacency matrix, from task deps."""
    nodes = [str(t.get("id")) for t in tasks if t.get("id")]
    node_set = set(nodes)
    index = {tid: i for i, tid in enumerate(nodes)}
    task_by_id = {str(t.get("id")): t for t in tasks if t.get("id")}
    errors: list[str] = []
    deps_by_node: dict[str, list[str]] = {}
    reverse: dict[str, list[str]] = {tid: [] for tid in nodes}
    adjacency: dict[str, list[str]] = {tid: [] for tid in nodes}
    matrix = [[0 for _ in nodes] for _ in nodes]

    for tid in nodes:
        raw_deps = list(task_by_id[tid].get("depends_on") or [])
        deps: list[str] = []
        for dep in raw_deps:
            dep = str(dep)
            if dep == tid:
                errors.append(f"{tid}: self dependency is not allowed")
                continue
            if dep not in node_set:
                errors.append(f"{tid}: dependency '{dep}' is not a known task")
                continue
            if dep not in deps:
                deps.append(dep)
                adjacency[dep].append(tid)
                reverse[tid].append(dep)
                matrix[index[dep]][index[tid]] = 1
        deps_by_node[tid] = deps

    done: set[str] = set()
    remaining: set[str] = set(nodes)
    levels: list[list[str]] = []
    while remaining:
        level = [tid for tid in nodes if tid in remaining and all(dep in done for dep in deps_by_node.get(tid, []))]
        if not level:
            errors.append("cycle detected or unresolved dependency chain: " + ", ".join(sorted(remaining)))
            break
        levels.append(level)
        done.update(level)
        remaining.difference_update(level)

    mode = "explicit_dag"
    source_projection = [
        {
            "id": tid,
            "depends_on": deps_by_node.get(tid, []),
            "conflict_groups": list(task_by_id[tid].get("conflict_groups") or []),
            "write_set": list(task_by_id[tid].get("write_set") or []),
            "risk_level": task_by_id[tid].get("risk_level") or "medium",
            "verify_mode": task_by_id[tid].get("verify_mode") or "human",
        }
        for tid in nodes
    ]
    source_digest = __import__("hashlib").sha256(json.dumps(source_projection, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "mode": mode,
        "nodes": nodes,
        "edges": [[dep, tid] for tid in nodes for dep in deps_by_node.get(tid, [])],
        "adjacency_index": index,
        "adjacency_matrix": matrix,
        "adjacency_list": adjacency,
        "reverse_dependencies": reverse,
        "topological_levels": levels,
        "conflict_groups": {tid: list(task_by_id[tid].get("conflict_groups") or []) for tid in nodes},
        "write_set": {tid: list(task_by_id[tid].get("write_set") or []) for tid in nodes},
        "risk_level": {tid: task_by_id[tid].get("risk_level") or "medium" for tid in nodes},
        "verify_mode": {tid: task_by_id[tid].get("verify_mode") or "human" for tid in nodes},
        "canonical_source": "registry.tasks",
        "source_digest": source_digest,
        "errors": errors,
    }


def render_task_dag_markdown(task_dag: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    task_by_id = {t.get("id"): t for t in tasks}
    lines = [
        "# Task DAG",
        "",
        "> DERIVED artifact. Do not edit manually. Source of truth: Coverage Registry `Depends on` column.",
        "",
        f"- Mode: `{task_dag.get('mode')}`",
        f"- Nodes: {len(task_dag.get('nodes') or [])}",
        f"- Edges: {len(task_dag.get('edges') or [])}",
        "",
        "## Parallel waves",
        "",
    ]
    for i, level in enumerate(task_dag.get("topological_levels") or [], start=1):
        lines.append(f"### Wave {i}")
        lines.append("")
        for tid in level:
            task = task_by_id.get(tid, {})
            title = task.get("title") or tid
            deps = ", ".join(task.get("depends_on") or []) or "—"
            groups = ", ".join(task.get("conflict_groups") or []) or "—"
            writes = ", ".join(task.get("write_set") or []) or "—"
            risk = task.get("risk_level") or "medium"
            verify_mode = task.get("verify_mode") or "human"
            lines.append(f"- `{tid}` — {title} _(depends_on: {deps}; conflict_groups: {groups}; write_set: {writes}; risk: {risk}; verify_mode: {verify_mode})_")
        lines.append("")
    if task_dag.get("errors"):
        lines.append("## Errors")
        lines.append("")
        for err in task_dag["errors"]:
            lines.append(f"- {err}")
        lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("Rows are source nodes, columns are destination nodes; `1` means row -> column.")
    lines.append("")
    nodes = task_dag.get("nodes") or []
    matrix = task_dag.get("adjacency_matrix") or []
    if nodes:
        lines.append("| from \\ to | " + " | ".join(nodes) + " |")
        lines.append("|---" + "|---" * len(nodes) + "|")
        for node, row in zip(nodes, matrix):
            lines.append("| " + node + " | " + " | ".join(str(x) for x in row) + " |")
    else:
        lines.append("(no tasks)")
    lines.append("")
    return "\n".join(lines)


def _serializable_doc_paths(doc_paths: dict[str, list[Path]]) -> dict[str, list[str]]:
    """Return source-doc paths as strings for JSON CLI output.

    ``generate_artifacts()`` can fail before artifacts are written; in that
    path the CLI must still be able to print ``--json`` diagnostics instead of
    trying to serialize raw ``Path`` objects.
    """
    return {k: [relpath(p) for p in v] for k, v in doc_paths.items()}

def validate_docs(doc_paths: dict[str, list[Path]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in ("instructions", "checklist", "guide"):
        if len(doc_paths[key]) != 1:
            errors.append(f"Expected exactly one {key} document, found {len(doc_paths[key])}.")
    # Production DAG-only source-of-truth contract:
    # instrucciones.md + technical guide + implementation checklist + UX_CONTRACT.md
    # + STACK_PROFILE.yaml. A clean engine template may have an empty folder; any
    # active app must provide the full five-file pack. Extra files are rejected
    # because they can make the bootstrap build the wrong product.
    sot = canonical_source_docs_dir()
    if sot.exists():
        active_md = sorted(p for p in sot.glob("*.md") if p.is_file())
        allowed_md = {"instrucciones.md", "UX_CONTRACT.md"}
        allowed_md.update(p.name for p in active_md if p.name.endswith("_TECHNICAL_GUIDE.md") or p.name.endswith("_IMPLEMENTATION_CHECKLIST.md"))
        extra_md = [p.name for p in active_md if p.name not in allowed_md]
        if extra_md:
            errors.append("source-of-truth contains unexpected markdown files: " + ", ".join(extra_md))
        stack_profiles = sorted(p for p in sot.glob("STACK_PROFILE.yaml") if p.is_file())
        if active_md or stack_profiles:
            if len(active_md) != 4:
                errors.append(
                    "source-of-truth expected exactly 4 active markdown docs "
                    "(instrucciones.md, *_TECHNICAL_GUIDE.md, *_IMPLEMENTATION_CHECKLIST.md, UX_CONTRACT.md) "
                    f"or 0 in the clean template, found {len(active_md)}: "
                    + ", ".join(p.name for p in active_md)
                )
            if len(stack_profiles) != 1:
                errors.append("source-of-truth expected exactly one STACK_PROFILE.yaml, found " + str(len(stack_profiles)))
    if errors:
        return {"errors": errors, "warnings": warnings}

    instructions = doc_paths["instructions"][0]
    checklist = doc_paths["checklist"][0]
    guide = doc_paths["guide"][0]
    ux_docs = doc_paths.get("ux", [])
    stack_profiles = doc_paths.get("stack_profile", [])
    if len(ux_docs) > 1:
        errors.append(f"Expected at most one UX_CONTRACT.md, found {len(ux_docs)}.")
    if len(stack_profiles) > 1:
        errors.append(f"Expected at most one STACK_PROFILE.yaml, found {len(stack_profiles)}.")
    if len(ux_docs) == 0:
        errors.append("UX_CONTRACT.md is required in docs/source-of-truth/.")
    if len(stack_profiles) == 0:
        errors.append("STACK_PROFILE.yaml is required in docs/source-of-truth/.")

    if checklist.stem.replace("_IMPLEMENTATION_CHECKLIST", "") != guide.stem.replace("_TECHNICAL_GUIDE", ""):
        errors.append("Checklist and technical guide do not share the same prefix.")

    instructions_text = read_text(instructions)
    checklist_text = read_text(checklist)
    guide_text = read_text(guide)
    ux_text = read_text(ux_docs[0]) if ux_docs else ""

    coverage_rows = parse_coverage_registry(checklist_text)
    if not coverage_rows:
        errors.append("Coverage Registry table with explicit TASK_ID rows is required for DAG-only bootstrap.")
    else:
        dag_mode_ok, dag_errors = resolve_coverage_dependencies(coverage_rows)
        if not dag_mode_ok:
            errors.append("Coverage Registry must include and fill a dependency column such as `Depends on`.")
        errors.extend(dag_errors)

    for label, text in (
        ("instrucciones.md", instructions_text),
        ("technical guide", guide_text),
        ("implementation checklist", checklist_text),
        ("UX_CONTRACT.md", ux_text),
    ):
        if not text:
            continue
        if UNFILLED_TEMPLATE_MARKERS_RE.search(text):
            errors.append(f"{label} still contains template markers (>>> MODELO: or 📋 SI APLICA). Fill it before bootstrap.")

    if len(extract_headings(instructions_text)) < 1:
        errors.append("instrucciones.md has no markdown headings.")
    if len(extract_headings(guide_text)) < 2:
        errors.append("technical guide has too few markdown headings.")
    checklist_headings = extract_headings(checklist_text)
    if len(checklist_headings) < 2:
        errors.append("implementation checklist has too few markdown headings.")
    phase_count = len(phase_headings(checklist_headings))
    if phase_count < 1:
        errors.append("implementation checklist does not expose phase headings.")
    if phase_count < 2:
        warnings.append("Only one phase was detected in the implementation checklist.")
    if len(instructions_text.strip()) < 200:
        warnings.append("instrucciones.md is unusually short.")
    if len(guide_text.strip()) < 500:
        warnings.append("technical guide is unusually short.")
    if len(checklist_text.strip()) < 300:
        warnings.append("implementation checklist is unusually short.")
    if ux_text and len(extract_headings(ux_text)) < 2:
        warnings.append("UX_CONTRACT.md has too few markdown headings.")
    if stack_profiles:
        try:
            profile = load_stack_profile(project_root())
            for key in ("frontend", "backend", "db"):
                if not isinstance(profile.get(key), dict):
                    errors.append(f"STACK_PROFILE.yaml missing object section: {key}")
            if not profile.get("design_tokens_enforcer"):
                errors.append("STACK_PROFILE.yaml missing design_tokens_enforcer")
            if not profile.get("git_workflow"):
                errors.append("STACK_PROFILE.yaml missing git_workflow")
        except Exception as exc:
            errors.append(f"STACK_PROFILE.yaml could not be parsed: {type(exc).__name__}: {exc}")
    if not docs_are_in_canonical_dir(doc_paths):
        errors.append("Source-of-truth files must live in docs/source-of-truth/ for DAG-only projects")
    return {"errors": errors, "warnings": warnings}


def extract_sections(text: str, headings: list[dict[str, Any]], phase_heading: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], int | None]:
    lines = text.splitlines()
    end_line = None
    for h in headings:
        if h["line"] > phase_heading["line"] and h["level"] <= phase_heading["level"] and PHASE_KEYWORD_RE.search(h["title"]):
            end_line = h["line"]
            break
    section_lines = lines[phase_heading["line"] - 1 : end_line - 1 if end_line else len(lines)]
    child_headings = [
        h for h in headings
        if h["line"] > phase_heading["line"]
        and (end_line is None or h["line"] < end_line)
        and h["level"] > phase_heading["level"]
    ]
    return section_lines, child_headings, end_line


def build_phases_and_tasks(checklist_path: Path, checklist_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build phases and tasks from the canonical Coverage Registry.

    Production is DAG-only: Coverage Registry rows are the authoritative TASK_ID
    source and the dependency column is the source-of-truth adjacency list.
    Body step sections are used only to enrich acceptance and verification text.
    """
    headings = extract_headings(checklist_text)
    phases_raw = phase_headings(headings)
    canonical_tasks = parse_coverage_registry(checklist_text)
    dag_mode, dag_errors = resolve_coverage_dependencies(canonical_tasks)
    canonical_index: dict[str, dict[str, Any]] = {t["id"]: t for t in canonical_tasks}
    canonical_by_phase: dict[str, list[dict[str, Any]]] = {}
    for ct in canonical_tasks:
        canonical_by_phase.setdefault(ct["phase_id"], []).append(ct)

    phases: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    # Coarse warnings list also receives unrecognized-registry warnings — both
    # surface to the user via the validation block, alongside the existing
    # synthetic-coarseness alerts. Detection runs once per bootstrap.
    coarse_warnings: list[str] = list(
        detect_unrecognized_coverage_registries(checklist_text)
    )
    previous_phase_last_task_id = None

    for p_idx, phase_heading in enumerate(phases_raw, start=1):
        section_lines, child_headings, end_line = extract_sections(checklist_text, headings, phase_heading)
        m = PHASE_RE.search(phase_heading["title"])
        raw_number = m.group(1) if m and m.group(1) else str(p_idx)
        major = raw_number.split(".")[0]
        try:
            phase_number = int(major)
        except (TypeError, ValueError):
            phase_number = p_idx
        phase_title_suffix = (m.group(2) if m else phase_heading["title"]).strip() or phase_heading["title"]
        phase_id = f"P{phase_number:02d}"
        phase = {
            "id": phase_id,
            "phase_number": phase_number,
            "title": phase_title_suffix,
            "status": "ready" if p_idx == 1 else "blocked",
            "depends_on": [] if p_idx == 1 else [phases[-1]["id"]],
            "source_ref": f"{relpath(checklist_path)}#{phase_heading['title']}",
            "task_ids": [],
        }

        # Fix B2: only keep `## Step N.M` headings under the phase. PRE-GATE,
        # PHASE GATE, "canonical slices" matrix, and emoji meta-headings are
        # filtered out so they never become tasks and never shift the step
        # numbering.
        all_step_headings = [h for h in child_headings
                             if h["level"] == min((x["level"] for x in child_headings), default=phase_heading["level"] + 1)]
        step_headings = _step_headings_only(all_step_headings)

        phase_line_end = end_line if end_line else len(checklist_text.splitlines()) + 1
        last_task_id = previous_phase_last_task_id

        registry_tasks_for_phase = canonical_by_phase.get(phase_id, [])

        if registry_tasks_for_phase:
            # ----- Registry-driven path (Fix B3, refined) -----------------
            # Walk the Step headings in DOCUMENT ORDER. For each step:
            #   * if any canonical task's step_ref matches -> emit those
            #     (registry IDs are authoritative);
            #   * otherwise emit ONE synthetic task per step, with its
            #     body bullets as acceptance — so internal scaffolding work
            #     (Step 2.1 "estructura", Step 2.3 "config service", etc.)
            #     isn't silently dropped. The synthetic step_id is derived
            #     from "Step N.M" -> "Pnn-S{M:02d}" to line up with the
            #     registry's own step_id convention.
            covered_canonical_ids: set[str] = set()

            def _emit_canonical(canonical: dict[str, Any], step_heading: dict[str, Any] | None,
                                last_id: str | None) -> str:
                tid = canonical["id"]
                step_id = canonical["step_id"]
                acceptance: list[str] = list(canonical.get("acceptance") or [])
                source_step_title = canonical.get("step_ref") or step_id
                if step_heading is not None:
                    source_step_title = step_heading["title"]
                if not acceptance:
                    acceptance = [canonical.get("title") or tid]
                deps = list(canonical.get("depends_on") or []) if dag_mode else ([last_id] if last_id else [])
                default_status = "ready" if not deps else "blocked"
                status = _status_from_build_state(canonical.get("build_state_raw") or canonical.get("build_state") or "", default_status)
                task_record = {
                    "id": tid, "phase_id": phase_id, "step_id": step_id,
                    "title": canonical.get("title") or tid,
                    "status": status,
                    "build_state": canonical.get("build_state") or "planned",
                    "product_increment": canonical.get("product_increment") or "unspecified",
                    "risk_level": canonical.get("risk_level") or "medium",
                    "verify_mode": canonical.get("verify_mode") or "human",
                    "depends_on": deps,
                    "source_ref": f"{relpath(checklist_path)}#{source_step_title}",
                    "acceptance": acceptance,
                    "verification_commands": list(canonical.get("verification_commands", [])),
                    "kind": canonical.get("kind") or "unspecified",
                    "target": canonical.get("target") or "",
                    "journey_refs": list(canonical.get("journey_refs") or []),
                    "route": canonical.get("route") or "",
                    "endpoint": canonical.get("endpoint") or "",
                    "tables": list(canonical.get("tables") or []),
                    "origin_instr": canonical.get("origin_instr") or "",
                    "origin_techguide": canonical.get("origin_techguide") or "",
                    "allowed_paths": list(canonical.get("write_set") or []),
                    "conflict_groups": list(canonical.get("conflict_groups") or []),
                    "write_set": list(canonical.get("write_set") or []),
                    "delete_set": list(canonical.get("delete_set") or []),
                    "handoff_path": f"orchestrator-state/tasks/handoffs/{tid}.md",
                    "evidence_dir": f"orchestrator-state/tasks/evidence/{tid}",
                    "notes": [],
                }
                if dag_mode:
                    task_record["dependency_mode"] = "explicit_dag"
                    task_record["depends_on_raw"] = canonical.get("depends_on_raw", "")
                    task_record["conflict_groups_raw"] = canonical.get("conflict_groups_raw", "")
                    task_record["write_set_raw"] = canonical.get("write_set_raw", "")
                    task_record["delete_set_raw"] = canonical.get("delete_set_raw", "")
                    task_record["product_increment_raw"] = canonical.get("product_increment_raw", "")
                    task_record["build_state_raw"] = canonical.get("build_state_raw", "")
                    task_record["risk_level_raw"] = canonical.get("risk_level_raw", "")
                    task_record["verify_mode_raw"] = canonical.get("verify_mode_raw", "")
                    task_record["kind_raw"] = canonical.get("kind_raw", "")
                    task_record["target_raw"] = canonical.get("target_raw", "")
                    task_record["journey_refs_raw"] = canonical.get("journey_refs_raw", "")
                    task_record["screen_route_raw"] = canonical.get("screen_route_raw", "")
                    task_record["endpoint_raw"] = canonical.get("endpoint_raw", "")
                    task_record["tables_raw"] = canonical.get("tables_raw", "")
                    task_record["origin_instr_raw"] = canonical.get("origin_instr_raw", "")
                    task_record["origin_techguide_raw"] = canonical.get("origin_techguide_raw", "")
                tasks.append(task_record)
                phase["task_ids"].append(tid)
                covered_canonical_ids.add(tid)
                return tid

            def _emit_synthetic(step_heading: dict[str, Any], last_id: str | None) -> str:
                # Derive step_id from "Step N.M" -> "Pnn-S{M:02d}".
                m = STEP_HEADING_RE.match(step_heading["title"])
                if m and m.group(2):
                    step_minor = int(m.group(2))
                else:
                    step_minor = 1
                synth_step_id = f"{phase_id}-S{step_minor:02d}"
                body = _step_section_lines(checklist_text, headings, step_heading, phase_line_end)

                # Look for sub-headings INSIDE the step body. A sub-heading is
                # any heading whose level is deeper than the step heading
                # itself. The author put them there as natural sub-task
                # boundaries — we honour that as the split point.
                body_text = "\n".join(body)
                sub_headings = [h for h in extract_headings(body_text)
                                if h["level"] > step_heading["level"]]

                def _emit_one(suffix_idx: int, title: str, acceptance_lines: list[str],
                              last_id_inner: str | None) -> str:
                    tid_inner = f"{synth_step_id}-T{suffix_idx:03d}"
                    acceptance_inner = extract_items(acceptance_lines) or [title]
                    note = (
                        "synthetic — step has no Coverage Registry entry; "
                        "one task per sub-heading"
                        if len(sub_headings) >= 2
                        else "synthetic — step has no Coverage Registry entry; one task per step heading"
                    )
                    notes_inner = [note]
                    if len(acceptance_inner) > SYNTHETIC_COARSE_THRESHOLD:
                        warn = (
                            f"synthetic task {tid_inner} has {len(acceptance_inner)} "
                            f"acceptance items (>{SYNTHETIC_COARSE_THRESHOLD}). The slice is "
                            f"likely too coarse for the 20-spawn pipeline. Either add "
                            f"canonical Slice IDs in the Coverage Registry, or add ### "
                            f"sub-headings inside the step body to drive a split."
                        )
                        notes_inner.append(f"WARN: {warn}")
                        coarse_warnings.append(warn)
                    tasks.append({
                        "id": tid_inner, "phase_id": phase_id, "step_id": synth_step_id,
                        "title": title,
                        "status": "ready" if not last_id_inner else "blocked",
                        "depends_on": [last_id_inner] if last_id_inner else [],
                        "source_ref": f"{relpath(checklist_path)}#{title}",
                        "acceptance": acceptance_inner,
                        "verification_commands": [],
                        "risk_level": "medium",
                        "verify_mode": "human",
                        "allowed_paths": [],
                        "conflict_groups": [],
                        "write_set": [],
                        "handoff_path": f"orchestrator-state/tasks/handoffs/{tid_inner}.md",
                        "evidence_dir": f"orchestrator-state/tasks/evidence/{tid_inner}",
                        "notes": notes_inner,
                    })
                    phase["task_ids"].append(tid_inner)
                    return tid_inner

                if len(sub_headings) >= 2:
                    # Multi-task split: each sub-heading becomes its own task.
                    body_lines_array = body  # Already a list of lines.
                    last_emitted = last_id
                    suffix = 1
                    # Optional preamble: bullets BEFORE the first sub-heading.
                    first_sub_line = sub_headings[0]["line"]
                    preamble = body_lines_array[: max(0, first_sub_line - 1)]
                    if extract_items(preamble):
                        last_emitted = _emit_one(suffix, step_heading["title"],
                                                 preamble, last_emitted)
                        suffix += 1
                    # One task per sub-heading.
                    for i, sub in enumerate(sub_headings):
                        start_line = sub["line"]
                        end_line = sub_headings[i + 1]["line"] if i + 1 < len(sub_headings) else len(body_lines_array) + 1
                        chunk = body_lines_array[start_line - 1 : max(0, end_line - 1)]
                        last_emitted = _emit_one(suffix, sub["title"], chunk, last_emitted)
                        suffix += 1
                    return last_emitted
                else:
                    # Single-task fallback (the common case).
                    return _emit_one(1, step_heading["title"], body, last_id)

            # Walk step headings in document order and emit accordingly.
            for step_heading in step_headings:
                step_text = step_heading["title"]
                m = STEP_HEADING_RE.match(step_text)
                step_label = None
                if m:
                    if m.group(2):
                        step_label = f"Step {m.group(1)}.{m.group(2)}"
                    else:
                        step_label = f"Step {m.group(1)}"
                # Match a canonical iff its step_ref contains EXACTLY the
                # step_label (with a (?!\d) right-boundary so 'Step 2.1'
                # doesn't match 'Step 2.10' or 'Step 2.11').
                matched: list[dict[str, Any]] = []
                if step_label:
                    label_pat = re.compile(re.escape(step_label) + r"(?!\d)", re.IGNORECASE)
                    matched = [c for c in registry_tasks_for_phase
                               if c["id"] not in covered_canonical_ids
                               and label_pat.search(c.get("step_ref", ""))]
                if matched:
                    for canonical in matched:
                        last_task_id = _emit_canonical(canonical, step_heading, last_task_id)
                else:
                    coarse_warnings.append(f"{phase_id}: step '{step_heading['title']}' has no Coverage Registry row; DAG-only bootstrap emits no synthetic task")

            # Any canonical tasks whose step_ref didn't match a body heading
            # (rare — usually a typo in the registry) still need to be
            # emitted so they're reachable. They go at the end of the phase.
            for canonical in registry_tasks_for_phase:
                if canonical["id"] in covered_canonical_ids:
                    continue
                last_task_id = _emit_canonical(canonical, None, last_task_id)
        else:
            coarse_warnings.append(f"{phase_id}: phase has no Coverage Registry rows; DAG-only bootstrap emits no synthetic tasks")

        previous_phase_last_task_id = last_task_id
        phases.append(phase)

    # Incremental/vN support: runtime follow-ups or future product increments may
    # append canonical Coverage Registry rows for a new phase (for example P06)
    # without adding a full Phase heading yet. Those rows are still source of
    # truth and must become executable DAG tasks. Emit a synthetic phase wrapper
    # rather than silently dropping them. The row-level Depends on / Build state
    # cells remain authoritative.
    emitted_phase_ids = {p.get("id") for p in phases}

    def _phase_sort_key(pid: str) -> tuple[int, str]:
        m = re.match(r"^P(\d+)", str(pid or ""))
        return (int(m.group(1)) if m else 9999, str(pid or ""))

    for phase_id in sorted(canonical_by_phase.keys(), key=_phase_sort_key):
        if phase_id in emitted_phase_ids:
            continue
        try:
            phase_number = int(str(phase_id).lstrip("P"))
        except Exception:
            phase_number = len(phases)
        phase = {
            "id": phase_id,
            "phase_number": phase_number,
            "title": f"Incremental/runtime coverage {phase_id}",
            "status": "blocked",
            "depends_on": [phases[-1]["id"]] if phases else [],
            "source_ref": f"{relpath(checklist_path)}#Runtime Follow-up Coverage Registry",
            "task_ids": [],
            "notes": ["synthetic phase wrapper — canonical rows exist without a Phase heading"],
        }
        last_task_id = previous_phase_last_task_id
        for canonical in canonical_by_phase.get(phase_id, []):
            tid = canonical["id"]
            deps = list(canonical.get("depends_on") or []) if dag_mode else ([last_task_id] if last_task_id else [])
            default_status = "ready" if not deps else "blocked"
            status = _status_from_build_state(canonical.get("build_state_raw") or canonical.get("build_state") or "", default_status)
            task_record = {
                "id": tid,
                "phase_id": phase_id,
                "step_id": canonical.get("step_id") or phase_id,
                "title": canonical.get("title") or tid,
                "status": status,
                "build_state": canonical.get("build_state") or "planned",
                "product_increment": canonical.get("product_increment") or "unspecified",
                "risk_level": canonical.get("risk_level") or "medium",
                "verify_mode": canonical.get("verify_mode") or "human",
                "depends_on": deps,
                "source_ref": f"{relpath(checklist_path)}#{canonical.get('step_ref') or 'Runtime Follow-up Coverage Registry'}",
                "acceptance": list(canonical.get("acceptance") or [canonical.get("title") or tid]),
                "verification_commands": list(canonical.get("verification_commands") or []),
                "kind": canonical.get("kind") or "unspecified",
                "target": canonical.get("target") or "",
                "journey_refs": list(canonical.get("journey_refs") or []),
                "route": canonical.get("route") or "",
                "endpoint": canonical.get("endpoint") or "",
                "tables": list(canonical.get("tables") or []),
                "origin_instr": canonical.get("origin_instr") or "",
                "origin_techguide": canonical.get("origin_techguide") or "",
                "allowed_paths": list(canonical.get("write_set") or []),
                "conflict_groups": list(canonical.get("conflict_groups") or []),
                "write_set": list(canonical.get("write_set") or []),
                "handoff_path": f"orchestrator-state/tasks/handoffs/{tid}.md",
                "evidence_dir": f"orchestrator-state/tasks/evidence/{tid}",
                "notes": ["registry-only phase task — emitted from cumulative source-of-truth"],
            }
            if dag_mode:
                task_record["dependency_mode"] = "explicit_dag"
                task_record["depends_on_raw"] = canonical.get("depends_on_raw", "")
                task_record["conflict_groups_raw"] = canonical.get("conflict_groups_raw", "")
                task_record["write_set_raw"] = canonical.get("write_set_raw", "")
                task_record["product_increment_raw"] = canonical.get("product_increment_raw", "")
                task_record["build_state_raw"] = canonical.get("build_state_raw", "")
                task_record["risk_level_raw"] = canonical.get("risk_level_raw", "")
                task_record["verify_mode_raw"] = canonical.get("verify_mode_raw", "")
            tasks.append(task_record)
            phase["task_ids"].append(tid)
            last_task_id = tid
        previous_phase_last_task_id = last_task_id
        phases.append(phase)
        emitted_phase_ids.add(phase_id)

    # Body-only task generation safety for invalid docs; valid DAG docs derive readiness from dependency cells.
    if not dag_mode and tasks and tasks[0]["status"] != "ready":
        tasks[0]["status"] = "ready"
        tasks[0]["depends_on"] = []

    # Attach coarse-synthetic/DAG validation warnings to the phases container as a
    # side-channel — tuple is unchanged for back-compat with callers, but
    # the function-level closure exposes them via the `coarse_warnings`
    # attribute on the first phase (read by generate_artifacts).
    # If the Coverage Registry declares already-built baseline rows, keep
    # phase lifecycle coherent. This lets cumulative existing baseline + v1 + v2 source
    # docs avoid rebuilding old increments while preserving journeys, UX and
    # wiring context.
    task_by_id = {t.get("id"): t for t in tasks}
    for phase in phases:
        phase_tasks = [task_by_id.get(tid) for tid in phase.get("task_ids", [])]
        phase_tasks = [t for t in phase_tasks if t]
        if phase_tasks and all(t.get("status") == "done" for t in phase_tasks):
            phase["status"] = "complete"
        elif any(t.get("status") in {"ready", "claimed", "in_progress", "validator_tester_pending", "ready_for_close", "verified_pending_close"} for t in phase_tasks):
            phase["status"] = "ready"

    if phases:
        phases[0].setdefault("_coarse_warnings", coarse_warnings)
        phases[0].setdefault("_dag_errors", dag_errors)
    return phases, tasks


def build_project_brief(instructions_path: Path, checklist_path: Path, guide_path: Path, instructions_text: str, validation: dict[str, Any]) -> str:
    headings = extract_headings(instructions_text)[:20]
    lines = [
        "# Project brief",
        "",
        f"- Generated at: {now_iso()}",
        f"- Canonical source-of-truth dir: `{relpath(canonical_source_docs_dir())}`",
        f"- Discovery mode: {'canonical' if docs_are_in_canonical_dir({'instructions': [instructions_path], 'checklist': [checklist_path], 'guide': [guide_path]}) else 'invalid-noncanonical'}",
        f"- Instructions: `{relpath(instructions_path)}`",
        f"- Checklist: `{relpath(checklist_path)}`",
        f"- Technical guide: `{relpath(guide_path)}`",
        "",
        "## Top-level headings from instrucciones.md",
    ]
    for h in headings:
        lines.append(f"- H{h['level']}: {h['title']}")
    lines.extend([
        "",
        "## Validation summary",
    ])
    if validation["errors"]:
        lines.extend([f"- ERROR: {e}" for e in validation["errors"]])
    else:
        lines.append("- No blocking validation errors detected.")
    if validation["warnings"]:
        lines.extend([f"- WARNING: {w}" for w in validation["warnings"]])
    return "\n".join(lines) + "\n"


def build_architecture_contract(guide_path: Path, guide_text: str) -> str:
    headings = extract_headings(guide_text)[:40]
    constraint_lines: list[str] = []
    for line in guide_text.splitlines():
        if CONSTRAINT_RE.search(line.strip()):
            cleaned = line.strip()
            if cleaned and len(cleaned) < 240:
                constraint_lines.append(cleaned)
        if len(constraint_lines) >= 30:
            break

    lines = [
        "# Architecture contract",
        "",
        f"- Generated at: {now_iso()}",
        f"- Source: `{relpath(guide_path)}`",
        "",
        "## Structural headings",
    ]
    for h in headings:
        lines.append(f"- H{h['level']}: {h['title']}")
    lines.extend([
        "",
        "## Constraint and invariant signals",
    ])
    if constraint_lines:
        for line in constraint_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- No explicit constraint signal lines were extracted automatically.")
    lines.extend([
        "",
        "## Operating note",
        "This file is derived. Use it as an execution contract, but reconcile against the raw guide when ambiguity matters.",
    ])
    return "\n".join(lines) + "\n"


def build_manifest(instructions_path: Path, checklist_path: Path, guide_path: Path, validation: dict[str, Any], ux_path: Path | None = None, stack_profile_path: Path | None = None) -> dict[str, Any]:
    prefix = checklist_path.stem.replace("_IMPLEMENTATION_CHECKLIST", "")
    documents = {
        "instructions": {"path": relpath(instructions_path), "sha256": sha256_file(instructions_path)},
        "checklist": {"path": relpath(checklist_path), "sha256": sha256_file(checklist_path)},
        "guide": {"path": relpath(guide_path), "sha256": sha256_file(guide_path)},
    }
    if ux_path:
        documents["ux_contract"] = {"path": relpath(ux_path), "sha256": sha256_file(ux_path)}
    if stack_profile_path:
        documents["stack_profile"] = {"path": relpath(stack_profile_path), "sha256": sha256_file(stack_profile_path)}
    return {
        "generated_at": now_iso(),
        "project_root": relpath(project_root()),
        "project_prefix": prefix,
        "source_of_truth": {
            "canonical_dir": relpath(canonical_source_docs_dir()),
            "discovery_mode": "canonical-strict" if docs_are_in_canonical_dir({"instructions": [instructions_path], "checklist": [checklist_path], "guide": [guide_path]}) else "invalid",
            "contract_version": "five-file-source-of-truth",
        },
        "documents": documents,
        "validation": validation,
    }



_REQUIRED_JOURNEY_HEADERS = ["id", "milestone", "screens", "actions", "endpoints", "tables", "client_state", "slices", "verification"]


def _normalise_journey_header(value: str) -> str:
    key = _normalize_header_alias(value)
    aliases = {
        "id": "id", "journey id": "id", "jid": "id", "journey": "id",
        "milestone": "milestone", "hito": "milestone", "m": "milestone",
        "p": "screens", "pantallas": "screens", "pantallas (en orden)": "screens", "screens": "screens", "screens (ordered)": "screens",
        "a": "actions", "acciones": "actions", "acciones clave": "actions", "actions": "actions", "key actions": "actions",
        "ep": "endpoints", "endpoints": "endpoints", "endpoint": "endpoints",
        "t": "tables", "tablas db": "tables", "tablas": "tables", "tables": "tables", "db tables": "tables",
        "s": "client_state", "estado": "client_state", "estado cliente": "client_state", "estado cliente/provider": "client_state", "client state": "client_state", "providers": "client_state",
        "slices": "slices", "slice refs": "slices", "task ids": "slices", "tasks": "slices",
        "v": "verification", "verif": "verification", "verificación": "verification", "verificacion": "verification", "verification": "verification", "verify": "verification",
    }

    if key in aliases:
        return aliases[key]
    for part in re.split(r"[/\(\)]", key):
        part = part.strip()
        if part in aliases:
            return aliases[part]
    return key

def _extract_journey_rows_by_header(section_lines: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    sep_re = re.compile(r"^\|[\s:\-|]+\|?\s*$")
    for i, line in enumerate(section_lines):
        if not line.lstrip().startswith("|"):
            continue
        headers = [_normalise_journey_header(h) for h in _split_md_table_row(line)]
        if "id" not in headers:
            continue
        missing = [h for h in _REQUIRED_JOURNEY_HEADERS if h not in headers]
        if missing:
            return [], ["Journey Coverage Matrix missing required header(s): " + ", ".join(missing)]
        if i + 1 >= len(section_lines) or not sep_re.match(section_lines[i + 1]):
            return [], ["Journey Coverage Matrix header is not followed by a markdown separator row"]
        rows: list[dict[str, str]] = []
        j = i + 2
        while j < len(section_lines) and section_lines[j].lstrip().startswith("|"):
            cells = _split_md_table_row(section_lines[j])
            if cells and not all(re.fullmatch(r"[:\-\s]+", c or "") for c in cells):
                row = {h: _strip_md_inline(cells[idx]) if idx < len(cells) else "" for idx, h in enumerate(headers)}
                if re.match(r"^J\d+$", row.get("id", "")):
                    rows.append(row)
            j += 1
        return rows, errors
    return [], errors

def extract_journey_matrix(
    instructions_text: str,
    all_tasks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Parse the §3.5 Journey Coverage Matrix from instrucciones.md.

    Returns a list of journey dicts ready to embed in registry.json under the
    'journeys' key. Returns [] if the section is not present (back-compat for
    pre-matrix projects).

    Each journey dict has:
      - id, milestone, screens, actions, endpoints, tables, client_state,
        task_ids (expanded — see below), verification, title (derived from
        screens), verification_status='pending', verified_at=None,
        verify_handoff path.

    Slice cell expansion (in `task_ids`):
      - Full TASK_ID  ("P00-S05-T001")        → kept as-is.
      - Range         ("P00-S05-T001..T003")  → enumerated.
      - Step ref      ("P00-S05")             → all tasks of that step,
                                                resolved via `all_tasks`.
      - Phase ref     ("P00")                 → all tasks of that phase.
      - Descriptive text                      → kept verbatim. The validator
                                                script flags it later as drift.

    The split is robust to backslash-escaped pipes (`\\|` inside a cell is
    treated as content, not as a column boundary).
    """
    if not instructions_text:
        return []

    all_tasks = all_tasks or []

    headings = extract_headings(instructions_text)
    matrix_heading = None
    for h in headings:
        if JOURNEY_SECTION_RE.search(h["title"]):
            matrix_heading = h
            break
    if not matrix_heading:
        return []

    end_line: int | None = None
    for h in headings:
        if h["line"] > matrix_heading["line"] and h["level"] <= matrix_heading["level"]:
            end_line = h["line"]
            break

    all_lines = instructions_text.splitlines()
    section_lines = all_lines[matrix_heading["line"] - 1 : (end_line - 1 if end_line else len(all_lines))]

    journey_rows, journey_errors = _extract_journey_rows_by_header(section_lines)
    if journey_errors:
        return [{
            "id": "__JOURNEY_MATRIX_PARSE_ERROR__",
            "title": "Journey matrix parse error",
            "errors": journey_errors,
            "verification_status": "invalid",
            "task_ids": [],
        }]

    journeys: list[dict[str, Any]] = []
    for row in journey_rows:
        jid = row.get("id", "")
        milestone = row.get("milestone", "")
        screens_raw = row.get("screens", "")
        actions_raw = row.get("actions", "")
        endpoints_raw = row.get("endpoints", "")
        tables_raw = row.get("tables", "")
        client_state_raw = row.get("client_state", "")
        slices_raw = row.get("slices", "")
        verification = row.get("verification", "")

        screens = [s.strip() for s in re.split(r"[→,]", screens_raw) if s.strip()]
        actions = [s.strip() for s in actions_raw.split(",") if s.strip()]
        endpoints = [s.strip() for s in endpoints_raw.split(",") if s.strip()]
        tables = [s.strip() for s in tables_raw.split(",") if s.strip()]
        client_state = [s.strip() for s in client_state_raw.split(",") if s.strip()]

        task_ids: list[str] = []
        for s_ref in [_strip_md_inline(x) for x in slices_raw.split(",") if _strip_md_inline(x)]:
            for expanded in _expand_slice_ref(s_ref, all_tasks):
                if expanded and expanded not in task_ids:
                    task_ids.append(expanded)

        title_parts = screens[:3] + (["..."] if len(screens) > 3 else [])
        title = " → ".join(title_parts) if title_parts else jid
        journeys.append({
            "id": jid,
            "title": title,
            "milestone": milestone,
            "screens": screens,
            "actions": actions,
            "endpoints": endpoints,
            "tables": tables,
            "client_state": client_state,
            "task_ids": task_ids,
            "task_ids_source_order": list(task_ids),
            "slices_raw": slices_raw,
            "verification": verification,
            "verification_status": "pending",
            "verified_at": None,
            "verify_handoff": f"orchestrator-state/tasks/journey-handoffs/{jid}.md",
            "pending_reason": "not_all_tasks_done",
            "completion_policy": "all_task_ids_done",
            "task_order_policy": "dag_topological_order",
        })

    return journeys


def enrich_journey_completion_metadata(
    journeys: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    task_dag: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normalize journey task order and add DAG completion metadata.

    The Journey Matrix is authored for humans and may use ranges, step refs or
    manual lists. Runtime must not rely on cell order. This pass sorts valid
    TASK_IDs by the derived DAG topological order and computes the terminal
    frontier for each journey, so phase-gate and closer can decide journey
    completion without using ``task_ids[-1]``.
    """
    node_order = {tid: i for i, tid in enumerate(task_dag.get("nodes") or [])}
    task_by_id = {str(t.get("id")): t for t in tasks if t.get("id")}
    adjacency = task_dag.get("adjacency_list") or {}

    for journey in journeys:
        original = [str(t) for t in (journey.get("task_ids") or []) if t]
        valid = [tid for tid in original if tid in task_by_id]
        invalid = [tid for tid in original if tid not in task_by_id]
        valid_sorted: list[str] = []
        for tid in sorted(valid, key=lambda x: (node_order.get(x, 10**9), x)):
            if tid not in valid_sorted:
                valid_sorted.append(tid)
        journey["task_ids_source_order"] = original
        journey["task_ids"] = valid_sorted + invalid

        task_set = set(valid_sorted)
        terminal: list[str] = []
        for tid in valid_sorted:
            successors = [str(s) for s in (adjacency.get(tid) or [])]
            if not any(s in task_set for s in successors):
                terminal.append(tid)
        journey["terminal_task_ids"] = terminal or (valid_sorted[-1:] if valid_sorted else [])
        journey["completion_policy"] = "all_task_ids_done"
        journey["task_order_policy"] = "dag_topological_order" if valid_sorted else "source_order_unresolved"
    return journeys


def write_phase_yaml(path: Path, phase: dict[str, Any]) -> None:
    lines = [
        f"id: {phase['id']}",
        f"title: {json.dumps(phase['title'], ensure_ascii=False)}",
        f"status: {phase['status']}",
        "depends_on:",
    ]
    for dep in phase.get("depends_on", []):
        lines.append(f"  - {dep}")
    lines.append("task_ids:")
    for tid in phase.get("task_ids", []):
        lines.append(f"  - {tid}")
    lines.append(f"source_ref: {json.dumps(phase['source_ref'], ensure_ascii=False)}")
    write_text(path, "\n".join(lines) + "\n")


def write_task_yaml(path: Path, task: dict[str, Any]) -> None:
    lines = [
        f"id: {task['id']}",
        f"phase_id: {task['phase_id']}",
        f"step_id: {task['step_id']}",
        f"title: {json.dumps(task['title'], ensure_ascii=False)}",
        f"status: {task['status']}",
        f"kind: {json.dumps(task.get('kind') or 'unspecified', ensure_ascii=False)}",
        f"target: {json.dumps(task.get('target') or '', ensure_ascii=False)}",
        f"product_increment: {json.dumps(task.get('product_increment') or 'unspecified', ensure_ascii=False)}",
        f"build_state: {json.dumps(task.get('build_state') or 'planned', ensure_ascii=False)}",
        f"risk_level: {json.dumps(task.get('risk_level') or 'medium', ensure_ascii=False)}",
        f"verify_mode: {json.dumps(task.get('verify_mode') or 'human', ensure_ascii=False)}",
        f"route: {json.dumps(task.get('route') or '', ensure_ascii=False)}",
        f"endpoint: {json.dumps(task.get('endpoint') or '', ensure_ascii=False)}",
        "journey_refs:",
    ]
    for item in task.get("journey_refs", []) or []:
        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append("tables:")
    for item in task.get("tables", []) or []:
        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append("depends_on:")
    for dep in task.get("depends_on", []):
        lines.append(f"  - {dep}")
    lines.append("acceptance:")
    for item in task.get("acceptance", []):
        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append("verification_commands:")
    for item in task.get("verification_commands", []):
        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append("allowed_paths:")
    for item in task.get("allowed_paths", []):
        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append("conflict_groups:")
    for item in task.get("conflict_groups", []):
        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append("write_set:")
    for item in task.get("write_set", []):
        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    if task.get("scope_inferred_from_acceptance"):
        lines.append("scope_inferred_from_acceptance:")
        for item in task.get("scope_inferred_from_acceptance", []):
            lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append(f"handoff_path: {task['handoff_path']}")
    lines.append(f"evidence_dir: {task['evidence_dir']}")
    lines.append(f"source_ref: {json.dumps(task['source_ref'], ensure_ascii=False)}")
    if task.get("source_fingerprint"):
        lines.append(f"source_fingerprint: {json.dumps(task['source_fingerprint'], ensure_ascii=False)}")
    write_text(path, "\n".join(lines) + "\n")



_SOURCE_FINGERPRINT_FIELDS = (
    "id",
    "phase_id",
    "step_id",
    "title",
    "kind",
    "target",
    "product_increment",
    "build_state",
    "risk_level",
    "verify_mode",
    "depends_on",
    "conflict_groups",
    "write_set",
    "allowed_paths",
    "acceptance",
    "verification_commands",
    "journey_refs",
    "route",
    "endpoint",
    "tables",
    "origin_instr",
    "origin_techguide",
)

CLOSER_FINAL_STATUSES = {"done"}
CLOSER_FINAL_OUTCOMES = {"committed"}


def _canonical_for_fingerprint(value: Any) -> Any:
    """Return a stable JSON-serializable value for source fingerprinting."""
    if isinstance(value, dict):
        return {str(k): _canonical_for_fingerprint(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonical_for_fingerprint(v) for v in value]
    if isinstance(value, tuple):
        return [_canonical_for_fingerprint(v) for v in value]
    return value


def task_source_fingerprint(task: dict[str, Any]) -> str:
    """Fingerprint the source-of-truth definition of a task.

    Runtime fields are intentionally excluded. A stable fingerprint lets
    `--refresh` preserve lifecycle state only when the same TASK_ID still
    represents the same Coverage Registry definition.
    """
    payload = {field: _canonical_for_fingerprint(task.get(field)) for field in _SOURCE_FINGERPRINT_FIELDS}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def attach_task_source_fingerprints(tasks: list[dict[str, Any]]) -> None:
    """Attach source fingerprints after all source-derived enrichment is done."""
    for task in tasks:
        task["source_fingerprint"] = task_source_fingerprint(task)


def _is_closer_final_task(task: dict[str, Any]) -> bool:
    return str(task.get("status") or "") in CLOSER_FINAL_STATUSES or str(task.get("last_outcome") or "") in CLOSER_FINAL_OUTCOMES


def _mark_source_fingerprint_changed(task: dict[str, Any], old: dict[str, Any]) -> None:
    """Block a task whose source definition changed under an existing TASK_ID."""
    old_status = old.get("status")
    old_outcome = old.get("last_outcome")
    task["status"] = "blocked"
    task["blocked_reason"] = "source_of_truth_changed_after_runtime_state"
    blockers = task.get("blocked_by")
    if not isinstance(blockers, list):
        blockers = []
    blocker = "source_fingerprint_changed"
    if blocker not in blockers:
        blockers.append(blocker)
    task["blocked_by"] = blockers
    task["last_blocker"] = {
        "type": "source_fingerprint_changed",
        "previous_status": old_status,
        "previous_last_outcome": old_outcome,
        "old_source_fingerprint": old.get("source_fingerprint"),
        "new_source_fingerprint": task.get("source_fingerprint"),
        "ts": now_iso(),
    }
    task["source_fingerprint_changed"] = True
    task["previous_runtime_status"] = old_status
    task["previous_runtime_last_outcome"] = old_outcome

_RUNTIME_TASK_FIELDS_TO_PRESERVE = {
    "status",
    "last_updated_by",
    "last_stop_at",
    "last_outcome",
    "last_note",
    "last_blocker",
    "blocked_reason",
    "blocked_by",
    "validator_outcome",
    "validator_next_status",
    "tester_outcome",
    "debugger_outcome",
    "closer_outcome",
    "deployer_outcome",
    "retry_count",
    "debug_retry_count",
    "claimed_by",
    "claimed_at",
    "worktree",
    "branch",
}

_RUNTIME_KEYS_TO_PRESERVE = {
    "last_worker",
    "last_event",
    "pending_journey_verifications",
    "last_journey_verified",
    "spawn_budget",
    "spawns_in_current_slice",
    "open_followups",
    "last_trailer",
    "last_stop_at",
    "last_claimed_task_id",
}


def _apply_preserved_runtime(tasks: list[dict[str, Any]], phases: list[dict[str, Any]], previous_registry: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Preserve live DAG runtime fields across source-of-truth refresh.

    The Coverage Registry remains authoritative for task definitions: title,
    depends_on, conflict_groups, write_set, allowed_paths, acceptance,
    verification_commands, routes, endpoints and tables are always regenerated.

    Only lifecycle/runtime fields owned by claim/hooks/closer are carried
    forward, and only when the same TASK_ID still has the same source
    fingerprint. A refresh must never silently reopen a closer-final task, and
    it must never silently keep a task done when its source-of-truth definition
    changed.
    """
    old_by_id = {str(t.get("id")): t for t in previous_registry.get("tasks", []) if t.get("id")}
    preserved = 0
    for task in tasks:
        old = old_by_id.get(str(task.get("id")))
        if not old:
            continue
        old_fp = old.get("source_fingerprint")
        new_fp = task.get("source_fingerprint")
        same_definition = bool(old_fp and new_fp and old_fp == new_fp)
        # Migration path: registries generated before source_fingerprint existed
        # are allowed to preserve once. The freshly generated task receives a
        # fingerprint, so the next refresh becomes fully drift-aware.
        missing_previous_fingerprint = not old_fp
        if not (same_definition or missing_previous_fingerprint):
            if _is_closer_final_task(old):
                # A completed slice is immutable runtime history. A source doc
                # edit or a Runtime Follow-up Coverage Registry append must not
                # silently reopen it or rewrite its work-item from done ->
                # blocked. Surface the drift as metadata so humans can create a
                # new follow-up if the changed definition represents new work.
                for key in _RUNTIME_TASK_FIELDS_TO_PRESERVE:
                    if key in old:
                        task[key] = old[key]
                for key in ("status", "last_outcome", "last_updated_by", "last_stop_at"):
                    if key in old:
                        task[key] = old[key]
                task["source_fingerprint_changed_after_done"] = True
                task["previous_source_fingerprint"] = old.get("source_fingerprint")
                task["source_fingerprint_change_recorded_at"] = now_iso()
                notes = task.setdefault("notes", [])
                note = "Source fingerprint changed after closer-final state; preserved done lifecycle. Open/promote a follow-up for any new work instead of reopening this slice."
                if note not in notes:
                    notes.append(note)
                preserved += 1
                continue
            _mark_source_fingerprint_changed(task, old)
            continue
        for key in _RUNTIME_TASK_FIELDS_TO_PRESERVE:
            if key in old:
                task[key] = old[key]
        # Defensive re-assertion for closer-final tasks. If a task has already
        # been committed/closed by closer and the source definition has not
        # changed, refresh must never reopen it.
        if _is_closer_final_task(old):
            for key in ("status", "last_outcome", "last_updated_by", "last_stop_at"):
                if key in old:
                    task[key] = old[key]
        preserved += 1
    # Recompute phase status from preserved task statuses using the same
    # phase vocabulary as common.refresh_phase_statuses (`complete` for all-done
    # phases). This keeps bootstrap refresh/register-followup regeneration from
    # reverting project phase YAML from complete -> done.
    task_by_id = {str(t.get("id")): t for t in tasks if t.get("id")}
    for phase in phases:
        phase_tasks = [task_by_id.get(str(tid)) for tid in phase.get("task_ids", [])]
        phase_tasks = [t for t in phase_tasks if t]
        statuses = {str(t.get("status") or "") for t in phase_tasks}
        if phase_tasks and all(st == "done" for st in statuses):
            phase["status"] = "complete"
        elif statuses & {"ready", "claimed", "in_progress", "validator_tester_pending", "ready_for_close", "verified_pending_close", "needs_debug", "test_pending", "qa_pending", "review_pending"}:
            phase["status"] = "ready"
        elif phase_tasks:
            phase["status"] = "blocked"
    return tasks, phases, preserved

def _runtime_after_refresh(previous_runtime: dict[str, Any], tasks: list[dict[str, Any]], phases: list[dict[str, Any]], *, preserve_runtime_state: bool) -> dict[str, Any]:
    next_ready_task = next((t for t in tasks if t.get("status") == "ready"), None)
    next_ready_phase_id = (next_ready_task or {}).get("phase_id") or (phases[0].get("id") if phases else None)
    state = {
        "generated_at": now_iso(),
        "next_ready_phase_id": next_ready_phase_id,
        "next_ready_task_id": (next_ready_task or {}).get("id"),
        "last_worker": None,
        "last_event": "bootstrap_refresh",
        "pending_journey_verifications": [],
        "last_journey_verified": None,
        "spawn_budget": 20,
        "spawns_in_current_slice": {},
        "open_followups": [],
    }
    if not preserve_runtime_state:
        return state

    for key in _RUNTIME_KEYS_TO_PRESERVE:
        if key in previous_runtime:
            state[key] = previous_runtime[key]
    if not isinstance(state.get("pending_journey_verifications"), list):
        state["pending_journey_verifications"] = []
    if not isinstance(state.get("spawns_in_current_slice"), dict):
        state["spawns_in_current_slice"] = {}
    if not isinstance(state.get("open_followups"), list):
        state["open_followups"] = []
    state["generated_at"] = now_iso()
    state["last_event"] = "bootstrap_refresh_preserve_runtime"
    # FW-003 wiring: preserved aggregates get re-validated against the fresh
    # registry. Stale JIDs (J103 capa-4), gone follow-ups, ready hints to done
    # tasks — all dropped.
    try:
        from common import reconcile_runtime_state as _reconcile, load_registry as _load_registry
        proj_reg = _load_registry()
        if proj_reg:
            cleaned, repairs = _reconcile(proj_reg, state, apply=False)
            if repairs:
                state["pending_journey_verifications"] = cleaned.get("pending_journey_verifications", [])
                state["next_ready_task_id"] = cleaned.get("next_ready_task_id")
                state["next_ready_phase_id"] = cleaned.get("next_ready_phase_id")
                state["spawns_in_current_slice"] = cleaned.get("spawns_in_current_slice", {})
                state["open_followups"] = cleaned.get("open_followups", [])
                state["last_event"] = "bootstrap_refresh_reconciled"
    except Exception:
        pass
    return state


def generate_artifacts(*, preserve_runtime_state: bool = True) -> dict[str, Any]:
    docs = discover_source_docs(project_root())
    validation = validate_docs(docs)
    if validation["errors"]:
        return {"ok": False, "validation": validation, "docs": _serializable_doc_paths(docs)}

    previous_registry = load_registry() if preserve_runtime_state else {"tasks": [], "phases": []}
    previous_runtime = load_runtime_state() if preserve_runtime_state else {}

    instructions_path = docs["instructions"][0]
    checklist_path = docs["checklist"][0]
    guide_path = docs["guide"][0]
    ux_path = (docs.get("ux") or [None])[0]
    stack_profile_path = (docs.get("stack_profile") or [None])[0]
    instructions_text = read_text(instructions_path)
    checklist_text = read_text(checklist_path)
    guide_text = read_text(guide_path)
    ux_text = read_text(ux_path) if ux_path else ""

    manifest = build_manifest(instructions_path, checklist_path, guide_path, validation, ux_path=ux_path, stack_profile_path=stack_profile_path)
    phases, tasks = build_phases_and_tasks(checklist_path, checklist_text)
    _augment_task_scope_from_text(tasks)
    attach_task_source_fingerprints(tasks)
    # Lift the coarse-synthetic warnings (if any) into validation so the
    # user sees them on the bootstrap CLI output and in source-manifest.
    coarse_warnings_local = phases[0].pop("_coarse_warnings", []) if phases else []
    dag_errors_local = phases[0].pop("_dag_errors", []) if phases else []
    for w in coarse_warnings_local:
        validation.setdefault("warnings", []).append(w)
    for err in dag_errors_local:
        validation.setdefault("errors", []).append(err)

    preserved_task_count = 0
    if preserve_runtime_state:
        tasks, phases, preserved_task_count = _apply_preserved_runtime(tasks, phases, previous_registry)

    task_dag = build_task_dag(tasks)
    for err in task_dag.get("errors", []):
        if err not in validation.setdefault("errors", []):
            validation["errors"].append(err)
    if validation.get("errors"):
        return {"ok": False, "validation": validation, "docs": _serializable_doc_paths(docs), "phases": phases, "tasks": tasks, "task_dag": task_dag}

    # Journey Coverage Matrix (§3.5 of instrucciones.md). Empty list if absent.
    # Pass the freshly-built task list so the parser can expand step / phase
    # refs in the Slices column to real TASK_IDs.
    journeys = extract_journey_matrix(instructions_text, all_tasks=tasks)
    journeys = enrich_journey_completion_metadata(journeys, tasks, task_dag)

    # Fix B4 validation: check every journey.task_id resolves to a real task.
    # Unresolved IDs are added as warnings — never block the bootstrap, since
    # journeys can legitimately reference future canonical IDs (cross-phase
    # endpoints declared in the registry but not yet in the doc body).
    known_task_ids = {t["id"] for t in tasks}
    for j in journeys:
        unresolved = [tid for tid in j.get("task_ids", []) if tid not in known_task_ids]
        if unresolved:
            validation.setdefault("warnings", []).append(
                f"Journey {j.get('id')}: {len(unresolved)} task_id(s) do not resolve to a registry task: {unresolved[:5]}"
            )

    memory = memory_dir()
    tasks_root = tasks_dir()
    memory.mkdir(parents=True, exist_ok=True)
    tasks_root.mkdir(parents=True, exist_ok=True)
    (tasks_root / "phases").mkdir(parents=True, exist_ok=True)
    (tasks_root / "work-items").mkdir(parents=True, exist_ok=True)
    # New dirs for journey verification artifacts.
    (tasks_root / "journey-handoffs").mkdir(parents=True, exist_ok=True)
    (tasks_root / "evidence" / "journeys").mkdir(parents=True, exist_ok=True)
    (tasks_root / "follow-ups").mkdir(parents=True, exist_ok=True)
    (tasks_root / "source-doc-patches").mkdir(parents=True, exist_ok=True)

    write_json(memory / "source-manifest.json", manifest)
    write_json(memory / "stack-profile.json", load_stack_profile(project_root()))
    if ux_path:
        write_text(memory / "ux-contract.md", ux_text)
    write_text(memory / "project-brief.md", build_project_brief(instructions_path, checklist_path, guide_path, instructions_text, validation))
    write_text(memory / "architecture-contract.md", build_architecture_contract(guide_path, guide_text))

    # Initialize PROGRESS.md if it doesn't exist
    progress_path = memory / "PROGRESS.md"
    if not progress_path.exists():
        progress_content = f"""# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System
- **Last completed slice**: —
- **Next pending slice**: {tasks[0]['title'] if tasks else '—'}
- **Blockers**: none
- **Generated at**: {now_iso()}

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not started | — |
| Health check | — | — |
| Endpoints implemented | 0 | — |
| Migrations applied | 0 | — |
| Seed data | not loaded | — |
| Backend tests | 0 passing | — |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | not started | — |
| Routes implemented | 0 | — |
| Components | 0 | — |
| Frontend tests | 0 passing | — |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| (none yet) | — | — | — |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 0 | — |
| Frontend unit | 0 | — |
| Frontend component | 0 | — |
| E2E | 0 | — |
| **Total** | **0** | — |

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| (none yet) | — | — | — |

## Journeys (from the Journey Coverage Matrix of instrucciones.md)

| Journey | Milestone | Status | Slices |
|---------|-----------|--------|--------|
{chr(10).join(f'| {j["id"]} | {j["milestone"]} | pending | {len(j["task_ids"])} | ' for j in journeys) if journeys else "| (none yet) | — | — | — |"}

## Recent Decisions

(none yet)

## Known Issues / Risks

(none yet)

---

> Last updated: {now_iso()}
> Updated by: bootstrap_source_of_truth.py
"""
        write_text(progress_path, progress_content)

    registry = {
        "generated_at": now_iso(),
        "project_prefix": manifest["project_prefix"],
        "phase_order": [p["id"] for p in phases],
        "phases": phases,
        "tasks": tasks,
        "journeys": journeys,
        "task_dag": task_dag,
    }
    # registry.json is the canonical runtime graph source. task-dag.json/md
    # and execution-graph.json are derived views. Write the canonical source
    # first so a failed refresh cannot leave new views pointing at old tasks.
    # check-task-dag --strict verifies view drift before next-wave/phase-gate.
    save_registry(registry)
    write_json(memory / "task-dag.json", task_dag)
    write_text(memory / "task-dag.md", render_task_dag_markdown(task_dag, tasks))
    execution_graph = {
        "generated_at": now_iso(),
        "phase_order": [p["id"] for p in phases],
        "phases": phases,
        "tasks": tasks,
        "journeys": journeys,
        "task_dag": task_dag,
    }
    write_json(memory / "execution-graph.json", execution_graph)

    for phase in phases:
        write_phase_yaml(tasks_root / "phases" / f"{phase['id']}.yaml", phase)
    for task in tasks:
        write_task_yaml(tasks_root / "work-items" / f"{task['id']}.yaml", task)

    runtime_state = _runtime_after_refresh(previous_runtime, tasks, phases, preserve_runtime_state=preserve_runtime_state)
    save_runtime_state(runtime_state)

    # Materialize API contracts from the freshly-written registry. This closes
    # the front/back drift hole: if registry endpoints change,
    # ./scripts/generate-api-contracts.sh --validate-only fails until refreshed.
    from generate_api_contracts import generate_contracts
    api_contracts = generate_contracts(validate_only=False)

    append_jsonl(tasks_root / "ledger.jsonl", {
        "ts": now_iso(),
        "event": "bootstrap_refresh",
        "phase_count": len(phases),
        "task_count": len(tasks),
        "journey_count": len(journeys),
        "task_dag_mode": task_dag.get("mode"),
        "task_dag_wave_count": len(task_dag.get("topological_levels") or []),
        "project_prefix": manifest["project_prefix"],
        "api_contract_endpoint_count": api_contracts.get("endpoint_count", 0),
        "preserve_runtime_state": preserve_runtime_state,
        "preserved_task_count": preserved_task_count,
    })

    return {
        "ok": True,
        "manifest": manifest,
        "phase_count": len(phases),
        "task_count": len(tasks),
        "journey_count": len(journeys),
        "task_dag_mode": task_dag.get("mode"),
        "task_dag_wave_count": len(task_dag.get("topological_levels") or []),
        "api_contracts": api_contracts,
        "phases": phases,
        "tasks": tasks,
        "journeys": journeys,
        "task_dag": task_dag,
        "validation": validation,
        "preserve_runtime_state": preserve_runtime_state,
        "preserved_task_count": preserved_task_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a source-of-truth DAG project.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate the source-of-truth contract.")
    parser.add_argument("--refresh", action="store_true", help="Generate or refresh artifacts. Preserves live runtime state by default.")
    parser.add_argument("--preserve-runtime-state", dest="preserve_runtime_state", action="store_true", default=True, help="Preserve existing task lifecycle/runtime metadata during refresh (default).")
    parser.add_argument("--reset-runtime-state", dest="preserve_runtime_state", action="store_false", help="Explicitly reset runtime-state/task lifecycle metadata while refreshing.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    docs = discover_source_docs(project_root())
    validation = validate_docs(docs)

    if args.validate_only and not args.refresh:
        result = {"ok": not bool(validation["errors"]), "validation": validation, "docs": {k: [relpath(p) for p in v] for k, v in docs.items()}}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["ok"]:
                print("Source-of-truth contract is valid.")
            else:
                print("Source-of-truth contract is INVALID.")
            for err in validation["errors"]:
                print(f"ERROR: {err}")
            for warn in validation["warnings"]:
                print(f"WARNING: {warn}")
            print(json.dumps(result["docs"], ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    result = generate_artifacts(preserve_runtime_state=args.preserve_runtime_state)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["ok"]:
            print(f"Bootstrapped project prefix: {result['manifest']['project_prefix']}")
            print(f"Detected phases: {result['phase_count']}")
            print(f"Generated tasks: {result['task_count']}")
            print(f"Detected journeys: {result.get('journey_count', 0)}")
            print("Artifacts written under orchestrator-state/memory and orchestrator-state/tasks")
            if result.get("preserve_runtime_state"):
                print(f"Runtime state preserved by default ({result.get('preserved_task_count', 0)} matching task(s)). Use --reset-runtime-state only for intentional destructive resets.")
        else:
            print("Failed to bootstrap due to validation errors.")
            for err in result["validation"]["errors"]:
                print(f"ERROR: {err}")
            for warn in result["validation"]["warnings"]:
                print(f"WARNING: {warn}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
