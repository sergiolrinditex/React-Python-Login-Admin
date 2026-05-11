#!/usr/bin/env python3
"""Audit high-level docs/config for the AnyStack production-DAG refactor.

This catches drift that unit tests often miss: stale three-doc wording, old
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
    for banned in ["# Three-doc execution index", "bootstrap-three-doc-project", "Hard reset + fixtures"]:
        if banned in claude_index:
            fail(errors, f".claude/CLAUDE.md contains stale wording: {banned}")

    settings = json.loads(read(".claude/settings.json"))
    if settings.get("agent") != "main-orchestrator":
        fail(errors, ".claude/settings.json must set agent=main-orchestrator")

    legacy_baseline_dir = ROOT / "docs" / ("base" + "-" + "app")
    if legacy_baseline_dir.exists():
        fail(errors, "legacy bundled baseline directory must not exist; use optional docs/product-baseline for a real existing app snapshot")
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

    runbook = read("docs/guides/LEGACY_AND_DAG_RUNBOOK.md")
    if "trío de documentos" in runbook:
        fail(errors, "LEGACY_AND_DAG_RUNBOOK still says source-of-truth is a 3-doc trio")
    if re.search(r"step supera 10|step <=10|steps <=10|step\s+<*=\s*10", runbook, re.I):
        fail(errors, "LEGACY_AND_DAG_RUNBOOK still uses old step<=10 budget")
    if "claude --agent main-orchestrator --permission-mode bypassPermissions \"/next-slice" not in runbook:
        fail(errors, "LEGACY_AND_DAG_RUNBOOK next-wave example must use full claude --agent command")
    if "--scope-classification" not in runbook or "--why-not-debugger" not in runbook:
        fail(errors, "LEGACY_AND_DAG_RUNBOOK follow-up example must include anti-FU-spam triage flags")

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

    if errors:
        print("ORCHESTRATOR_REFACTOR_CONSISTENCY_AUDIT: failed", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("ORCHESTRATOR_REFACTOR_CONSISTENCY_AUDIT: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
