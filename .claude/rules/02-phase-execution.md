# Phase execution

Phases are source-of-truth driven, strict order. Each phase declared in the Coverage Registry must produce a VISIBLE, FUNCTIONAL, VERIFIABLE deliverable. Never build in the dark: after every slice, verify the deliverable using the method defined in the task pack / TECHNICAL_GUIDE / UX_CONTRACT.

## Phases

Do not hardcode a fixed phase count. Read `orchestrator-state/tasks/registry.json -> phase_order` and `phases[]` after bootstrap. Minimal apps may have a short lane; existing baseline-style products may have many phases (for example P00..P12). The only invariant is dependency order: a phase can advance only when its DAG predecessors and phase gate are satisfied.

Typical examples, not a contract:

- Scaffold/design-system baseline.
- Auth/data foundation.
- Core features.
- Complete features and secondary UX.
- Hardening/observability/security.
- Release/deploy/handoff.

## Pipeline per slice (20 spawns max, parallelism first)

1. Validate prerequisites (PRE-GATE: all previous tests green).
2. Read PROGRESS.md to understand current state.
3. `planner` — selects next ready task, extracts the full source-of-truth pack, does impact analysis. Blocking. Must output `CONTEXT_READY: yes`.
4. `developer` plus optional `official-docs-researcher` — one message with one or two Agent calls.
   - `developer` implements DB/migration → backend (endpoint + service + repo + tests + logs) → frontend (domain + data + presentation + tests + logs) → updates PROGRESS.md → writes handoff.
   - `official-docs-researcher` runs only when the `planner` marks `NEEDS_OFFICIAL_DOCS: yes` or the slice touches unconfirmed external API/library/security/AI/RAG/MCP/streaming/DB/deploy behavior. It receives 1–5 concrete questions and uses cache/MCP/Context7 first. If it detects a discrepancy with internal docs → writes a note in `orchestrator-state/memory/official-doc-notes/`; the PreToolUse docs-discrepancy hook warns the developer on the next Write/Edit (warn-only, never blocks) so the developer reconciles the source-of-truth pack and adds a `RESOLVED: <how>` line before continuing.
5. `validator` ‖ `tester` — parallel, one message with two Agent calls.
   - `validator` reviews architecture, scope, DRY/KISS/YAGNI, file size, docstrings, logging, PROGRESS.md, security scope.
   - `tester` runs real tests with backend + DB up, verifies logs under both verbose modes.
6. If `validator` or `tester` finds an in-scope defect → `debugger` → back to step 5. **Max 3 debug cycles per task.** If still failing after 3 debugger passes → stop pipeline, surface blocker to human, mark task `blocked` in registry. Do not create FU for defects the debugger can fix inside the same task pack/write_set.
   - Create FU only for out-of-scope work: missing Coverage Registry row, new route/endpoint/table/journey, write_set/conflict_group expansion, missing real/provided data contract, external dependency, or explicit human product decision.
7. **Visual verification** via `/verify-slice` — router + `slice-verifier`. It performs hard reset, loads real/provided Verification Data Contract rows, reproduces the app through Chrome DevTools MCP, claude-in-chrome or Agent360 Browser MCP (`browser-mcp`), watches front/back/DB logs, and appends `## verify-slice` with `MCP_BROWSER`, `DATA_CONTRACT_ROWS`, `DATA_SETUP`, `PERSISTED_DATA_OBSERVED`, `FLOWS_TESTED`, `EVIDENCE` and `VERIFY_OUTCOME: verified|issues_found|blocked`. Resilient to `/clear`: rebuilds state from disk. Verified moves to `verified_pending_close`, not `done`.
   `slice-verifier` may use up to `maxTurns: 130` for MCP-heavy Chrome DevTools runs, but must keep a final-write reserve and block with `mcp_budget_exhausted_or_scope_too_large` instead of leaving partial state. This does not change the 20-spawn per-slice budget.
   - **§5.bis — Journey-closing inline (gate humano único)**. Si la slice cierra al menos un journey de `registry.journeys[]` Y `VERIFY_OUTCOME: verified`, el comando pregunta al usuario si verifica el journey end-to-end ahora aprovechando el entorno ya reseteado. Si "ahora" → ejecuta verify-journey inline (estados marginales, deep links, next action) y apendiza `## verify-journey` al handoff con `JOURNEY_VERIFY_OUTCOME: verified|issues_found`. Si "aparte" → mantiene la rama tradicional (closer emite `JOURNEY_PENDING_VERIFY`, planner bloqueará).
8. `closer` — writes evidence report, creates the atomic commit for this `TASK_ID`, runs the configured `./scripts/git-workflow.sh`, and cleans safe worktrees. Pre-check requires a full verified `## verify-slice` handoff and the prior state `verified_pending_close` (or an explicit human `VERIFY_WAIVED: <reason>` for non-UI cases). Detects journey-closing slices with `list_journey_closures.py`/`completion_policy=all_task_ids_done`, never with positional `task_ids[-1]`:
   - Si el handoff tiene `## verify-journey` con `JOURNEY_VERIFY_OUTCOME: verified` para ese JID → emite `JOURNEY_VERIFIED_INLINE: <JID>`; el hook lo marca `verified` bajo lock.
   - Si el handoff tiene `## verify-journey` con `issues_found` → `OUTCOME: blocked` (lanza debugger).
   - En cualquier otro caso → emite `JOURNEY_PENDING_VERIFY: <JID>` (rama tradicional).
   - Tras integración Git, el `closer` dispara `slice-clean.sh --apply` y `cleanup-worktrees.sh --apply --task <TASK_ID> --schedule-active`. El cleanup resuelve el root canónico internamente y no debe borrar la worktree activa antes del `SubagentStop`; `active_deferred=1` es válido cuando va acompañado de limpieza diferida o comando manual. Si la limpieza falla por dirty/skipped, bloquea como fallo mecánico; no abras follow-up de producto.
9. **Journey gate aparte** (solo si verify-slice eligió "aparte" o waiver) — `/verify-journey <JID>` resuelve los pending. En DAG-only, pending journeys difieren sólo las tasks que referencian ese `JID`; ramas independientes pueden seguir. Hard reset + datos reales/proporcionados consolidados + reproducción end-to-end multi-pantalla. Resilient to `/clear`. Waiver via `JOURNEY_VERIFY_WAIVED: <reason>` in the trailer (only with explicit human signature).

Stop immediately if: `planner` returns `CONTEXT_READY: no`, official-doc discrepancy remains unresolved for files this slice needs to edit, or the current task depends on incomplete predecessors.

## Tool-call fan-out dentro de cada agente

Los agentes deben agrupar lecturas/consultas independientes en un solo mensaje con varias tool calls cuando no haya dependencia entre ellas: `Read`/`Grep` de ficheros distintos, consultas MCP/Context7/WebFetch de tecnologías distintas, o checks de estado independientes. No serialices lo que puede resolverse en batch. Mantén la lógica secuencial solo cuando una salida alimenta la siguiente llamada, o cuando haya riesgo de escribir el mismo recurso.

## Gate per phase

Before advancing to the next phase:

- All tests green on both sides.
- Every function/endpoint has logging.
- `ENABLE_VERBOSE_LOGGING=true` shows full flow; `false` shows only warning+error.
- PROGRESS.md reflects all work in the phase.
- Dependency audit clean.
- Security + a11y checklist green where relevant.


## DAG execution overlay

Production execution is DAG-only. DAG execution is enabled by the Coverage Registry dependency column in the checklist; if `task_dag.mode` is `missing dependency column`, treat it as a source-of-truth defect and do not open workers. The planner must treat `depends_on` as a hard gate: a node can be selected only when every predecessor is `done`. Multiple ready nodes in the earliest incomplete phase form the current wave.

Cross-slice regression guard:

- Shared frontend/domain files (`errors.ts`, auth/MFA/ForgotPassword, router/routes, chat/domain, providers/layout, shared/core) require real `/verify-slice` browser evidence before closer. Auto verify is only for low-risk non-UI/non-shared deterministic tasks.
- If a worktree cannot see a done dependency from `origin/main`, stop as `stale_worktree_dep_missing`; do not let planner auto-rebase or silently plan against stale files.
- PROGRESS.md is canonical in the main repo. During a slice, a worktree may not show a local PROGRESS diff; `progress_md_gate: inconclusive` is diagnostic, not by itself a product blocker.

Rules for DAG waves:

- Use `/next-wave` to list independent `ready` nodes. The script first performs safe local housekeeping (agent MEMORY.md auto-compaction above 250 lines, deferred worktree cleanup, lifecycle-event sync) and then enforces `Conflict group` and `Write set` guardrails before opening worker terminals. It must not kill/restart browser MCPs; MCP health belongs to `/verify-slice`.
- Do not spawn several slice pipelines inside one Claude session. Use one terminal per `TASK_ID`, each with `CLAUDE_ACTIVE_TASK_ID=<TASK_ID>`.
- Before the first worker call in a DAG terminal, claim the task with `.claude/bin/claim_task.py <TASK_ID>`. This prevents duplicate terminals from taking the same node and denies claims that conflict with DAG tasks by `Conflict group`/`Write set`.
- Do not bypass journey gates, phase gates, spawn budget, human verification or closer. DAG only changes which independent slices may be worked at the same time.
- If path conflicts are likely (same migration file, same screen, same provider, same endpoint family), encode them in the source-of-truth `Conflict group`/`Write set` cells instead of relying on memory.
- Before opening the next phase, run `./scripts/phase-gate.sh <PHASE_ID>`; use `--require-git-clean` when a real `origin/main` exists.
