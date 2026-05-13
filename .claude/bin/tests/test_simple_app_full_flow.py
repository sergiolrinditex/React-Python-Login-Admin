from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parents[1]


def write_simple_app_docs(root: Path) -> None:
    sot = root / "docs" / "source-of-truth"
    sot.mkdir(parents=True, exist_ok=True)
    (sot / "STACK_PROFILE.yaml").write_text(
        """profile_version: stack-profile-v1
frontend:
  language: dart
  framework: flutter
  module_root: app/lib
  theme_root: app/lib/core/theme
  test_cmd: flutter test
  dev_cmd: flutter run -d chrome
  visual_check: browser
backend:
  language: python
  framework: fastapi
  module_root: api/src
  test_cmd: pytest
  dev_cmd: uvicorn src.main:app --reload
  health_url: http://localhost:8000/health
db:
  engine: postgres
  migrate_cmd: alembic upgrade head
  seed_cmd: python -m seeds.simple_tasks --profile prod_like
git_workflow: push-to-main
design_tokens_enforcer: design_tokens_v1
""",
        encoding="utf-8",
    )
    (sot / "UX_CONTRACT.md").write_text(
        """# UX_CONTRACT — SimpleTasks

## 1. UX purpose
Verify a real task list flow with persisted task rows.

## 2. Persona
| Persona | Goal | Journey | Data required |
|---|---|---|---|
| QA user | Login and inspect tasks | J101 | confirmed user + persisted tasks |

## 3. Screen inventory
| Route | Screen/Page | Primary journey refs | Required UI states | Real data contract |
|---|---|---|---|---|
| /login | LoginPage | J101 | idle,loading,error_validation,error_network,success | real user credentials |
| /tasks | TasksPage | J101 | loading,empty,error_network,success | persisted tasks rows |
| /tasks/:id | TaskDetailPage | J101 | loading,not_found,permission_denied,error_network,success | persisted task row |
""",
        encoding="utf-8",
    )

    (sot / "instrucciones.md").write_text(
        """# SimpleTasks — instrucciones

## 3.7 Journey Coverage Matrix

| ID | Milestone | Pantallas | Acciones | Endpoints | Tablas DB | Estado cliente | Slices | Verificación |
|---|---|---|---|---|---|---|---|---|
| J101 | M1 | LoginPage → TasksPage → TaskDetailPage | login, listar, abrir detalle | `POST /auth/login`, `GET /api/v1/tasks`, `GET /api/v1/tasks/{id}` | `users`, `tasks` | `authStateProvider`, `tasksProvider`, `taskDetailProvider` | `P01-S01-T001`, `P02-S01-T001`, `P03-S01-T001`, `P03-S02-T001` | `/verify-journey J101` |
""",
        encoding="utf-8",
    )
    (sot / "SIMPLEAPP_TECHNICAL_GUIDE.md").write_text(
        """# SimpleTasks Technical Guide

## 6. Interfaces

### 6.1 Rutas Flutter nuevas

| Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/provider | Estados UI obligatorios | Next action | Slice ID | Descripción |
|---|---|---|---|---|---|---|---|---|---|
| /login | LoginPage | No | J101 | POST /auth/login | authStateProvider | idle, loading, error_validation, error_network, success | /tasks | P01-S01-T001 | Login real contra backend sandbox |
| /tasks | TasksPage | Sí | J101 | GET /api/v1/tasks | tasksProvider | loading, empty, error_network, success | /tasks/{id} | P03-S01-T001 | Lista tareas persistidas |
| /tasks/:id | TaskDetailPage | Sí | J101 | GET /api/v1/tasks/{id} | taskDetailProvider | loading, not_found, permission_denied, error_network, success | volver a lista | P03-S02-T001 | Detalle tarea persistida |

### 6.2 Endpoints API nuevos

| Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
|---|---|---|---|---|---|---|---|---|
| POST | /auth/login | email/password | `{data:{session,user}}` | No | 400, 401 | LoginPage / J101 | users read | P01-S01-T001 |
| GET | /api/v1/tasks | cursor, limit | `{data:[Task]}` | Sí | 401 | TasksPage / J101 | tasks read | P02-S01-T001 |
| GET | /api/v1/tasks/{id} | — | `{data:Task}` | Sí | 401, 403, 404 | TaskDetailPage / J101 | tasks read | P02-S02-T001 |

### 6.5 Verification Data Contract

| Flow/Journey | Persona/Rol | Datos reales/proporcionados requeridos | Carga de datos reales/proporcionados permitida | Reset/Cleanup | Slices/Journeys |
|---|---|---|---|---|---|
| J101 | usuario QA tareas | usuario confirmado + 2 tareas persistidas con owner_id real | `python -m seeds.simple_tasks --profile prod_like` | truncate tasks del usuario QA + logout | P01-S01-T001, P02-S01-T001, P02-S02-T001, P03-S01-T001, P03-S02-T001 / J101 |

## 10. Persistencia

### 10.3 Schema

tasks(id, owner_id, title, status, created_at)
""",
        encoding="utf-8",
    )
    (sot / "SIMPLEAPP_IMPLEMENTATION_CHECKLIST.md").write_text(
        """# SimpleTasks Implementation Checklist

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | db | 0001_tasks.py | Step 0.1 | v1 | planned | low | auto | — | db:migrations | api/alembic/versions/*tasks*; api/tests/**/tasks* | — | — | — | tasks | §3.1 | §10.3#tasks | migración up/down + índices por owner | pytest api/tests/integration/test_tasks_migration.py |
| P01-S01-T001 | api | POST /auth/login | Step 1.1 | v1 | planned | medium | human | P00-S01-T001 | api:auth | api/src/**/auth*.py; api/tests/**/auth* | J101 | LoginPage /login | POST /auth/login | users | §3.7#J101 | §6.2#POST-/auth/login | schema + integración real con cuenta sandbox | pytest api/tests/integration/test_auth_login.py |
| P02-S01-T001 | api | GET /api/v1/tasks | Step 2.1 | v1 | planned | medium | human | P00-S01-T001 | api:tasks | api/src/**/tasks*.py; api/tests/**/tasks* | J101 | TasksPage /tasks | GET /api/v1/tasks | tasks | §3.7#J101 | §6.2#GET-/api/v1/tasks | lista solo tareas del usuario | pytest api/tests/integration/test_tasks_list.py |
| P02-S02-T001 | api | GET /api/v1/tasks/{id} | Step 2.2 | v1 | planned | medium | human | P02-S01-T001 | api:tasks | api/src/**/tasks*.py; api/tests/**/tasks* | J101 | TaskDetailPage /tasks/:id | GET /api/v1/tasks/{id} | tasks | §3.7#J101 | §6.2#GET-/api/v1/tasks-id | 404/403/200 correctos | pytest api/tests/integration/test_tasks_detail.py |
| P03-S01-T001 | flutter | TasksPage | Step 3.1 | v1 | planned | medium | human | P02-S01-T001 | front:tasks, router | app/lib/features/tasks/**; app/test/**/tasks*; app/lib/core/router.dart | J101 | TasksPage /tasks | GET /api/v1/tasks | — | §3.7#J101 | §6.1#/tasks | UI states + provider real | /verify-slice con backend real sandbox |
| P03-S02-T001 | flutter | TaskDetailPage | Step 3.2 | v1 | planned | high | human | P02-S02-T001, P03-S01-T001 | front:tasks, router | app/lib/features/tasks/**; app/test/**/tasks*; app/lib/core/router.dart | J101 | TaskDetailPage /tasks/:id | GET /api/v1/tasks/{id} | — | §3.7#J101 | §6.1#/tasks/:id | detalle navega desde lista con dato persistido | /verify-slice + /verify-journey J101 |

## Phase 0 — DB foundation
### Step 0.1 — Tasks schema
- [ ] P00-S01-T001

## Phase 1 — Auth lane
### Step 1.1 — Login API
- [ ] P01-S01-T001

## Phase 2 — Tasks API lane
### Step 2.1 — List API
- [ ] P02-S01-T001
### Step 2.2 — Detail API
- [ ] P02-S02-T001

## Phase 3 — Tasks UI lane
### Step 3.1 — List UI
- [ ] P03-S01-T001
### Step 3.2 — Detail UI / journey close
- [ ] P03-S02-T001
""",
        encoding="utf-8",
    )


def run_py(script: str, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(root)
    return subprocess.run(
        [sys.executable, "-B", "-S", str(BIN / script), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


def test_simple_app_template_to_dag_flow(tmp_project):
    write_simple_app_docs(tmp_project)
    result = run_py("bootstrap_source_of_truth.py", tmp_project, "--refresh", "--json")
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["task_count"] == 6
    assert payload["journey_count"] == 1
    assert payload["task_dag_mode"] == "explicit_dag"
    assert payload["task_dag_wave_count"] == 4

    dag = run_py("check_task_dag.py", tmp_project, "--strict", "--json")
    assert dag.returncode == 0, dag.stderr + dag.stdout
    dag_payload = json.loads(dag.stdout)
    assert dag_payload["edge_count"] == 6
    assert dag_payload["wave_count"] == 4

    wiring = run_py("check_wiring_contract.py", tmp_project, "--strict", "--require-new-template-columns", "--json")
    assert wiring.returncode == 0, wiring.stderr + wiring.stdout
    wiring_payload = json.loads(wiring.stdout)
    assert wiring_payload["counts"] == {
        "routes": 3,
        "endpoints": 3,
        "registry_rows": 6,
        "journeys": 1,
        "verification_data_contract": 1,
    }

    registry = json.loads((tmp_project / "orchestrator-state" / "tasks" / "registry.json").read_text())
    assert registry["task_dag"]["canonical_source"] == "registry.tasks"
    assert registry["task_dag"]["source_digest"]
    assert all(t.get("product_increment") == "v1" for t in registry["tasks"])
    assert [len(level) for level in registry["task_dag"]["topological_levels"]] == [1, 2, 2, 1]
    task = next(t for t in registry["tasks"] if t["id"] == "P03-S01-T001")
    assert task["kind"] == "flutter"
    assert task["journey_refs"] == ["J101"]
    assert task["route"] == "TasksPage /tasks"
    assert task["endpoint"] == "GET /api/v1/tasks"
    assert "app/lib/features/tasks/**" in task["allowed_paths"]

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(tmp_project)
    design = subprocess.run(["bash", str(Path(__file__).resolve().parents[3] / "scripts" / "check-design-tokens.sh")], cwd=tmp_project, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, env=env)
    assert design.returncode == 0, design.stdout + design.stderr
    assert "no existe todavia" in design.stdout or "OK Design tokens" in design.stdout

    work_item = (tmp_project / "orchestrator-state" / "tasks" / "work-items" / "P03-S01-T001.yaml").read_text()
    assert "kind: \"flutter\"" in work_item
    assert "route: \"TasksPage /tasks\"" in work_item
    assert "endpoint: \"GET /api/v1/tasks\"" in work_item
