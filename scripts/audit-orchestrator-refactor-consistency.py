#!/usr/bin/env python3
"""Audit high-level docs/config for the AnyStack production-DAG refactor.

This catches drift that unit tests often miss: stale source-of-truth wording, old
Baseflutter branding in core docs, existing baseline fixture clobbering, old next-wave
copy/paste commands, and stale phase/step budgets.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []

    readme = read("README.md")
    if "BaseflutterAppsEngineFeatures" in readme.splitlines()[0] or "apps Flutter fullstack" in readme.splitlines()[0]:
        fail(errors, "README title still uses old Baseflutter/Flutter-only branding")
    if "claude --agent main-orchestrator --permission-mode bypassPermissions \"/next-slice <TASK_ID>\"" not in readme:
        fail(errors, "README must document next-slice via main-orchestrator main-thread command")

    gitignore = read(".gitignore")
    if "BaseflutterAppsEngineFeatures" in gitignore.splitlines()[0]:
        fail(errors, ".gitignore header still uses old Baseflutter branding")

    claude_index = read(".claude/CLAUDE.md")
    for banned in ["Hard reset + fixtures"]:
        if banned in claude_index:
            fail(errors, f".claude/CLAUDE.md contains stale wording: {banned}")

    # Source-of-truth bootstrap must not carry the historical numbered name.
    historical_bootstrap = "bootstrap_" + "three_docs.py"
    if (ROOT / ".claude/bin" / historical_bootstrap).exists():
        fail(errors, "historical numbered bootstrap script must not exist; use bootstrap_source_of_truth.py")
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache", "node_modules"} for part in path.parts):
            continue
        if path.suffix in {".pyc", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if ("bootstrap_" + "three_docs") in text:
            fail(errors, f"{path.relative_to(ROOT)} still references historical numbered bootstrap name")
            break

    settings = json.loads(read(".claude/settings.json"))
    if settings.get("agent") != "main-orchestrator":
        fail(errors, ".claude/settings.json must set agent=main-orchestrator")

    historical_baseline_dir = ROOT / "docs" / ("base" + "-" + "app")
    if historical_baseline_dir.exists():
        fail(errors, "bundled baseline directory must not exist; use optional docs/product-baseline for a real existing app snapshot")
    sot = ROOT / "docs" / "source-of-truth"
    active_sot_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sot.glob("*")
        if path.is_file() and path.name != ".gitkeep"
    )
    for banned in ["Base" + "App", "BASE" + "APP", "base" + "app", "base" + "-" + "app"]:
        if banned in active_sot_text:
            fail(errors, f"docs/source-of-truth must not ship a default bundled baseline source-of-truth: {banned}")

    workflow = read(".github/workflows/orchestrator-tests.yml")
    if "cp docs/product-baseline" in workflow:
        fail(errors, "workflow must not clobber active docs/source-of-truth from an optional baseline")
    for item in [
        "docs/source-of-truth/instrucciones.md",
        "docs/source-of-truth/UX_CONTRACT.md",
        "docs/source-of-truth/STACK_PROFILE.yaml",
        "*_TECHNICAL_GUIDE.md",
        "*_IMPLEMENTATION_CHECKLIST.md",
    ]:
        if item not in workflow:
            fail(errors, f"workflow must assert active source-of-truth file exists: {item}")
    if "audit-orchestrator-refactor-consistency.py" not in workflow:
        fail(errors, "workflow lint must run audit-orchestrator-refactor-consistency.py")

    # DAG-only docs: there should be no separate dual-mode runbook.
    if (ROOT / "docs/guides" / ("OLD" + "_AND_DAG" + "_RUNBOOK.md")).exists() or (ROOT / "docs/guides" / ("DAG" + "_RUNBOOK.md")).exists():
        fail(errors, "dual-mode runbook must not exist; DAG-only guidance lives in README/CHEATSHEET/CHATGPT_DAG_SOURCE_OF_TRUTH_GUIDE")

    prompt = read("docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md")
    if "prod-like" in prompt:
        fail(errors, "PROMPT_SOURCE_OF_TRUTH_DAG still uses prod-like instead of reales/proporcionados")
    if "Step ideal: 3-10 tasks" in prompt or "hard advisory cap: 10 tasks per step" in prompt:
        fail(errors, "PROMPT_SOURCE_OF_TRUTH_DAG still uses old step budget")
    if "Screen/Journey" not in prompt and "pantalla/journey" not in prompt:
        fail(errors, "PROMPT_SOURCE_OF_TRUTH_DAG must reinforce screen/journey lanes")

    guide = read("docs/guides/CHATGPT_DAG_SOURCE_OF_TRUTH_GUIDE.md")
    if "prod-like" in guide:
        fail(errors, "CHATGPT guide still uses prod-like instead of reales/proporcionados")
    if "steps <=15" not in guide:
        fail(errors, "CHATGPT guide must document steps <=15")

    # The ChatGPT guide must point to the real three profile directories and all five templates.
    stale_guide_paths = [
        "docs/templates/instrucciones.template.md",
        "docs/templates/PROJECT_TECHNICAL_GUIDE.template.md",
        "docs/templates/PROJECT_IMPLEMENTATION_CHECKLIST.template.md",
        "instrucciones.minimal.template.md",
        "PROJECT_TECHNICAL_GUIDE.minimal.template.md",
        "PROJECT_IMPLEMENTATION_CHECKLIST.minimal.template.md",
    ]
    for stale in stale_guide_paths:
        if stale in guide:
            fail(errors, f"CHATGPT guide references stale template path/name: {stale}")
    for required in ["UX_CONTRACT.md", "STACK_PROFILE.yaml", "docs/templates/large-without-base", "docs/templates/large-with-base"]:
        if required not in guide:
            fail(errors, f"CHATGPT guide missing required current source/template reference: {required}")

    contract = read(".claude/orchestrator-contract.json")
    if "prod-like" in contract:
        fail(errors, "orchestrator-contract still uses prod-like data wording")

    sync_baseline = read(".claude/bin/sync_product_baseline.py")
    if "five-file source-of-truth" not in sync_baseline or "require_verify_slice=True" not in sync_baseline:
        fail(errors, "sync_product_baseline.py must require the verified five-file source-of-truth pack before writing product-baseline")
    if "writer" not in sync_baseline or "last_written_paths" not in sync_baseline:
        fail(errors, "sync_product_baseline.py manifest must record writer and last_written_paths")
    sync_wrapper = read("scripts/sync-product-baseline.sh")
    if "CLAUDE_ALLOW_BASELINE_SYNC_WRITES=1" not in sync_wrapper:
        fail(errors, "sync-product-baseline.sh must be the audited baseline write path with CLAUDE_ALLOW_BASELINE_SYNC_WRITES=1")
    if "Only closer" not in contract or "five-file" not in contract:
        fail(errors, "orchestrator-contract product_baseline policy must say only closer syncs the verified five-file baseline")

    common_py = read(".claude/bin/common.py")
    if "RESOLVED(?:" not in common_py or "\\d{4}-\\d{2}-\\d{2}" not in common_py:
        fail(errors, "official-doc note resolution marker must accept RESOLVED: and RESOLVED YYYY-MM-DD forms")


    # Worktree policy: task worktree isolation is session-level, not per-subagent.
    # Otherwise developer/debugger can edit a different checkout than
    # validator/tester/closer are inspecting.
    for agent in (ROOT / ".claude" / "agents").glob("*.md"):
        body = agent.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?m)^isolation:\s*worktree\s*$", body):
            fail(errors, f"{agent.relative_to(ROOT)} must not declare subagent isolation: worktree; /next-wave owns per-TASK_ID worktree checkout")
    if "workspace_root" not in read(".claude/bin/common.py"):
        fail(errors, "common.py must expose workspace_root() for product commands in task worktrees")
    if "ensure-task-worktree.sh" not in read(".claude/bin/next_wave.py"):
        fail(errors, "next_wave.py must route pr-flow worker terminals into per-TASK_ID worktrees")
    next_wave_py = read(".claude/bin/next_wave.py")
    if "--print-root" not in next_wave_py or "BOOTSTRAP_ROOT" not in next_wave_py:
        fail(errors, "next_wave.py must canonicalize the main repo root before entering a task worktree")
    task_wt = read("scripts/ensure-task-worktree.sh")
    if "--print-root" not in task_wt or "CANONICAL_ROOT" not in task_wt or "git -C \"$ROOT\" worktree add" not in task_wt:
        fail(errors, "ensure-task-worktree.sh must resolve the canonical main root and avoid nested worktrees when invoked from a task worktree")
    closer_body = read(".claude/agents/closer.md")
    if "git checkout main" in closer_body or "cambia a `main`" in closer_body or "created in `main`" in closer_body:
        fail(errors, "closer must not switch to main in pr-flow; it must close the current TASK_ID checkout")

    # Operational docs must not reintroduce stale all-slice docs research,
    # global journey gates, direct-main push wording, or dual-mode journey gates.
    operational_drift_patterns = [
        (r"\*\*SIEMPRE\*\*\s+—", "official-docs-researcher must not be documented as always invoked"),
        (r"te invocan en CADA slice|invoked in every slice|for every slice", "official-docs-researcher must not be documented as invoked for every slice"),
        (r"ALWAYS runs", "official-docs-researcher must not be documented as always running"),
        (r"frontier.*strict|strict.*frontier", "journey gate must be single-policy DAG-only, not frontier/strict"),
        (r"commits atomically on `main`, pushes `origin/main`", "closer must use configured git-workflow wording, not direct main push wording"),
        (r"planner.*pending_journey_verifications.*no est[aá] vac[ií]o.*CONTEXT_READY: no", "pending journeys must not globally block all next-slice work"),
        (r"planner.*rejects.*pending_journey_verifications.*non-empty", "pending journeys must not globally block all next-slice work"),
        (r"datos-real_o_prod|prod--like", "docs/site must not use prod-like data badge wording"),
    ]
    operational_drift_paths = [
        ".claude/agents/official-docs-researcher.md",
        ".claude/agents/main-orchestrator.md",
        ".claude/rules/01-non-negotiables.md",
        ".claude/rules/02-phase-execution.md",
        ".claude/rules/04-traceability.md",
        ".claude/skills/phase-execution/SKILL.md",
        ".claude/commands/verify-journey.md",
        ".claude/commands/revise-slice.md",
        "site/diagrams/comandos.md",
        "site/html-site/comandos.html",
        "site/html-site/terminales.html",
    ]
    for rel in operational_drift_paths:
        if not (ROOT / rel).exists():
            continue
        text = read(rel)
        for pattern, message in operational_drift_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
                fail(errors, f"{rel}: {message}")

    # Operational command/rule docs can mention lorem/mocks only as prohibitions,
    # but should not use the old positive fixture/prod-like closure language.
    operational_paths = [
        ".claude/commands/verify-slice.md",
        ".claude/commands/verify-journey.md",
        ".claude/rules/02-phase-execution.md",
        ".claude/rules/05-runtime-write-contract.md",
        ".claude/skills/write-handoff/SKILL.md",
    ]
    for rel in operational_paths:
        text = read(rel)
        for banned in ["real/prod-like", "datos reales/prod-like", "Hard reset + fixtures", "seed base + fixtures"]:
            if banned in text:
                fail(errors, f"{rel} contains stale positive data language: {banned}")


    sync_script = read(".claude/bin/sync_product_baseline.py")
    if "_require_verified_close_context(args)" not in sync_script:
        fail(errors, "sync_product_baseline.py must refuse sync before verified closer handoff")
    if "allow_unverified" not in sync_script:
        fail(errors, "sync_product_baseline.py must make manual unverified sync explicit")
    if 'required = ("instructions", "guide", "checklist", "ux", "stack_profile")' not in sync_script:
        fail(errors, "sync_product_baseline.py must require the five-file source-of-truth pack")
    closer_doc = read(".claude/agents/closer.md")
    if "validator approved" not in closer_doc or "VERIFY_OUTCOME: verified" not in closer_doc:
        fail(errors, "closer must document that product-baseline sync happens only after verified close")
    write_guard = read(".claude/bin/hook_write_scope_guard.py")
    if "docs/product-baseline/" not in write_guard or "CLAUDE_ALLOW_BASELINE_SYNC_WRITES" not in write_guard:
        fail(errors, "write-scope guard must block direct docs/product-baseline edits during DAG tasks")

    common = read(".claude/bin/common.py")
    if "has_resolved_doc_discrepancy_marker" not in common or "RESOLVED 2026" not in common:
        fail(errors, "docs-discrepancy resolution detector must accept date-prefixed RESOLVED lines")


    # Single journey gate policy: DAG-only has no configured mode or global-block branch.
    journey_sensitive = [
        "README.md",
        "CHEATSHEET.md",
        "docs/guides/CHEATSHEET.md",
        "docs/README.md",
        ".claude/CLAUDE.md",
        ".claude/agents/planner.md",
        ".claude/agents/closer.md",
        ".claude/commands/next-wave.md",
        ".claude/commands/verify-slice.md",
        ".claude/rules/04-traceability.md",
        ".claude/skills/close-task/SKILL.md",
        "site/diagrams/dag-flujo.md",
        "site/diagrams/outcomes.md",
        "site/html-site/tecnico.html",
        "site/html-site/outcomes.html",
    ]
    for rel in journey_sensitive:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if ("journey" + "_gate" + "_mode") in text or "bloqueo global estricto" in text or "global" + "/strict" in text or ("fallback " + "hardcoded") in text or ("fallback " + "defensivo") in text:
            fail(errors, f"{rel} contains stale dual-mode/fallback wording")

    capture_hook = read(".claude/bin/hook_capture_subagent_stop.py")
    if "ALLOWED_OUTCOMES" in capture_hook or "ALLOWED_NEXT_STATUS" in capture_hook or "damaged-install fallback" in capture_hook or "fallback only for damaged" in capture_hook:
        fail(errors, "hook_capture_subagent_stop.py must be schema-only; no hardcoded enum fallback")
    contract_json = json.loads(read(".claude/orchestrator-contract.json"))
    journey_policy = json.dumps(contract_json.get("journey_gate", {}), ensure_ascii=False)
    if "strict" in journey_policy or ("journey" + "_gate" + "_mode") in journey_policy:
        fail(errors, "orchestrator-contract journey_gate must be single-policy DAG-only, not mode-based")

    # DAG-only task context: production has no global task/phase selector
    # writer or migration flag. Hooks must use CLAUDE_ACTIVE_TASK_ID only.
    forbidden_helpers = [
        "save" + "_" + "active" + "_task",
        "save" + "_" + "active" + "_phase",
        "load" + "_" + "active" + "_task",
        "load" + "_" + "active" + "_phase",
        "ACTIVE_MIRRORS",
    ]
    if any(name in common for name in forbidden_helpers):
        fail(errors, "common.py must not expose task/phase selector writers or migration flags")
    if "return dag_worker_task_id()" not in common:
        fail(errors, "effective_worker_task_id must use only CLAUDE_ACTIVE_TASK_ID/CLAUDE_TASK_ID")
    session_ctx = read(".claude/bin/hook_session_context.py")
    forbidden_session_fallbacks = [
        'registry.get("' + "active" + '_task")',
        'registry.get("' + "worker" + '_task")',
    ]
    if "DAG worker task" not in session_ctx or any(item in session_ctx for item in forbidden_session_fallbacks):
        fail(errors, "SessionStart must display DAG worker task and not fallback to a implicit selector")

    # Hooks must enforce deterministic script/contract policy, not markdown rules.
    # Agent instructions may be reloaded after /clear; hook decisions should not
    # drift because someone edited .claude/rules/*.md mid-session.
    for hook in (ROOT / ".claude" / "bin").glob("hook_*.py"):
        hook_text = hook.read_text(encoding="utf-8", errors="replace")
        if ".claude/rules" in hook_text or "rules/" in hook_text:
            fail(errors, f"{hook.relative_to(ROOT)} must not parse .claude/rules/*.md at runtime; use code + orchestrator-contract.json")

    stale_terms = [
        "INFO" + "_ONLY_AGENTS",
        "LIFECYCLE" + "_AGENTS",
        "STATE_MUTATING" + "_AGENTS",
        "plain_text" + "_fallback",
        "body-only generation" + " fallback",
        "broken install" + " fallback",
    ]
    scan_roots = [ROOT / ".claude", ROOT / "scripts", ROOT / "docs", ROOT / "site"]
    scan_files = [ROOT / "README.md", ROOT / "CHEATSHEET.md", ROOT / ".github" / "workflows" / "orchestrator-tests.yml"]
    for base in scan_roots:
        if base.exists():
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".zip"}:
                    continue
                try:
                    body = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for term in stale_terms:
                    if term in body:
                        fail(errors, f"{path.relative_to(ROOT)} contains stale refactor term: {term}")
    for path in scan_files:
        if path.exists():
            body = path.read_text(encoding="utf-8", errors="replace")
            for term in stale_terms:
                if term in body:
                    fail(errors, f"{path.relative_to(ROOT)} contains stale refactor term: {term}")

    if errors:
        print("ORCHESTRATOR_REFACTOR_CONSISTENCY_AUDIT: failed", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("ORCHESTRATOR_REFACTOR_CONSISTENCY_AUDIT: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
