from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BIN = ROOT / ".claude" / "bin"
sys.path.insert(0, str(BIN))

from stack_profile import parse_simple_yaml, load_stack_profile


def test_stack_profile_parser_reads_nested_values():
    data = parse_simple_yaml("""
frontend:
  language: typescript
  framework: nextjs
  module_root: web/src
backend:
  health_url: http://localhost:3000/api/health
  test_cmd: pnpm test
 git_workflow: pr-flow
""")
    assert data["frontend"]["framework"] == "nextjs"
    assert data["backend"]["health_url"] == "http://localhost:3000/api/health"


def test_check_design_tokens_dispatcher_uses_none_enforcer(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo)
    sot = repo / "docs" / "source-of-truth"
    (sot / "STACK_PROFILE.yaml").write_text("""
frontend:
  language: typescript
  framework: nextjs
  module_root: web/src
  theme_root: web/src/theme
backend:
  language: typescript
  framework: express
  module_root: server/src
db:
  engine: sqlite
git_workflow: pr-flow
design_tokens_enforcer: design_tokens_v1
""", encoding="utf-8")
    result = subprocess.run(["bash", "scripts/check-design-tokens.sh"], cwd=repo, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK Design tokens" in result.stdout or "no existe todavia" in result.stdout


def test_minireact_source_docs_bootstrap_without_flutter_tables(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo)
    sot = repo / "docs" / "source-of-truth"
    for p in sot.glob("*"):
        if p.name != ".gitkeep":
            p.unlink()
    (sot / "STACK_PROFILE.yaml").write_text("""
profile_version: stack-profile-v1
frontend:
  language: typescript
  framework: nextjs
  module_root: web/src
  theme_root: web/src/theme
  test_cmd: pnpm test
  dev_cmd: pnpm dev
  visual_check: browser
backend:
  language: typescript
  framework: nextjs-api
  module_root: web/src/server
  test_cmd: pnpm test
  dev_cmd: pnpm dev
  health_url: http://localhost:3000/api/health
db:
  engine: sqlite
  migrate_cmd: pnpm prisma migrate deploy
  seed_cmd: pnpm seed
git_workflow: pr-flow
design_tokens_enforcer: design_tokens_v1
""", encoding="utf-8")
    (sot / "UX_CONTRACT.md").write_text("""# UX_CONTRACT — MiniReact

## 1. UX purpose
Small note app.

## 2. Persona
| Persona | Goal | Journey | Data required |
|---|---|---|---|
| User | Create and list notes | J1 | persisted notes rows |

## 3. Screen inventory
| Route | Screen/Page | Primary journey refs | Required UI states | Real data contract |
|---|---|---|---|---|
| /notes | NotesPage | J1 | loading,error,success,empty | sqlite notes rows |
""", encoding="utf-8")
    (sot / "instrucciones.md").write_text("""# MiniReact Instructions

## Journey Coverage Matrix
| ID | Milestone | Pantallas/Screens | Acciones/Actions | Endpoints | Tablas/Tables | Estado cliente/Client state | Slices | Verificación/Verification |
|---|---|---|---|---|---|---|---|---|
| J1 | Notes CRUD | /notes | create note, list notes | POST /api/notes, GET /api/notes | notes | notesStore | P00-S01-T001, P01-S01-T001, P02-S01-T001 | Browser + SQLite persisted rows |
""", encoding="utf-8")
    (sot / "MINIREACT_TECHNICAL_GUIDE.md").write_text("""# MINIREACT Technical Guide

## 1 Architecture
Next.js frontend/API with SQLite.

## 2 Routes
| Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/provider | Estados UI obligatorios | Next action | Slice ID |
|---|---|---|---|---|---|---|---|---|
| /notes | NotesPage | none | J1 | GET /api/notes, POST /api/notes | notesStore | loading,error,success,empty | create note | P02-S01-T001 |

## 3 Endpoints
| Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
|---|---|---|---|---|---|---|---|---|
| POST | /api/notes | title | note | none | 400 | /notes J1 | notes insert | P01-S01-T001 |
| GET | /api/notes | none | notes[] | none | 500 | /notes J1 | notes select | P02-S01-T001 |

## Verification Data Contract
| Flow/Journey | Persona/Rol | Datos reales/proporcionados requeridos | Carga de datos reales/proporcionados permitida | Reset/Cleanup | Slices/Journeys |
|---|---|---|---|---|---|
| Notes CRUD | User | sqlite notes row | resettable provided data | delete notes | J1 |
""", encoding="utf-8")
    (sot / "MINIREACT_IMPLEMENTATION_CHECKLIST.md").write_text("""# MINIREACT Implementation Checklist

# Phase 0 — DB lane
## Step 0.1 — SQLite notes table
- [ ] notes table exists

# Phase 1 — API lane
## Step 1.1 — Notes API
- [ ] POST /api/notes works

# Phase 2 — UI lane
## Step 2.1 — Notes page
- [ ] /notes consumes real API

## Canonical Coverage Registry
| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P00-S01-T001 | db | notes schema | Step 0.1 | v1 | planned | low | auto | — | db:migrations | prisma/schema.prisma; web/tests/**/notes* | J1 | — | — | notes | J1 | §1 | notes table exists | pnpm test -- notes.schema |
| P01-S01-T001 | api | create note API | Step 1.1 | v1 | planned | medium | human | P00-S01-T001 | api:notes | web/src/server/**/notes*; web/tests/**/notes* | J1 | — | POST /api/notes | notes | J1 | §3 | creates persisted note | pnpm test -- notes.api |
| P02-S01-T001 | frontend | notes page | Step 2.1 | v1 | planned | medium | human | P01-S01-T001 | front:notes | web/src/app/notes/**; web/src/theme/** | J1 | /notes | GET /api/notes | notes | J1 | §2 | page lists persisted notes | pnpm test -- notes.page |
""", encoding="utf-8")
    cmds = [
        ["python3", "-B", "-S", ".claude/bin/bootstrap_source_of_truth.py", "--validate-only"],
        ["python3", "-B", "-S", ".claude/bin/bootstrap_source_of_truth.py", "--refresh"],
        ["bash", "scripts/check-task-dag.sh", "--strict"],
        ["bash", "scripts/check-journey-matrix.sh", "--strict"],
        ["bash", "scripts/check-wiring-contract.sh", "--strict", "--require-new-template-columns"],
    ]
    outputs = []
    for cmd in cmds:
        res = subprocess.run(cmd, cwd=repo, text=True, capture_output=True, timeout=60)
        outputs.append(res.stdout + res.stderr)
        assert res.returncode == 0, "\n".join(outputs)
    registry = json.loads((repo / "orchestrator-state/tasks/registry.json").read_text())
    assert registry["task_dag"]["mode"] == "explicit_dag"
    assert len(registry["tasks"]) == 3
    assert len(registry["journeys"]) == 1
    assert registry["task_dag"]["adjacency_list"]["P00-S01-T001"] == ["P01-S01-T001"]
    assert "notes" in {tbl for j in registry["journeys"] for tbl in j["tables"]}
    assert not any("auth.users" in str(t.get("tables")) for t in registry["tasks"])


def _make_minimal_git_workflow_repo(tmp_path, workflow: str):
    if not shutil.which("git"):
        return None
    repo = tmp_path / "git-workflow-repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".claude" / "bin").mkdir(parents=True)
    (repo / ".claude" / "git-workflows").mkdir(parents=True)
    (repo / "docs" / "source-of-truth").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "git-workflow.sh", repo / "scripts" / "git-workflow.sh")
    shutil.copy2(ROOT / ".claude" / "bin" / "stack_profile.py", repo / ".claude" / "bin" / "stack_profile.py")
    for plugin in (ROOT / ".claude" / "git-workflows").glob("*.sh"):
        shutil.copy2(plugin, repo / ".claude" / "git-workflows" / plugin.name)
    for script in [repo / "scripts" / "git-workflow.sh", *(repo / ".claude" / "git-workflows").glob("*.sh")]:
        script.chmod(0o755)
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text(
        f"profile_version: stack-profile-v1\ngit_workflow: {workflow}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def test_git_workflow_direct_main_alias_pushes_to_main(tmp_path):
    repo = _make_minimal_git_workflow_repo(tmp_path, "direct-main")
    if repo is None:
        return
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    result = subprocess.run(["bash", "scripts/git-workflow.sh"], cwd=repo, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GIT_WORKFLOW_READY: yes" in result.stdout
    assert "PUSH_READY: yes" in result.stdout
    heads = subprocess.run(["git", "--git-dir", str(remote), "show-ref", "refs/heads/main"], cwd=repo, text=True, capture_output=True, timeout=30)
    assert heads.returncode == 0, heads.stdout + heads.stderr


def test_git_workflow_pr_flow_rejects_main_without_fallback(tmp_path):
    repo = _make_minimal_git_workflow_repo(tmp_path, "pr-flow")
    if repo is None:
        return
    result = subprocess.run(["bash", "scripts/git-workflow.sh"], cwd=repo, text=True, capture_output=True, timeout=30)
    assert result.returncode == 2
    assert "pr-flow requires a feature branch" in result.stdout
    assert "push-to-main/direct-main" in result.stdout


def test_git_workflow_amends_late_ledger_before_push(tmp_path):
    repo = _make_minimal_git_workflow_repo(tmp_path, "direct-main")
    if repo is None:
        return
    remote = tmp_path / "origin-ledger.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    ledger = repo / "orchestrator-state" / "tasks" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text('{"event":"before_close"}\n', encoding="utf-8")
    subprocess.run(["git", "add", str(ledger.relative_to(repo))], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "track ledger"], cwd=repo, check=True)
    ledger.write_text('{"event":"before_close"}\n{"event":"post_commit_bash"}\n', encoding="utf-8")

    result = subprocess.run(["bash", "scripts/git-workflow.sh"], cwd=repo, text=True, capture_output=True, timeout=30)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "GIT_WORKFLOW_TRACE_AMENDED: yes" in result.stdout
    assert "GIT_WORKFLOW_READY: yes" in result.stdout
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, timeout=30).stdout.strip() == ""
    show = subprocess.run(["git", "show", "main:orchestrator-state/tasks/ledger.jsonl"], cwd=repo, text=True, capture_output=True, timeout=30)
    assert show.returncode == 0, show.stdout + show.stderr
    assert "post_commit_bash" in show.stdout


def test_git_workflow_blocks_dirty_non_ledger_paths(tmp_path):
    repo = _make_minimal_git_workflow_repo(tmp_path, "direct-main")
    if repo is None:
        return
    remote = tmp_path / "origin-dirty.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    (repo / "unexpected.txt").write_text("dirty\n", encoding="utf-8")

    result = subprocess.run(["bash", "scripts/git-workflow.sh"], cwd=repo, text=True, capture_output=True, timeout=30)

    assert result.returncode == 2
    assert "working tree is dirty" in result.stdout
    assert "unexpected.txt" in result.stdout


def test_git_workflow_rejects_dirty_worktree_without_stash(tmp_path):
    repo = _make_minimal_git_workflow_repo(tmp_path, "direct-main")
    if repo is None:
        return
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text(
        "profile_version: stack-profile-v1\ngit_workflow: direct-main\n# dirty\n",
        encoding="utf-8",
    )
    result = subprocess.run(["bash", "scripts/git-workflow.sh"], cwd=repo, text=True, capture_output=True, timeout=30)
    assert result.returncode == 2
    assert "working tree is dirty" in result.stdout
    assert "Do not use stash/pop" in result.stdout
    assert "DIRTY:" in result.stdout
