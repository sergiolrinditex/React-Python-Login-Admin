#!/usr/bin/env python3
"""Validate the Journey Coverage Matrix against generated task artifacts.

Stdlib-only helper used by scripts/check-journey-matrix.sh. It intentionally
keeps the checks broad and literal: the matrix is a drift detector, not a full
Markdown/architecture parser.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import project_root

JOURNEY_HEADING_RE = re.compile(r"^#{2,}\s+(?:\d+(?:\.\d+)*\.?\s+)?Journey\s+Coverage\s+Matrix", re.I)
NEXT_TOP_HEADING_RE = re.compile(r"^#{1,2}\s+")
JOURNEY_ROW_RE = re.compile(r"^\|\s*J\d+\s*\|")
REQUIRED_HEADERS = ["id", "milestone", "screens", "actions", "endpoints", "tables", "client_state", "slices", "verification"]
SENTINELS = {"", "-", "—", "n/a", "N/A", "(none)", "(None)"}
FULL_TASK_RE = re.compile(r"^[A-Z]\d+-S\d+-T\d+$")
TASK_RANGE_RE = re.compile(r"^([A-Z]\d+-S\d+-T)(\d+)\.\.([A-Z]?)(\d+)$")
STEP_REF_RE = re.compile(r"^[A-Z]\d+-S\d+$")
PHASE_REF_RE = re.compile(r"^[A-Z]\d+$")
METHOD_RE = re.compile(r"^([A-Z]+(?:/[A-Z]+)*)\s+", re.I)



def log(msg: str) -> None:
    print(f"==> {msg}")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def strip_cell(value: str) -> str:
    return value.replace("`", "").strip()


def is_none(value: str) -> bool:
    value = strip_cell(value)
    if value in SENTINELS:
        return True
    return bool(re.match(r"^\(none($|[^A-Za-z0-9])", value, re.I))


def split_md_row(row: str) -> list[str]:
    placeholder = "\x00PIPE\x00"
    safe = row.replace(r"\|", placeholder)
    cells = [c.replace(placeholder, "|").strip() for c in safe.split("|")]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells




def normalise_header(value: str) -> str:
    key = re.sub(r"\s+", " ", strip_cell(value).strip().lower())
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

def find_matrix_table(text: str) -> tuple[int | None, list[dict[str, str]], list[str]]:
    lines = text.splitlines()
    start_idx: int | None = None
    for i, line in enumerate(lines):
        if JOURNEY_HEADING_RE.search(line):
            start_idx = i
            break
    if start_idx is None:
        return None, [], []
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if NEXT_TOP_HEADING_RE.match(lines[j]):
            end_idx = j
            break
    section = lines[start_idx:end_idx]
    for off, row in enumerate(section):
        if not row.lstrip().startswith("|"):
            continue
        headers = [normalise_header(h) for h in split_md_row(row)]
        if "id" not in headers:
            continue
        missing = [h for h in REQUIRED_HEADERS if h not in headers]
        if missing:
            return start_idx + off + 1, [], ["Journey Coverage Matrix missing required header(s): " + ", ".join(missing)]
        if off + 1 >= len(section) or not re.match(r"^\|[\s:\-|]+\|?\s*$", section[off + 1]):
            return start_idx + off + 1, [], ["Journey Coverage Matrix header is not followed by separator row"]
        rows: list[dict[str, str]] = []
        k = off + 2
        while k < len(section) and section[k].lstrip().startswith("|"):
            cells = split_md_row(section[k])
            if cells and not all(re.fullmatch(r"[:\-\s]+", c or "") for c in cells):
                data = {h: strip_cell(cells[idx]) if idx < len(cells) else "" for idx, h in enumerate(headers)}
                if re.match(r"^J\d+$", data.get("id", "")):
                    rows.append(data)
            k += 1
        return start_idx + off + 1, rows, []
    return start_idx + 1, [], []

def split_list(value: str, arrows: bool = False) -> list[str]:
    pattern = r"[→,]" if arrows else r"," 
    return [strip_cell(part) for part in re.split(pattern, value) if strip_cell(part)]


def validate_slice(ref: str, jid: str, root: Path, drifts: list[str]) -> None:
    ref = strip_cell(ref)
    if not ref or is_none(ref):
        return
    workitems = root / "orchestrator-state/tasks/work-items"
    phases = root / "orchestrator-state/tasks/phases"
    m = TASK_RANGE_RE.match(ref)
    if m:
        prefix, start_raw, _end_prefix, end_raw = m.groups()
        start_n, end_n = int(start_raw), int(end_raw)
        width = len(start_raw)
        for n in range(start_n, end_n + 1):
            task_id = f"{prefix}{n:0{width}d}"
            if not (workitems / f"{task_id}.yaml").is_file():
                drifts.append(f"{jid}: slice '{task_id}' (expandida de '{ref}') no existe en work-items/")
        return
    if FULL_TASK_RE.match(ref):
        if not (workitems / f"{ref}.yaml").is_file():
            drifts.append(f"{jid}: slice '{ref}' no existe en work-items/ (¿bootstrap pendiente?)")
        return
    if STEP_REF_RE.match(ref):
        if not any(workitems.glob(f"{ref}-T*.yaml")):
            drifts.append(f"{jid}: step '{ref}' no tiene ninguna task en work-items/ (¿bootstrap pendiente?)")
        return
    if PHASE_REF_RE.match(ref):
        if not (phases / f"{ref}.yaml").is_file():
            drifts.append(f"{jid}: phase '{ref}' no existe en orchestrator-state/tasks/phases/")
        return
    drifts.append(f"{jid}: slice '{ref}' no es ID válido — usa P0X-S0Y-T00Z, rango, P0X-S0Y o P0X")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = project_root()
    instructions = root / "docs/source-of-truth/instrucciones.md"
    guides = sorted((root / "docs/source-of-truth").glob("*_TECHNICAL_GUIDE.md"))
    if not instructions.is_file():
        fail(f"No existe {instructions}")
    if len(guides) != 1:
        fail("No encuentro exactamente 1 *_TECHNICAL_GUIDE.md filled en docs/source-of-truth/")
    guide_text = guides[0].read_text(encoding="utf-8", errors="replace").replace(r"\|", "|")
    start_line, rows, header_errors = find_matrix_table(instructions.read_text(encoding="utf-8", errors="replace"))
    if header_errors:
        for err in header_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    if start_line is None:
        if args.strict:
            fail(f"No se encontró la sección Journey Coverage Matrix en {instructions} (--strict)")
        log("Sección Journey Coverage Matrix no presente en instrucciones.md.")
        return 0
    if not rows:
        log("Matriz presente pero sin filas. Nada que validar.")
        return 0

    log(f"Detectadas {len(rows)} journeys en la matriz.")
    print("\n==> Validando referencias cruzadas...\n")
    drifts: list[str] = []

    for row in rows:
        jid = row.get("id", "")
        screens = row.get("screens", "")
        endpoints = row.get("endpoints", "")
        tables = row.get("tables", "")
        slices = row.get("slices", "")
        if args.verbose:
            print(f"  · [{jid}] processing")

        for screen in split_list(screens, arrows=True):
            if is_none(screen):
                continue
            screen_key = screen.split()[0] if screen.split() else screen
            if screen not in guide_text and screen_key not in guide_text:
                drifts.append(f"{jid}: pantalla '{screen}' no encontrada en TECHNICAL_GUIDE (§6.1 rutas o widgets)")

        for endpoint in split_list(endpoints):
            if is_none(endpoint):
                continue
            endpoint = strip_cell(endpoint)
            if METHOD_RE.match(endpoint):
                parts = endpoint.split()
                path = parts[1] if len(parts) > 1 else ""
            else:
                path = endpoint
            if path:
                if path.endswith("*"):
                    found = path[:-1] in guide_text
                else:
                    found = path in guide_text
                if not found:
                    drifts.append(f"{jid}: endpoint '{endpoint}' no encontrado en TECHNICAL_GUIDE (§6.2 endpoints)")

        for table in split_list(tables):
            if is_none(table) or table.startswith("auth.") or table.startswith("storage."):
                continue
            if table not in guide_text:
                drifts.append(f"{jid}: tabla DB '{table}' no encontrada en TECHNICAL_GUIDE (§10.3 schema)")

        for slice_ref in split_list(slices):
            validate_slice(slice_ref, jid, root, drifts)

    if drifts:
        print(f"❌ Journey matrix DRIFT — {len(drifts)} inconsistencias detectadas:\n")
        for drift in drifts:
            print(f"  ❌ {drift}")
        print("\nCómo arreglar:")
        print("  1. Si la celda apunta a algo que SÍ existe pero con otro nombre → renombra en la matriz.")
        print("  2. Si la celda apunta a algo que aún no existe → créalo en su sección canónica y actualiza la matriz.")
        print("  3. Si la slice no existe pero ya está en CHECKLIST → corre bootstrap_source_of_truth.py --refresh.")
        return 1

    log(f"✓ Journey matrix coherent — {len(rows)} journeys validadas, 0 drifts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
