---
name: phase-execution
description: Execute the current phase or a specific phase in a controlled document-driven loop.
argument-hint: "[current|PHASE_ID]"
disable-model-invocation: true
allowed-tools: Read Grep Glob Write Bash WebSearch WebFetch Agent TaskCreate TaskGet TaskList TaskUpdate
---

Execute the requested phase using the source-of-truth operating system.

Target phase: $ARGUMENTS

## Loop (per task — max 20 spawns, parallelism first)

1. Refresh bootstrap artifacts if needed.
2. Read PROGRESS.md to understand current state.
3. Ensure DAG phase is ready (PRE-GATE: all previous tests green).
4. **`planner`** [BLOCKING] — picks next ready task, extracts the source-of-truth pack + PROGRESS, does impact analysis, and writes `orchestrator-state/tasks/task-packs/<TASK_ID>.md`. Wait for `CONTEXT_READY: yes` with the full source pack extracted AND `IMPACT_READY: yes`. If `no` → resolve the blocker; DO NOT invoke developer without context.
5. **`developer` ‖ `official-docs-researcher`** [PARALLEL — one message with two Agent calls]: pass both `TASK_ID` and `TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md`.
   - `developer`: DB → backend → frontend → tests → logs. Updates PROGRESS.md. Writes handoff.
   - `official-docs-researcher`: ALWAYS runs as safety net (shallow pass ≤5s on cache hit). On discrepancy → writes note to `orchestrator-state/memory/official-doc-notes/`. The PreToolUse hook surfaces the note as a WARNING (warn-only, never blocks) next time the developer writes product code. Developer reconciles and adds `RESOLVED: <how>` to each note.
6. **`validator` ‖ `tester`** [PARALLEL — one message with two Agent calls]:
   - `validator`: architecture, scope, DRY/KISS/YAGNI, docstrings, logging, PROGRESS.md, tests realness (no execution), integrated security checklist (if diff touches auth/secrets/CORS/SQL/permissions/headers/rate-limit/infra).
   - `tester`: real tests with backend + DB up, curl endpoints, verify logs in both `ENABLE_VERBOSE_LOGGING` modes, evidence to `orchestrator-state/tasks/evidence/<TASK_ID>/`.
7. **`debugger`** if `tester` fails → go back to step 6. Max 3 cycles; on the 4th failure the debugger emits `OUTCOME: blocked` with reason `max_debug_cycles_reached` for human escalation.
8. **`/verify-slice`** (human gate) — hard reset + datos reales/proporcionados from the TECHNICAL_GUIDE `Verification Data Contract` + human reproduction in browser. Resilient to `/clear`: rebuilds state from disk. Appends `## verify-slice` with `DATA_CONTRACT_ROWS`, `PERSISTED_DATA_OBSERVED` and `VERIFY_OUTCOME: verified|issues_found`. If `issues_found` → debugger loop (step 7).
9. **`closer`** — evidence report + atomic commit via configured Git workflow (`./scripts/git-workflow.sh`) and safe worktree cleanup. Pre-check requires `VERIFY_OUTCOME: verified` (or explicit `VERIFY_WAIVED: <reason>`).
10. Update registry/runtime through hooks/scripts only; do not maintain task/implicit selector mirrors in production DAG.
11. Repeat until phase is complete or blocked.
12. Run `./scripts/phase-gate.sh <PHASE_ID>` before advancing to the next phase. Use `--require-git-clean` when the repo has a configured `origin/main`.

Stop immediately if:

- official docs contradict internal docs,
- `planner` returned `CONTEXT_READY: no` and blocker cannot be resolved,
- current phase depends on an incomplete previous phase.

## Test and logging verification (every phase gate)

- All tests real (no mocks of business logic).
- All functions/endpoints have BEFORE + AFTER + ERROR logging.
- `ENABLE_VERBOSE_LOGGING=true` shows complete flow.
- `ENABLE_VERBOSE_LOGGING=false` shows only warning + error.
- Dependency audit clean.
- Accessibility checklist green where relevant.

If any check fails → block phase advancement until fixed.

## PROGRESS.md in phase loop

- Start of phase: read PROGRESS.md.
- After each slice: verify developer updated it.
- End of phase: verify it reflects all work done in the phase.
