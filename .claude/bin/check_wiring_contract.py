#!/usr/bin/env python3
"""Validate cross-document wiring for routes, endpoints, journeys and slices.

This is intentionally a broad Markdown contract checker, not a full compiler.
It verifies that the source-of-truth docs agree on the identifiers that
make a slice implementable: Flutter route/page, API endpoint, DB tables, journey
IDs and Slice IDs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import discover_source_docs, project_root

SENTINELS = {"", "-", "—", "n/a", "N/A", "na", "none", "None", "(none)", "(None)"}
TASK_RE = re.compile(r"^[A-Z]\d+-S\d+-T\d+$")
JOURNEY_ROW_RE = re.compile(r"^\|\s*J\d+\s*\|")
REQUIRED_JOURNEY_HEADERS = ["id", "milestone", "screens", "actions", "endpoints", "tables", "client_state", "slices", "verification"]
ENDPOINT_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)(?:/[A-Z]+)*\s+([^\s,;`|]+)", re.I)
PATH_RE = re.compile(r"/[^\s,;`|]+")
ROUTE_RE = re.compile(r"^/[A-Za-z0-9_{}:?.=\-/]*$")
JOURNEY_SECTION_RE = re.compile(r"(?i)\bJourney\s+Coverage\s+Matrix\b")
HEADING_RE = re.compile(r"^(#{1,6})\s+.*$")

DATA_CONTRACT_RE = re.compile(r"(?i)(Verification\s+Data\s+Contract|Contrato\s+de\s+datos\s+de\s+verificaci[oó]n)")
AUTO_VERIFY_PLACEHOLDERS = {"auto", "automatic", "automático", "automatico", "manual", "human", "humano", "todo", "tbd"}
AUTO_VERIFY_COMMAND_RE = re.compile(r"(?:^|[;|&\n])\s*(?:python3?|pytest|flutter\s+test|dart\s+test|npm\s+test|pnpm\s+test|yarn\s+test|curl|bash|sh|make)\b", re.I)


def clean(value: str) -> str:
    return (value or "").replace("`", "").replace("\\|", "|").strip()


def lower_key(value: str) -> str:
    return re.sub(r"\s+", " ", clean(value).lower())


def is_none(value: str) -> bool:
    return clean(value) in SENTINELS


def looks_like_auto_verify_command(value: str) -> bool:
    value = clean(value)
    if not value or value.lower() in AUTO_VERIFY_PLACEHOLDERS or is_none(value):
        return False
    return bool(AUTO_VERIFY_COMMAND_RE.search(value))


def split_md_row(row: str) -> list[str]:
    placeholder = "\x00PIPE\x00"
    safe = (row or "").replace(r"\|", placeholder)
    cells = [c.replace(placeholder, "|").strip() for c in safe.split("|")]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def iter_tables(text: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    lines = text.splitlines()
    sep_re = re.compile(r"^\|[\s:\-|]+\|?\s*$")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("|") or i + 1 >= len(lines) or not sep_re.match(lines[i + 1]):
            i += 1
            continue
        header = split_md_row(line)
        rows: list[list[str]] = []
        j = i + 2
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            row = split_md_row(lines[j])
            if row and not all(re.fullmatch(r"[:\-\s]+", c or "") for c in row):
                rows.append(row)
            j += 1
        tables.append({"line": i + 1, "header": header, "rows": rows})
        i = j
    return tables


def row_dict(header: list[str], row: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for idx, name in enumerate(header):
        out[lower_key(name)] = clean(row[idx]) if idx < len(row) else ""
    return out


def get_any(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if key in row and not is_none(row[key]):
            return row[key]
    return ""


def split_items(value: str) -> list[str]:
    value = clean(value)
    if is_none(value):
        return []
    parts = re.split(r",|→|;|\n", value)
    return [clean(p) for p in parts if clean(p) and not is_none(p)]


def extract_endpoint_tokens(value: str, default_method: str = "") -> list[str]:
    value = clean(value)
    if is_none(value):
        return []
    found: list[str] = []
    for method, path in ENDPOINT_RE.findall(value):
        token = f"{method.upper()} {path}"
        if token not in found:
            found.append(token)
    if found:
        return found
    for path in PATH_RE.findall(value):
        method = default_method.upper().strip()
        token = f"{method} {path}" if method else path
        if token not in found:
            found.append(token)
    return found


def endpoint_key(token: str) -> tuple[str, str]:
    token = clean(token)
    m = ENDPOINT_RE.search(token)
    if m:
        return m.group(1).upper(), m.group(2)
    parts = token.split(maxsplit=1)
    if len(parts) == 2 and re.fullmatch(r"[A-Z/]+", parts[0], re.I):
        return parts[0].upper(), parts[1]
    return "", token


def path_matches(needed: str, available: str) -> bool:
    needed_m, needed_p = endpoint_key(needed)
    avail_m, avail_p = endpoint_key(available)
    if avail_m and needed_m:
        methods = set(avail_m.split("/"))
        if needed_m not in methods:
            return False
    if needed_p == avail_p:
        return True
    if avail_p.endswith("*") and needed_p.startswith(avail_p[:-1]):
        return True
    if needed_p.endswith("*") and avail_p.startswith(needed_p[:-1]):
        return True
    return False


def any_endpoint_match(needed: str, available: set[str]) -> bool:
    return any(path_matches(needed, candidate) for candidate in available)


def find_docs(root: Path) -> tuple[Path, Path, Path]:
    docs = discover_source_docs(root)
    core = ("instructions", "checklist", "guide")
    missing = [k for k in core if len(docs.get(k) or []) != 1]
    if missing:
        raise FileNotFoundError("Expected exactly one instrucciones, checklist and technical guide in docs/source-of-truth")
    return docs["instructions"][0], docs["checklist"][0], docs["guide"][0]


def parse_guide(guide_text: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    routes: list[dict[str, str]] = []
    endpoints: list[dict[str, str]] = []
    for table in iter_tables(guide_text):
        header_keys = [lower_key(h) for h in table["header"]]
        rows = [row_dict(table["header"], r) for r in table["rows"]]
        if "ruta" in header_keys and any(k in header_keys for k in ("page", "page / widget")):
            for r in rows:
                route = get_any(r, ["ruta", "ruta web"])
                page = get_any(r, ["page", "page / widget", "pantallas flutter", "pantalla"])
                if route and ROUTE_RE.match(route):
                    routes.append({
                        "route": route,
                        "page": page,
                        "slice_id": get_any(r, ["slice id", "slice"]),
                        "journey_refs": get_any(r, ["journey refs", "journeys", "journey"]),
                        "endpoints": get_any(r, ["endpoints consumidos", "consume endpoints", "endpoints"]),
                        "client_state": get_any(r, ["estado cliente/provider", "client state", "provider", "estado"]),
                        "ui_states": get_any(r, ["estados ui obligatorios", "ui states", "states"]),
                        "next_action": get_any(r, ["next action", "acción siguiente", "siguiente acción"]),
                        "line": str(table["line"]),
                    })
        if "method" in header_keys and "path" in header_keys:
            for r in rows:
                method = get_any(r, ["method", "método"]).upper()
                path = get_any(r, ["path", "ruta"])
                if method and path and PATH_RE.match(path):
                    endpoints.append({
                        "token": f"{method} {path}",
                        "method": method,
                        "path": path,
                        "consumer": get_any(r, ["consumidor front/journey", "consumer", "consumidor"]),
                        "tables": get_any(r, ["tablas/side effects", "tablas db", "tables"]),
                        "slice_id": get_any(r, ["slice id", "slice"]),
                        "line": str(table["line"]),
                    })
    return routes, endpoints


def parse_registry(checklist_text: str) -> list[dict[str, str]]:
    rows_out: list[dict[str, str]] = []
    for table in iter_tables(checklist_text):
        header = [lower_key(h) for h in table["header"]]
        if not header or header[0] != "slice id":
            continue
        for raw in table["rows"]:
            r = row_dict(table["header"], raw)
            sid = get_any(r, ["slice id"])
            if not sid or not TASK_RE.match(sid):
                continue
            method = get_any(r, ["method", "método"])
            path = get_any(r, ["path", "endpoint", "consume endpoints", "endpoints"])
            endpoint_tokens: list[str] = []
            if method and path:
                endpoint_tokens.append(f"{method.upper()} {path}")
            endpoint_tokens.extend(extract_endpoint_tokens(get_any(r, ["endpoint", "path", "target", "consume endpoints"]), method))
            # De-duplicate while preserving order.
            dedup: list[str] = []
            for token in endpoint_tokens:
                if token not in dedup:
                    dedup.append(token)
            rows_out.append({
                "slice_id": sid,
                "tipo": get_any(r, ["tipo", "type"]),
                "target": get_any(r, ["target", "page / widget", "migration / objeto"]),
                "route": get_any(r, ["pantalla/ruta", "ruta"]),
                "page": get_any(r, ["page", "page / widget", "pantalla"]),
                "endpoints": ", ".join(dedup),
                "tables": get_any(r, ["tablas db", "tablas / objetos", "tables"]),
                "journey_refs": get_any(r, ["journey refs", "journeys", "journey"]),
                "origin_instr": get_any(r, ["origen-instr", "origen instr", "source instr"]),
                "build_state": get_any(r, ["build state", "estado build", "estado"]),
                "risk_level": get_any(r, ["risk level", "risk", "riesgo"]),
                "verify_mode": get_any(r, ["verify mode", "verification mode", "modo verify", "modo verificación", "modo verificacion"]),
                "verify_minimo": get_any(r, ["verify mínimo", "verify minimo", "verify minimum", "verification minimum", "verificación mínima", "verificacion minima"]),
                "line": str(table["line"]),
                "headers": ",".join(header),
            })
    return rows_out


def normalise_journey_header(value: str) -> str:
    key = lower_key(value)
    aliases = {
        "id": "id", "journey id": "id", "jid": "id", "journey": "id",
        "milestone": "milestone", "hito": "milestone", "m": "milestone",
        "p": "screens", "pantallas": "screens", "pantallas (en orden)": "screens", "screens": "screens", "screens (ordered)": "screens",
        "a": "actions", "acciones": "actions", "acciones clave": "actions", "actions": "actions", "key actions": "actions",
        "ep": "endpoints", "endpoints": "endpoints", "endpoint": "endpoints",
        "t": "tables", "tablas db": "tables", "tablas": "tables", "tables": "tables", "db tables": "tables",
        "s": "client_state", "estado": "client_state", "estado cliente": "client_state", "client state": "client_state", "providers": "client_state", "estado cliente/provider": "client_state",
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

def _journey_matrix_section(text: str) -> str:
    """Return only the Journey Coverage Matrix section.

    This avoids a production-dangerous false positive where any unrelated
    Markdown table with an `ID` column was parsed as a journey matrix and could
    produce meaningless header errors.
    """
    lines = text.splitlines()
    start = None
    start_level = 6
    for idx, line in enumerate(lines):
        if JOURNEY_SECTION_RE.search(line):
            start = idx
            match = HEADING_RE.match(line)
            start_level = len(match.group(1)) if match else 6
            break
    if start is None:
        return ""
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        match = HEADING_RE.match(lines[idx])
        if match and len(match.group(1)) <= start_level:
            end = idx
            break
    return "\n".join(lines[start:end])


def parse_journeys(instructions_text: str) -> tuple[list[dict[str, str]], list[str]]:
    journeys: list[dict[str, str]] = []
    errors: list[str] = []
    section = _journey_matrix_section(instructions_text)
    if not section:
        return journeys, errors
    for table in iter_tables(section):
        headers = [normalise_journey_header(h) for h in table["header"]]
        if "id" not in headers:
            continue
        missing = [h for h in REQUIRED_JOURNEY_HEADERS if h not in headers]
        if missing:
            errors.append("Journey Coverage Matrix missing required header(s): " + ", ".join(missing))
            continue
        for raw in table["rows"]:
            r = {h: clean(raw[idx]) if idx < len(raw) else "" for idx, h in enumerate(headers)}
            if not re.match(r"^J\d+$", r.get("id", "")):
                continue
            journeys.append({
                "id": r.get("id", ""),
                "screens": r.get("screens", ""),
                "endpoints": r.get("endpoints", ""),
                "tables": r.get("tables", ""),
                "slices": r.get("slices", ""),
            })
    return journeys, errors

def validate(root: Path, require_new_template_columns: bool = False) -> dict[str, Any]:
    instructions, checklist, guide = find_docs(root)
    instructions_text = instructions.read_text(encoding="utf-8", errors="replace")
    checklist_text = checklist.read_text(encoding="utf-8", errors="replace")
    guide_text = guide.read_text(encoding="utf-8", errors="replace")

    routes, guide_endpoints = parse_guide(guide_text)
    registry = parse_registry(checklist_text)
    journeys, journey_parse_errors = parse_journeys(instructions_text)
    has_data_contract = bool(DATA_CONTRACT_RE.search(guide_text))

    errors: list[str] = []
    warnings: list[str] = []
    if require_new_template_columns and not has_data_contract:
        errors.append("TECHNICAL_GUIDE missing Verification Data Contract for real/provided verify-slice data")
    errors.extend(journey_parse_errors)

    task_ids = {r["slice_id"] for r in registry}
    journey_ids = {j["id"] for j in journeys}
    registry_endpoints: set[str] = set()
    registry_routes: set[str] = set()
    registry_pages: set[str] = set()
    for r in registry:
        for token in extract_endpoint_tokens(r.get("endpoints", "")):
            registry_endpoints.add(token)
        for token in split_items(r.get("route", "")):
            if ROUTE_RE.match(token):
                registry_routes.add(token)
        if r.get("page"):
            registry_pages.add(r["page"])
        if r.get("target"):
            registry_pages.add(r["target"])

    guide_endpoint_tokens = {e["token"] for e in guide_endpoints}
    route_values = {r["route"] for r in routes}
    page_values = {r["page"] for r in routes if r.get("page")}

    for endpoint in sorted(guide_endpoint_tokens):
        if not any_endpoint_match(endpoint, registry_endpoints):
            warnings.append(f"endpoint in TECHNICAL_GUIDE not mapped in Coverage Registry: {endpoint}")

    for endpoint in guide_endpoints:
        consumer = endpoint.get("consumer", "")
        if require_new_template_columns and not consumer:
            errors.append(f"endpoint missing Consumidor front/journey column value: {endpoint['token']}")
        if endpoint.get("slice_id") and endpoint["slice_id"] not in task_ids:
            errors.append(f"endpoint {endpoint['token']} references unknown Slice ID {endpoint['slice_id']}")

    for route in routes:
        if route.get("slice_id") and route["slice_id"] not in task_ids:
            errors.append(f"route {route['route']} references unknown Slice ID {route['slice_id']}")
        if require_new_template_columns:
            for field, label in [
                ("journey_refs", "Journey refs"),
                ("client_state", "Estado cliente/provider"),
                ("ui_states", "Estados UI obligatorios"),
                ("next_action", "Next action"),
            ]:
                if not route.get(field):
                    errors.append(f"route {route['route']} missing {label} value")
            ui_states = lower_key(route.get("ui_states", ""))
            for required_state in ("loading", "error", "success"):
                if route.get("ui_states") and required_state not in ui_states:
                    warnings.append(f"route {route['route']} UI states do not mention {required_state}")
        # Archived base docs can map a route to a widget row rather than a route cell.
        route_known = route["route"] in registry_routes or route.get("page") in registry_pages or route["route"] in checklist_text
        if not route_known:
            warnings.append(f"route/page in TECHNICAL_GUIDE not mapped in Coverage Registry: {route['route']} {route.get('page','')}")
        for token in extract_endpoint_tokens(route.get("endpoints", "")):
            if not any_endpoint_match(token, guide_endpoint_tokens):
                warnings.append(f"route {route['route']} consumes endpoint not declared in §6.2: {token}")

    for r in registry:
        headers = set(r.get("headers", "").split(","))
        if require_new_template_columns:
            required = {"slice id", "tipo", "target", "step", "product increment", "build state", "risk level", "verify mode", "depends on", "conflict group", "write set", "journey refs", "pantalla/ruta", "endpoint", "tablas db", "origen-instr", "origen-techguide", "acceptance mínimo", "verify mínimo"}
            missing = sorted(required - headers)
            if missing:
                errors.append(f"Coverage Registry at line {r['line']} missing new-template columns: {', '.join(missing)}")
        for jid in split_items(r.get("journey_refs", "")):
            if re.match(r"^J\d+$", jid) and jid not in journey_ids:
                errors.append(f"slice {r['slice_id']} references unknown Journey ref {jid}")
        for jid in re.findall(r"§3\.7#(J\d+)", r.get("origin_instr", "")):
            if jid not in journey_ids:
                errors.append(f"slice {r['slice_id']} Origen-Instr references unknown journey {jid}")
        verify_mode = lower_key(r.get("verify_mode", ""))
        risk_level = lower_key(r.get("risk_level", ""))
        build_state = lower_key(r.get("build_state", ""))
        if require_new_template_columns and verify_mode == "auto" and build_state != "done":
            if risk_level != "low":
                errors.append(f"slice {r['slice_id']} Verify mode=auto requires Risk level=low for executable/planned work; got: {risk_level or '—'}")
            if not looks_like_auto_verify_command(r.get("verify_minimo", "")):
                errors.append(f"slice {r['slice_id']} Verify mode=auto requires deterministic shell command(s) in Verify mínimo for executable/planned work; got: {r.get('verify_minimo') or '—'}")
        kind = r.get("tipo", "").lower()
        if kind == "api" and not extract_endpoint_tokens(r.get("endpoints", "")):
            errors.append(f"api slice {r['slice_id']} has no parseable endpoint")
        if kind in {"frontend", "flutter", "ui"} and not (r.get("route") or r.get("page") or ROUTE_RE.search(r.get("target", ""))):
            errors.append(f"frontend slice {r['slice_id']} has no route/page wiring")

    for journey in journeys:
        for screen in split_items(journey.get("screens", "")):
            if screen in SENTINELS:
                continue
            key = screen.split()[0] if screen.split() else screen
            if screen not in page_values and key not in guide_text:
                warnings.append(f"journey {journey['id']} screen not found in TECHNICAL_GUIDE: {screen}")
        for token in extract_endpoint_tokens(journey.get("endpoints", "")):
            if not any_endpoint_match(token, guide_endpoint_tokens):
                errors.append(f"journey {journey['id']} endpoint not declared in TECHNICAL_GUIDE §6.2: {token}")
        for slice_ref in split_items(journey.get("slices", "")):
            if TASK_RE.match(slice_ref) and slice_ref not in task_ids:
                warnings.append(f"journey {journey['id']} references Slice ID not present in Coverage Registry: {slice_ref}")

    return {
        "ok": not errors,
        "counts": {
            "routes": len(routes),
            "endpoints": len(guide_endpoints),
            "registry_rows": len(registry),
            "journeys": len(journeys),
            "verification_data_contract": 1 if has_data_contract else 0,
        },
        "warnings": warnings,
        "errors": errors,
        "docs": {
            "instructions": str(instructions.relative_to(root)),
            "checklist": str(checklist.relative_to(root)),
            "guide": str(guide.relative_to(root)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cross-doc route/endpoint/journey/slice wiring.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on wiring errors. Warnings stay warnings.")
    parser.add_argument("--require-new-template-columns", action="store_true", help="Require the expanded DAG wiring columns in Coverage Registry tables.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        result = validate(project_root(), args.require_new_template_columns)
    except Exception as exc:  # noqa: BLE001 - CLI should print readable error
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        c = result["counts"]
        status = "coherent" if result["ok"] else "DRIFT"
        print(f"Wiring contract {status} — {c['routes']} routes, {c['endpoints']} endpoints, {c['registry_rows']} registry rows, {c['journeys']} journeys, data_contract={c.get('verification_data_contract', 0)}")
        if result["warnings"]:
            print(f"Schema warnings: {len(result['warnings'])}")
            for warning in result["warnings"][:50]:
                print(f"WARNING: {warning}")
            if len(result["warnings"]) > 50:
                print(f"WARNING: ... {len(result['warnings']) - 50} more")
        for error in result["errors"]:
            print(f"ERROR: {error}")
    return 0 if result["ok"] or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
