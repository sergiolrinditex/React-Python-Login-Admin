# Phase execution

Phases are source-of-truth driven, strict order. Each phase declared in the Coverage Registry must produce a VISIBLE, FUNCTIONAL, VERIFIABLE deliverable. Never build in the dark: after every slice, verify the deliverable using the method defined in the task pack / TECHNICAL_GUIDE / UX_CONTRACT.

## Phases

Do not hardcode a fixed phase count. Read `orchestrator-state/tasks/registry.json -> phase_order` and `phases[]` after bootstrap. Minimal apps may have a short lane; BaseApp-style products may have many phases (for example P00..P12). The only invariant is dependency order: a phase can advance only when its DAG predecessors and phase gate are satisfied.

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
4. `developer` ‖ `official-docs-researcher` — parallel, one message with two Agent calls.
   - `developer` implements DB/migration → backend (endpoint + service + repo + tests + logs) → frontend (domain + data + presentation + tests + logs) → updates PROGRESS.md → writes handoff.
   - `official-docs-researcher` ALWAYS runs as a safety net (shallow pass ≤5s when cache hit). Catches patterns or ecosystem changes the `planner` missed. If it detects a discrepancy with internal docs → writes a note in `orchestrator-state/memory/official-doc-notes/`; the PreToolUse docs-discrepancy hook warns the developer on the next Write/Edit (warn-only, never blocks) so the developer reconciles the source-of-truth pack and adds a `RESOLVED: <how>` line before continuing.
5. `validator` ‖ `tester` — parallel, one message with two Agent calls.
   - `validator` reviews architecture, scope, DRY/KISS/YAGNI, file size, docstrings, logging, PROGRESS.md, security scope.
   - `tester` runs real tests with backend + DB up, verifies logs under both verbose modes.
6. If `tester` fails → `debugger` → back to step 5. **Max 3 debug cycles per task.** If tester still fails after 3 debugger passes → stop pipeline, surface blocker to human, mark task `blocked` in registry.
7. **Visual verification** via `/verify-slice` — hard reset + fixtures + human reproduction in browser (or the method defined in TECHNICAL_GUIDE: emulator, simulator, device, etc.). Resilient to `/clear`: rebuilds state from disk. Appends `## verify-slice` with `VERIFY_OUTCOME: verified|issues_found` to the handoff.
   - **§5.bis — Journey-closing inline (gate humano único)**. Si la slice cierra al menos un journey de `registry.journeys[]` Y `VERIFY_OUTCOME: verified`, el comando pregunta al usuario si verifica el journey end-to-end ahora aprovechando el entorno ya reseteado. Si "ahora" → ejecuta verify-journey inline (estados marginales, deep links, next action) y apendiza `## verify-journey` al handoff con `JOURNEY_VERIFY_OUTCOME: verified|issues_found`. Si "aparte" → mantiene la rama tradicional (closer emite `JOURNEY_PENDING_VERIFY`, planner bloqueará).
8. `closer` — writes evidence report, commits atomically on `main`, pushes `origin/main`, and cleans safe worktrees. Pre-check requires `VERIFY_OUTCOME: verified` (or an explicit `VERIFY_WAIVED: <reason>`). Detects journey-closing slices with `list_journey_closures.py`/`completion_policy=all_task_ids_done`, never with positional `task_ids[-1]`:
   - Si el handoff tiene `## verify-journey` con `JOURNEY_VERIFY_OUTCOME: verified` para ese JID → emite `JOURNEY_VERIFIED_INLINE: <JID>`; el hook lo marca `verified` bajo lock.
   - Si el handoff tiene `## verify-journey` con `issues_found` → `OUTCOME: blocked` (lanza debugger).
   - En cualquier otro caso → emite `JOURNEY_PENDING_VERIFY: <JID>` (rama tradicional).
   - Tras push, dispara `bash scripts/slice-clean.sh --apply` y `bash scripts/cleanup-worktrees.sh --apply --task <TASK_ID>` (housekeeping silencioso; no borra worktrees dirty).
9. **Journey gate aparte** (solo si verify-slice eligió "aparte" o waiver) — `/verify-journey <JID>` resuelve los pending. El `planner` refuses with `CONTEXT_READY: no` while `runtime-state.pending_journey_verifications` is non-empty. Hard reset + fixtures consolidados + reproducción end-to-end multi-pantalla. Resilient to `/clear`. Waiver via `JOURNEY_VERIFY_WAIVED: <reason>` in the trailer (only with explicit human signature).

Stop immediately if: official docs contradict internal docs, `planner` returns `CONTEXT_READY: no`, or the current phase/task depends on incomplete predecessors.

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

Sequential execution is still valid and remains the fallback. DAG execution is enabled only by the Coverage Registry dependency column in the checklist. The planner must treat `depends_on` as a hard gate: a node can be selected only when every predecessor is `done`. Multiple ready nodes in the earliest incomplete phase form the current wave.

Rules for DAG waves:

- Use `/next-wave` to list independent `ready` nodes. The script enforces `Conflict group` and `Write set` guardrails before opening worker terminals.
- Do not spawn several slice pipelines inside one Claude session. Use one terminal per `TASK_ID`, each with `CLAUDE_ACTIVE_TASK_ID=<TASK_ID>`.
- Before the first worker call in a DAG terminal, claim the task with `.claude/bin/claim_task.py <TASK_ID>`. This prevents duplicate terminals from taking the same node and denies claims that conflict with active tasks by `Conflict group`/`Write set`.
- Do not bypass journey gates, phase gates, spawn budget, human verification or closer. DAG only changes which independent slices may be worked at the same time.
- If path conflicts are likely (same migration file, same screen, same provider, same endpoint family), encode them in the source-of-truth `Conflict group`/`Write set` cells instead of relying on memory.
- Before opening the next phase, run `./scripts/phase-gate.sh <PHASE_ID>`; use `--require-git-clean` when a real `origin/main` exists.
