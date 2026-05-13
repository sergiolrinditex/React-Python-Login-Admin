---
name: bootstrap-source-of-truth-project
description: Bootstrap the full source-of-truth operating system for the current project. Use manually at the start of a new session or whenever the source docs changed.
disable-model-invocation: true
allowed-tools: Read Glob Grep Write Bash WebSearch WebFetch Agent TaskCreate TaskGet TaskList TaskUpdate
---

Bootstrap the project as a source-of-truth execution system. Runs ONCE at project start.

## Objective

Detect the source-of-truth pack, validate it, generate runtime artifacts, verify Claude Code design against current official docs, and prepare the project for controlled phase execution.

## Steps

1. Validate the source-of-truth contract:
   - Use ONLY `docs/source-of-truth/` as the canonical folder; no fallback.
   - Locate exactly one `instrucciones.md`, one `*_IMPLEMENTATION_CHECKLIST.md`, one `*_TECHNICAL_GUIDE.md`.
2. Run `python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh`.
3. Use `document-analyzer` to validate results.
4. Use `official-docs-researcher` to verify current Claude Code behaviors for: subagents, skills, hooks, settings, permissions, agent teams.
5. Use `project-architect` to build the executable architecture contract.
6. Use `task-planner` to build/refresh the task registry.
7. Use `planner`/bootstrap to materialize per-task packs under `orchestrator-state/tasks/task-packs/`.
8. If session task tools are available, you may display the first ready DAG task in the session task list for visibility only; never treat it as execution authority.
9. Report: detected docs, blocking issues, first ready DAG task, official-doc discrepancies if any.

Do NOT code product features during bootstrap.

After bootstrap completes, all subsequent work flows through the per-slice chain (max 20 spawns with aggressive parallelism): `planner → (developer ‖ official-docs-researcher) → (validator ‖ tester) → (debugger if needed) → /verify-slice (human gate) → closer`. Use `/next-slice` to arrancar slices; it pauses at tester pass and points you to `/verify-slice` for the human verification step. If `registry.task_dag.mode == explicit_dag`, use `/next-wave` first to list safe parallel roots, then run one terminal per selected `TASK_ID` with `CLAUDE_ACTIVE_TASK_ID` and per-task packs under `orchestrator-state/tasks/task-packs/`. `/next-wave` also enforces `Conflict group`/`Write set` serialization; if strict wiring reports those columns missing, fix the Coverage Registry before coding.
