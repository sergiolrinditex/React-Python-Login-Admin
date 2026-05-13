#!/usr/bin/env python3
"""Smoke test the three template profiles by generating random-ish apps.

The goal is not to build product code. It proves that source-of-truth packs
compatible with each profile can be reset and bootstrapped into registry/tasks/waves,
checked for journey/wiring drift, code-generated into API contracts, and fed to
/next-wave without global journey-gate deadlocks.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "docs" / "reports" / "TEMPLATE_SMOKE_REPORT.json"
TEMPLATE_FILES = [
    "instrucciones.template.md",
    "PROJECT_TECHNICAL_GUIDE.template.md",
    "PROJECT_IMPLEMENTATION_CHECKLIST.template.md",
    "UX_CONTRACT.template.md",
    "STACK_PROFILE.template.yaml",
]


@dataclass(frozen=True)
class App:
    profile: str
    name: str
    prefix: str
    domain: str
    entity: str
    route: str
    endpoint_base: str


APPS = [
    App("minimal", "PocketPantry", "POCKETPANTRY", "pantry", "pantry_items", "/pantry", "/api/v1/pantry-items"),
    App("minimal", "TrailLog", "TRAILLOG", "trail", "trail_entries", "/trails", "/api/v1/trail-entries"),
    App("large-without-base", "CivicPulse", "CIVICPULSE", "proposal", "proposals", "/proposals", "/api/v1/proposals"),
    App("large-without-base", "ClinicFlow", "CLINICFLOW", "appointment", "appointments", "/appointments", "/api/v1/appointments"),
    App("large-with-base", "InvoicePilot", "INVOICEPILOT", "invoice", "invoices", "/invoices", "/api/v1/invoices"),
    App("large-with-base", "EventOps", "EVENTOPS", "event", "events", "/events", "/api/v1/events"),
]


def _copy_repo(dst: Path) -> None:
    def ignore(dir_name: str, names: list[str]):
        ignored = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store", "__MACOSX"}
        if Path(dir_name).name == "api-contracts":
            return set(names)
        return {n for n in names if n in ignored or n.endswith(".pyc")}
    shutil.copytree(ROOT, dst, ignore=ignore)


def _write_source_docs(project: Path, app: App) -> None:
    sot = project / "docs" / "source-of-truth"
    if sot.exists():
        shutil.rmtree(sot)
    sot.mkdir(parents=True)
    docs = build_docs(app)
    for name, body in docs.items():
        (sot / name).write_text(body, encoding="utf-8")


def stack_profile(app: App) -> str:
    if app.profile == "large-with-base":
        return """profile_version: stack-profile-v1
frontend:
  language: typescript
  framework: react
  module_root: web/src
  theme_root: web/src/theme
  test_cmd: pnpm test -- --run
  dev_cmd: pnpm dev
  visual_check: pnpm test:visual
backend:
  language: typescript
  framework: node-fastify
  module_root: server/src
  test_cmd: pnpm test:server
  dev_cmd: pnpm dev:server
  health_url: http://localhost:3000/health
db:
  engine: postgres
  migrate_cmd: pnpm db:migrate
  seed_cmd: none
git_workflow: push-to-main
design_tokens_enforcer: design_tokens_v1
"""
    if app.profile == "large-without-base":
        return """profile_version: stack-profile-v1
frontend:
  language: typescript
  framework: react
  module_root: web/src
  theme_root: web/src/theme
  test_cmd: pnpm test -- --run
  dev_cmd: pnpm dev
  visual_check: pnpm test:visual
backend:
  language: typescript
  framework: node-fastify
  module_root: server/src
  test_cmd: pnpm test:server
  dev_cmd: pnpm dev:server
  health_url: http://localhost:3000/health
db:
  engine: postgres
  migrate_cmd: pnpm db:migrate
  seed_cmd: none
git_workflow: push-to-main
design_tokens_enforcer: design_tokens_v1
"""
    return """profile_version: stack-profile-v1
frontend:
  language: typescript
  framework: react
  module_root: web/src
  theme_root: web/src/theme
  test_cmd: pnpm test -- --run
  dev_cmd: pnpm dev
  visual_check: pnpm test:visual
backend:
  language: typescript
  framework: node-fastify
  module_root: server/src
  test_cmd: pnpm test:server
  dev_cmd: pnpm dev:server
  health_url: http://localhost:3000/health
db:
  engine: sqlite
  migrate_cmd: pnpm db:migrate
  seed_cmd: none
git_workflow: push-to-main
design_tokens_enforcer: design_tokens_v1
"""


def instructions(app: App, journey_rows: list[list[str]]) -> str:
    rows = "\n".join("| " + " | ".join(row) + " |" for row in journey_rows)
    return f"""# {app.name} — Instrucciones source-of-truth

## 1. Identidad

- Nombre: {app.name}
- Perfil template: {app.profile}
- Problema: coordinar el dominio `{app.domain}` con datos persistidos y un flujo verificable.
- Usuario objetivo: operador interno que necesita completar el journey sin drift entre UI, API y DB.

## 2. Alcance funcional

| Feature ID | Feature | Pantalla/Ruta | Endpoint principal | Tabla/side effect | Valor |
|---|---|---|---|---|---|
| F1 | Crear {app.domain} | {app.route} | POST {app.endpoint_base} | {app.entity} | registro persistido |
| F2 | Revisar {app.domain} | {app.route}/:id | PATCH {app.endpoint_base}/{{id}} | {app.entity} | actualización controlada |

## 3. Journey Coverage Matrix

| ID | Milestone | Pantallas/Screens | Acciones/Actions | Endpoints | Tablas/Tables | Estado cliente/Client state | Slices | Verificación/Verification |
|---|---|---|---|---|---|---|---|---|
{rows}

## 4. Milestones

| Milestone | Objetivo | Criterio visible | Journeys |
|---|---|---|---|
| M1 | Primer flujo usable | usuario completa creación con datos reales proporcionados | {journey_rows[0][0]} |
| M2 | Revisión usable | usuario modifica un registro existente | {journey_rows[-1][0]} |

## 5. Reglas de verificación real

- Verify-slice y verify-journey usan datos persistidos, reset reproducible y evidencia front -> back -> DB.
- Los datos decorativos, inventados o no proporcionados no cierran tareas humanas.
"""


def guide(app: App, route_rows: list[list[str]], api_rows: list[list[str]]) -> str:
    rr = "\n".join("| " + " | ".join(r) + " |" for r in route_rows)
    ar = "\n".join("| " + " | ".join(r) + " |" for r in api_rows)
    stack_note = "stack heredado del STACK_PROFILE.yaml del baseline existente" if app.profile == "large-with-base" else "AnyStack declarado por STACK_PROFILE.yaml"
    return f"""# {app.name} — Technical Guide

## 1. Stack

{stack_note}. Los agentes deben leer `STACK_PROFILE.yaml` antes de asumir rutas, widgets, handlers o comandos.

## 2. Contrato front -> back -> DB

### 2.1 Rutas/pantallas nuevas

| Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/provider | Estados UI obligatorios | Next action | Slice ID | Descripción |
|---|---|---|---|---|---|---|---|---|---|
{rr}

### 2.2 Endpoints API nuevos

| Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
|---|---|---|---|---|---|---|---|---|
{ar}

### 2.3 Modelos / tablas

| Tabla | Campos mínimos | Índices / constraints | Slices |
|---|---|---|---|
| {app.entity} | id, title, status, created_at, updated_at | id pk, status indexed | P00-S01-T001 |

## 3. Verification Data Contract

| Flow/Journey | Persona/Rol | Datos reales/proporcionados requeridos | Carga de datos reales proporcionados | Reset/Cleanup | Slices/Journeys |
|---|---|---|---|---|---|
| principal | operator | una fila real de {app.entity} creada por API | datos reales proporcionados por usuario/equipo | truncate {app.entity} | all / all journeys |

## 4. Testing mínimo

| Capa | Comando | Evidencia esperada |
|---|---|---|
| API | pnpm test:server / pytest api/tests | endpoint persiste y devuelve JSON |
| Frontend | pnpm test -- --run / flutter test | estados loading, empty, error, success |
| Contracts | ./scripts/generate-api-contracts.sh --validate-only | OpenAPI y stubs frescos |
"""


def checklist(app: App, rows: list[list[str]], phases: list[tuple[str, str, list[str]]]) -> str:
    reg = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    phase_text = []
    for phase_id, title, task_ids in phases:
        n = int(phase_id[1:]) if phase_id.startswith("P") and phase_id[1:].isdigit() else 0
        phase_text.append(f"## Phase {n} — {title}\n")
        for tid in task_ids:
            phase_text.append(f"### Step {tid.rsplit('-T', 1)[0]} — {tid}\n- [ ] {tid}\n")
    return f"""# {app.name} — Implementation Checklist

## Screen/Journey Lane Redactor Contract

This generated app is intentionally grouped by screen/journey lane, not by isolated API phase followed by isolated UI phase. API/data slices feed named screens and journeys; connected screen slices prove UX states with datos reales/proporcionados; journey verification closes the visible flow.

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
{reg}

{''.join(phase_text)}

## Runtime Follow-up Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""


def ux_contract(app: App, journey_ids: list[str]) -> str:
    rows = "\n".join(f"| {app.route}{'/'+jid.lower() if idx else ''} | {app.name}{jid}Page | {jid} | loading, empty, error_network, error_validation, success | {app.entity} persisted row |" for idx, jid in enumerate(journey_ids))
    return f"""# UX_CONTRACT — {app.name}

## 1. UX purpose

Permite completar journeys de {app.domain} con feedback claro, estados marginales y datos persistidos.

## 2. Persona

| Persona | Goal | Journey | Data required |
|---|---|---|---|
| Operator | completar workflow de {app.domain} | {', '.join(journey_ids)} | {app.entity} |

## 3. Screen inventory

| Route | Screen/Page | Primary journey refs | Required UI states | Real data contract |
|---|---|---|---|---|
{rows}

## 4. Verification rules

Los estados UI obligatorios son loading, empty, error_network, error_validation y success salvo N/A explícito en el handoff.
"""


def minimal_docs(app: App) -> dict[str, str]:
    rows = [
        ["P00-S01-T001", "db", f"{app.entity} schema", "Step 0.1", "v1", "planned", "low", "auto", "—", "db:migrations", "server/src/db/**", "—", "—", "—", app.entity, "§2#F1", "§2.3#schema", "schema created", "python3 -B -S -c \"print(\'db-ok\')\""],
        ["P01-S01-T001", "api", f"POST {app.endpoint_base}", "Step 1.1", "v1", "planned", "medium", "human", "P00-S01-T001", f"screen-journey:{app.domain}; api", "server/src/**", "J1", app.route, f"POST {app.endpoint_base}", app.entity, "§3#J1", f"§2.2#POST-{app.domain}", "API contract feeding J1 screen persists row", "pnpm test:server"],
        ["P01-S01-T002", "frontend", f"{app.name} connected screen", "Step 1.1", "v1", "planned", "medium", "human", "P01-S01-T001", f"screen-journey:{app.domain}; front", "web/src/**", "J1", app.route, f"POST {app.endpoint_base}", "—", "§3#J1", f"§2.1#{app.route}", "connected screen proves loading/empty/error/success states", "/verify-slice with persisted data"],
        ["P01-S02-T001", "journey", "J1 e2e", "Step 1.2", "v1", "planned", "high", "human", "P01-S01-T002", f"screen-journey:{app.domain}; verify", "orchestrator-state/tasks/journey-handoffs/**", "J1", app.route, f"POST {app.endpoint_base}", app.entity, "§3#J1", "§3 Verification Data Contract", "J1 verified front -> back -> DB", "/verify-journey J1"],
    ]
    phases = [
        ("P00", "Product foundation", ["P00-S01-T001"]),
        ("P01", "J1 screen/journey lane", ["P01-S01-T001", "P01-S01-T002", "P01-S02-T001"]),
    ]
    journey_rows = [["J1", "M1", app.route, "create", f"POST {app.endpoint_base}", app.entity, f"{app.domain}Store", "P01-S01-T001,P01-S01-T002,P01-S02-T001", "/verify-journey J1"]]
    route_rows = [[app.route, f"{app.name}Page", "session", "J1", f"POST {app.endpoint_base}", f"{app.domain}Store", "loading, empty, error_network, error_validation, success", "create", "P01-S01-T002", "main screen/journey lane"]]
    api_rows = [["POST", app.endpoint_base, f"Create{app.domain.title()}Request", f"{app.domain.title()}Response", "session", "400,401,500", "J1 connected screen", app.entity, "P01-S01-T001"]]
    return {
        "instrucciones.md": instructions(app, journey_rows),
        f"{app.prefix}_TECHNICAL_GUIDE.md": guide(app, route_rows, api_rows),
        f"{app.prefix}_IMPLEMENTATION_CHECKLIST.md": checklist(app, rows, phases),
        "UX_CONTRACT.md": ux_contract(app, ["J1"]),
        "STACK_PROFILE.yaml": stack_profile(app),
    }


def large_without_base_docs(app: App) -> dict[str, str]:
    rows = [
        ["P00-S01-T001", "db", f"{app.entity} schema", "Step 0.1", "v1", "planned", "low", "auto", "—", "db:migrations", "server/src/db/**", "—", "—", "—", app.entity, "§2#F1", "§2.3#schema", "schema created", "python3 -B -S -c \"print(\'db-ok\')\""],
        ["P01-S01-T001", "api", f"POST {app.endpoint_base}", "Step 1.1", "v1", "planned", "medium", "human", "P00-S01-T001", f"screen-journey:{app.domain}; api", "server/src/**", "J1", app.route, f"POST {app.endpoint_base}", app.entity, "§3#J1", f"§2.2#POST-{app.domain}", "create API feeds dashboard screen", "pnpm test:server"],
        ["P01-S01-T002", "api", f"GET {app.endpoint_base}", "Step 1.1", "v1", "planned", "low", "auto", "P00-S01-T001", f"screen-journey:{app.domain}; api", "server/src/**", "J1,J2", app.route, f"GET {app.endpoint_base}", app.entity, "§3#J1", f"§2.2#GET-{app.domain}", "list API feeds dashboard and detail", "python3 -B -S -c \"print(\'api-list-ok\')\""],
        ["P01-S01-T003", "frontend", f"{app.name} dashboard connected screen", "Step 1.1", "v1", "planned", "medium", "human", "P01-S01-T001,P01-S01-T002", f"screen-journey:{app.domain}; front; navigation", "web/src/**", "J1", app.route, f"GET {app.endpoint_base}, POST {app.endpoint_base}", "—", "§3#J1", f"§2.1#{app.route}", "dashboard uses real API and required UX states", "/verify-slice with persisted data"],
        ["P01-S02-T001", "frontend", f"{app.name} detail connected screen", "Step 1.2", "v1", "planned", "medium", "human", "P01-S01-T002", f"screen-journey:{app.domain}; front; navigation", "web/src/**", "J2", app.route + "/:id", f"GET {app.endpoint_base}", "—", "§3#J2", f"§2.1#{app.route}-detail", "detail screen consumes list data and UX states", "/verify-slice detail"],
        ["P02-S01-T001", "journey", "J1 create/list", "Step 2.1", "v1", "planned", "high", "human", "P01-S01-T003", f"screen-journey:{app.domain}; verify", "orchestrator-state/tasks/journey-handoffs/**", "J1", app.route, f"POST {app.endpoint_base}, GET {app.endpoint_base}", app.entity, "§3#J1", "§3 Verification Data Contract", "J1 verified visible front -> back -> DB", "/verify-journey J1"],
        ["P02-S02-T001", "journey", "J2 detail", "Step 2.2", "v1", "planned", "high", "human", "P01-S02-T001", f"screen-journey:{app.domain}; verify", "orchestrator-state/tasks/journey-handoffs/**", "J2", app.route + "/:id", f"GET {app.endpoint_base}", app.entity, "§3#J2", "§3 Verification Data Contract", "J2 verified visible front -> back -> DB", "/verify-journey J2"],
        ["P03-S01-T001", "release", f"{app.name} release gate", "Step 3.1", "v1", "planned", "medium", "human", "P02-S01-T001,P02-S02-T001", "release", "docs/**; .github/**", "J1,J2", "—", "—", "—", "§4#M2", "§4 Testing mínimo", "release checklist passes", "./scripts/run-all-tests.sh lint"],
    ]
    phases = [
        ("P00", "Product foundation", ["P00-S01-T001"]),
        ("P01", "Primary screen/journey lanes", ["P01-S01-T001", "P01-S01-T002", "P01-S01-T003", "P01-S02-T001"]),
        ("P02", "Visible journey verification", ["P02-S01-T001", "P02-S02-T001"]),
        ("P03", "Release", ["P03-S01-T001"]),
    ]
    journey_rows = [
        ["J1", "M1", app.route, "create and list", f"POST {app.endpoint_base}, GET {app.endpoint_base}", app.entity, f"{app.domain}Store", "P01-S01-T001,P01-S01-T002,P01-S01-T003,P02-S01-T001", "/verify-journey J1"],
        ["J2", "M2", app.route + " -> " + app.route + "/:id", "open detail from list", f"GET {app.endpoint_base}", app.entity, f"{app.domain}Store", "P01-S01-T002,P01-S02-T001,P02-S02-T001", "/verify-journey J2"],
    ]
    route_rows = [
        [app.route, f"{app.name}Dashboard", "session", "J1", f"GET {app.endpoint_base}, POST {app.endpoint_base}", f"{app.domain}Store", "loading, empty, error_network, error_validation, success", "open detail", "P01-S01-T003", "dashboard screen/journey lane"],
        [app.route + "/:id", f"{app.name}Detail", "session", "J2", f"GET {app.endpoint_base}", f"{app.domain}Store", "loading, empty, error_network, success", "return", "P01-S02-T001", "detail screen/journey lane"],
    ]
    api_rows = [
        ["POST", app.endpoint_base, f"Create{app.domain.title()}Request", f"{app.domain.title()}Response", "session", "400,401,500", "J1 connected screen", app.entity, "P01-S01-T001"],
        ["GET", app.endpoint_base, "query", f"{app.domain.title()}ListResponse", "session", "401,500", "dashboard/detail connected screens", app.entity, "P01-S01-T002"],
    ]
    return {
        "instrucciones.md": instructions(app, journey_rows),
        f"{app.prefix}_TECHNICAL_GUIDE.md": guide(app, route_rows, api_rows),
        f"{app.prefix}_IMPLEMENTATION_CHECKLIST.md": checklist(app, rows, phases),
        "UX_CONTRACT.md": ux_contract(app, ["J1", "J2"]),
        "STACK_PROFILE.yaml": stack_profile(app),
    }


def large_with_base_docs(app: App) -> dict[str, str]:
    rows = [
        ["P01-S01-T001", "api", "GET /api/v1/session", "Step 1.1", "v0", "done", "low", "auto", "—", "api:baseline-session", "server/src/**", "—", "/dashboard", "GET /api/v1/session", "sessions", "§baseline", "§baselineline#session", "existing baseline session endpoint already built", "pnpm test:server"],
        ["P15-S01-T001", "db", f"{app.entity} schema", "Step 15.1", "v1", "planned", "low", "auto", "P01-S01-T001", f"screen-journey:{app.domain}; db", "server/src/db/migrations/**", "J901", app.route, "—", app.entity, "§2#F1", "§2.3#schema", "schema supports create/edit screens", "python3 -B -S -c \"print(\'db-ok\')\""],
        ["P15-S01-T002", "api", f"POST {app.endpoint_base}", "Step 15.1", "v1", "planned", "medium", "human", "P15-S01-T001", f"screen-journey:{app.domain}; api", "server/src/**", "J901", app.route, f"POST {app.endpoint_base}", app.entity, "§3#J901", f"§2.2#POST-{app.domain}", "create endpoint feeds existing baseline screen", "pnpm test:server"],
        ["P15-S01-T003", "frontend", f"{app.name} dashboard connected screen", "Step 15.1", "v1", "planned", "medium", "human", "P15-S01-T002", f"screen-journey:{app.domain}; front; router", "web/src/**", "J901", app.route, f"POST {app.endpoint_base}", "—", "§3#J901", f"§2.1#{app.route}", "dashboard uses existing baseline shell with required UX states", "/verify-slice with device"],
        ["P15-S02-T001", "api", f"PATCH {app.endpoint_base}/{{id}}", "Step 15.2", "v1", "planned", "medium", "human", "P15-S01-T002", f"screen-journey:{app.domain}; api", "server/src/**", "J902", app.route + "/:id", f"PATCH {app.endpoint_base}/{{id}}", app.entity, "§3#J902", f"§2.2#PATCH-{app.domain}", "update endpoint feeds detail screen", "pnpm test:server"],
        ["P15-S02-T002", "frontend", f"{app.name} detail connected screen", "Step 15.2", "v1", "planned", "medium", "human", "P15-S01-T003,P15-S02-T001", f"screen-journey:{app.domain}; front; router", "web/src/**", "J902", app.route + "/:id", f"PATCH {app.endpoint_base}/{{id}}", "—", "§3#J902", f"§2.1#{app.route}-detail", "detail uses generated Dart client and UX states", "/verify-slice detail"],
        ["P16-S01-T001", "journey", "J901/J902 existing baseline journeys", "Step 16.1", "v1", "planned", "high", "human", "P15-S02-T002", f"screen-journey:{app.domain}; verify", "orchestrator-state/tasks/journey-handoffs/**", "J901,J902", app.route, f"POST {app.endpoint_base}, PATCH {app.endpoint_base}/{{id}}", app.entity, "§3#J901", "§3 Verification Data Contract", "both journeys verified visible front -> back -> DB", "/verify-journey J901 && /verify-journey J902"],
    ]
    phases = [
        ("P01", "existing product baseline shell", ["P01-S01-T001"]),
        ("P15", "Feature screen/journey lanes", ["P15-S01-T001", "P15-S01-T002", "P15-S01-T003", "P15-S02-T001", "P15-S02-T002"]),
        ("P16", "Journey verification gate", ["P16-S01-T001"]),
    ]
    journey_rows = [
        ["J901", "M1", app.route, "create in existing baseline shell", f"POST {app.endpoint_base}", app.entity, f"{app.domain}Provider", "P15-S01-T002,P15-S01-T003,P16-S01-T001", "/verify-journey J901"],
        ["J902", "M2", app.route + " -> " + app.route + "/:id", "edit existing row", f"PATCH {app.endpoint_base}/{{id}}", app.entity, f"{app.domain}Provider", "P15-S02-T001,P15-S02-T002,P16-S01-T001", "/verify-journey J902"],
    ]
    route_rows = [
        [app.route, f"{app.name}Page", "session", "J901", f"POST {app.endpoint_base}", f"{app.domain}Provider", "loading, empty, error_network, error_validation, success", "open detail", "P15-S01-T003", "existing baseline screen/journey lane"],
        [app.route + "/:id", f"{app.name}DetailPage", "session", "J902", f"PATCH {app.endpoint_base}/{{id}}", f"{app.domain}Provider", "loading, empty, error_network, error_validation, success", "back", "P15-S02-T002", "existing baseline detail screen/journey lane"],
    ]
    api_rows = [
        ["POST", app.endpoint_base, f"Create{app.domain.title()}Request", f"{app.domain.title()}Response", "session", "400,401,500", "J901 connected screen", app.entity, "P15-S01-T002"],
        ["PATCH", app.endpoint_base + "/{id}", f"Update{app.domain.title()}Request", f"{app.domain.title()}Response", "session", "400,401,404,500", "J902 connected screen", app.entity, "P15-S02-T001"],
    ]
    return {
        "instrucciones.md": instructions(app, journey_rows),
        f"{app.prefix}_TECHNICAL_GUIDE.md": guide(app, route_rows, api_rows),
        f"{app.prefix}_IMPLEMENTATION_CHECKLIST.md": checklist(app, rows, phases),
        "UX_CONTRACT.md": ux_contract(app, ["J901", "J902"]),
        "STACK_PROFILE.yaml": stack_profile(app),
    }


def build_docs(app: App) -> dict[str, str]:
    if app.profile == "minimal":
        return minimal_docs(app)
    if app.profile == "large-with-base":
        return large_with_base_docs(app)
    return large_without_base_docs(app)


def _run(project: Path, cmd: list[str]) -> dict[str, Any]:
    start = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
    out = out or ""
    return {
        "cmd": " ".join(cmd),
        "returncode": 124 if timed_out else proc.returncode,
        "seconds": round(time.time() - start, 3),
        "tail": (out + ("\n[TIMEOUT after 90s]" if timed_out else ""))[-1800:],
    }


def _validate_template_layout() -> list[str]:
    errors: list[str] = []
    root = ROOT / "docs" / "templates"
    dirs = sorted(p.name for p in root.iterdir() if p.is_dir())
    if dirs != ["large-with-base", "large-without-base", "minimal"]:
        errors.append(f"docs/templates must contain exactly the three profile dirs; got {dirs}")
    loose = [p.name for p in root.iterdir() if p.is_file()]
    if loose:
        errors.append(f"docs/templates has loose files: {loose}")
    for profile in dirs:
        files = sorted(p.name for p in (root / profile).iterdir() if p.is_file())
        if sorted(TEMPLATE_FILES) != files:
            errors.append(f"{profile} template file set mismatch: {files}")
    return errors


def smoke_app(temp_root: Path, app: App, keep: bool) -> dict[str, Any]:
    project = temp_root / f"{app.profile}-{app.name}"
    print(f"[smoke] preparing {app.profile} / {app.name}", file=sys.stderr, flush=True)
    _copy_repo(project)
    _write_source_docs(project, app)
    checks = []
    for cmd in [
        ["./scripts/reset-for-new-project.sh"],
        ["python3", "-B", "-S", ".claude/bin/bootstrap_source_of_truth.py", "--validate-only"],
        ["python3", "-B", "-S", ".claude/bin/bootstrap_source_of_truth.py", "--refresh", "--reset-runtime-state"],
        ["./scripts/check-task-dag.sh", "--strict"],
        ["./scripts/check-journey-matrix.sh", "--strict"],
        ["./scripts/check-wiring-contract.sh", "--strict", "--require-new-template-columns"],
        ["./scripts/generate-api-contracts.sh", "--validate-only"],
        ["python3", "-B", "-S", ".claude/bin/next_wave.py", "--json"],
    ]:
        print(f"[smoke] {app.profile}-{app.name}: {' '.join(cmd)}", file=sys.stderr, flush=True)
        check = _run(project, cmd)
        print(f"[smoke] {app.profile}-{app.name}: rc={check['returncode']} seconds={check['seconds']}", file=sys.stderr, flush=True)
        checks.append(check)
        if check["returncode"] != 0:
            break
    registry_path = project / "orchestrator-state" / "tasks" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    ok = all(c["returncode"] == 0 for c in checks)
    result = {
        "profile": app.profile,
        "app": app.name,
        "prefix": app.prefix,
        "ok": ok,
        "project": str(project) if keep else "(removed)",
        "tasks": len(registry.get("tasks", []) or []),
        "journeys": len(registry.get("journeys", []) or []),
        "dag_mode": (registry.get("task_dag") or {}).get("mode"),
        "waves": len((registry.get("task_dag") or {}).get("topological_levels") or []),
        "checks": checks,
    }
    if not keep:
        shutil.rmtree(project, ignore_errors=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test all docs/templates profiles.")
    parser.add_argument("--keep", action="store_true", help="Keep temporary projects for inspection.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help="Write the JSON smoke report to this path. Use 'none' to disable.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="APP_OR_PROFILE",
        help="Run only matching app names or profiles. Can be repeated.",
    )
    args = parser.parse_args()
    layout_errors = _validate_template_layout()
    wanted = {item.lower() for item in args.only}
    selected_apps = [
        app for app in APPS
        if not wanted or app.name.lower() in wanted or app.profile.lower() in wanted
    ]
    if not selected_apps:
        parser.error("--only did not match any app name or profile")
    temp_root = Path(tempfile.mkdtemp(prefix="orq-template-smoke-"))
    results = [smoke_app(temp_root, app, args.keep) for app in selected_apps]
    ok = not layout_errors and all(r["ok"] for r in results)
    payload = {"ok": ok, "temp_root": str(temp_root) if args.keep else "(removed)", "layout_errors": layout_errors, "selected": [app.name for app in selected_apps], "apps": results}
    report_path = None if str(args.report).lower() == "none" else Path(args.report)
    if report_path is not None:
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload["report_path"] = str(report_path)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.keep:
        shutil.rmtree(temp_root, ignore_errors=True)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Template profile smoke:", "OK" if ok else "FAIL")
        if layout_errors:
            for e in layout_errors:
                print("ERROR:", e)
        for r in results:
            print(f"- {r['profile']} / {r['app']}: ok={r['ok']} tasks={r['tasks']} journeys={r['journeys']} waves={r['waves']} dag={r['dag_mode']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
