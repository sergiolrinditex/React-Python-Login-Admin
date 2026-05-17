# Traceability and control

- `orchestrator-state/tasks/registry.json` records the real execution state. Bootstrap/claim/hooks write it under locks; `planner` reads it and writes the per-task pack, while closer verifies before final state.
- `orchestrator-state/tasks/runtime-state.json` tracks last worker + last event. Updated by claim scripts and the SubagentStop hook automatically.
- `orchestrator-state/tasks/ledger.jsonl` is a local high-churn runtime trace for Write/Edit/MultiEdit/NotebookEdit and lifecycle events. Bash PostToolUse records go to `orchestrator-state/tasks/bash-ledger.jsonl`. Both are runtime-only/ignored by Git so close-time Bash hooks cannot dirty the repo after commit/push.
- In explicit DAG mode, `CLAUDE_ACTIVE_TASK_ID` + `orchestrator-state/tasks/task-packs/<TASK_ID>.md` are authoritative. There is no global DAG task/phase file.
- `orchestrator-state/memory/PROGRESS.md` is the live project snapshot. Developer updates after every slice. All agents read it after `/clear`.
- `orchestrator-state/memory/task-dag.json` and `.md` are derived DAG artifacts. They contain adjacency matrix, adjacency list, reverse dependencies, topological waves, conflict groups and write-set metadata. They are never edited by hand; update the Coverage Registry `Depends on` / `Conflict group` / `Write set` cells instead.

- `orchestrator-state/agent-memory/<agent>/MEMORY.md` is live per-agent memory. `./scripts/next-wave.sh` auto-compacts files above 250 lines using `scripts/compact-agent-memory.py --apply`; originals are archived byte-for-byte under `archive/` and ignored by Git. Disable per run with `CLAUDE_AUTO_COMPACT_AGENT_MEMORY=0`.

## Handoff

- Every slice produces exactly one handoff: `orchestrator-state/tasks/handoffs/<TASK_ID>.md`.
- Workers append sections; they do not overwrite. `developer` initializes; `validator`, `tester`, `debugger` append.
- The handoff is the primary artifact `closer` reads to build the evidence report and commit message.

## Close conditions

A task is `done` only when all of the following exist:

1. Handoff file with all required sections.
2. Validator outcome = `approved`.
3. Tester outcome = `pass` (or explicitly waived with reason).
4. Evidence directory with test logs, screenshots, curl outputs.
5. PROGRESS.md updated with this slice's results.
6. Risks and open issues documented (handoff or risk-register).
7. Closer trailer had `REPORT_READY: yes`, `GIT_READY: yes`, `PUSH_READY: yes`, `WORKTREES_CLEANED: yes`; the SubagentStop hook refuses false `done` without these proof lines.

## Hooks behavior

- Four hook groups are wired in `.claude/settings.json` with timeout caps. Only the `PreToolUse` Agent hook can deny, and only when the active slice reaches the configured spawn budget. The docs-discrepancy hook is warn-only; PostToolUse, SubagentStop and SessionStart never block. Never delete the active task worktree before SubagentStop has recorded the closer trailer; cleanup must defer it as `active_deferred=1`.
  - `PreToolUse` on `Agent` → `hook_spawn_budget.py`. Blocks the 21st spawn for the active slice by returning `permissionDecision: deny`. This is a subagent-spawn budget, not a browser MCP tool-call budget; `slice-verifier` uses `maxTurns: 130` for Chrome DevTools MCP. In DAG worker terminals it scopes the count to `CLAUDE_ACTIVE_TASK_ID` without any singleton fallback.
  - `PreToolUse` on `Write|Edit|NotebookEdit` → `hook_docs_discrepancy_check.py`. If any note in `orchestrator-state/memory/official-doc-notes/` lacks a `RESOLVED:` line, emits `additionalContext` with a warning listing the unresolved notes. **Warn-only, never blocks.** Chrome MCP and every `mcp__*` tool are excluded by the matcher.
  - `PostToolUse` on `Write|Edit|Bash|NotebookEdit` → `hook_update_ledger.py`. Appends Write/Edit/MultiEdit/NotebookEdit events to local `ledger.jsonl` and Bash events to local `bash-ledger.jsonl`. Bash ledger is ignored by Git by design, so a Bash hook fired after `git commit`/`git push` cannot re-dirty the working tree. In DAG worker terminals it records `CLAUDE_ACTIVE_TASK_ID` from the explicit worker environment so ledger/memory traces cannot bleed across parallel nodes.
  - `SubagentStop` → `hook_capture_subagent_stop.py`. Parses the worker's trailer (`TASK_ID` / `OUTCOME` / `NEXT_STATUS` / `HANDOFF` / `EVIDENCE`) and syncs `registry.json` + `runtime-state.json` **under an exclusive file lock** so two parallel subagents (e.g. validator + tester) cannot clobber each other. In DAG terminals the environment scope is authoritative; if a trailer reports a different `TASK_ID`, the hook logs the mismatch and refuses to mutate a different node.
  - `SessionStart` → `hook_session_context.py`. Emits `additionalContext` with runtime suggested phase, per-terminal DAG worker task override, last worker + event, PROGRESS.md head, unresolved discrepancies, recent hook errors. Follows the official `hookSpecificOutput` format.
- On any exception each hook writes a timestamped entry to `orchestrator-state/hook-errors.log` via `log_hook_error()` in `common.py`. They never re-raise and never block the pipeline; the error log is the single source of truth for hook health, and the SessionStart hook surfaces recent entries on the first turn after a restart.
- If a worker forgets the trailer, the pipeline continues but the `closer` rejects the slice on missing evidence.

## Concurrency safety

- `common.py` provides a `file_lock(path)` context manager backed by `fcntl.flock` (POSIX). All registry / runtime-state mutations (in `write_json`, `update_task_status`, `mark_task_blocked`, `claim_task.py`, `hook_capture_subagent_stop`) acquire this lock before read-modify-write. Writes use a temp file + `rename` for atomicity.
- `claim_task.py` locks `registry.json` first and `runtime-state.json` second, same lock order as `hook_capture_subagent_stop.py`. This prevents duplicate DAG workers from claiming the same ready node and blocks claims that conflict with DAG tasks via `Conflict group`/`Write set`.
- Async evidence runner `run_tests_async.py` also honors `CLAUDE_ACTIVE_TASK_ID`; it loads verification commands from the scoped registry task and writes evidence under that node.
- On Windows the lock becomes a no-op. The framework is designed for POSIX dev machines.

## Journey verify modes (inline vs aparte)

El gate de journey tiene dos rutas. La ruta normal evita el doble gate:

- **Inline** (rama "ahora" en `/verify-slice §5.bis`): el comando ejecuta verify-journey aprovechando el entorno ya reseteado y los datos reales/proporcionados cargados. Apendiza `## verify-journey` al **mismo handoff** del slice (no usa `journey-handoffs/`). El closer al ver `JOURNEY_VERIFY_OUTCOME: verified` emite `JOURNEY_VERIFIED_INLINE: <JID>` y el SubagentStop hook marca el journey como `verified` bajo lock, sin añadirlo a `pending_journey_verifications`.
- **Aparte** (rama "aparte" en `/verify-slice §5.bis`, o falta de la sección): el closer emite `JOURNEY_PENDING_VERIFY: <JID>` como hasta ahora; el SubagentStop hook lo añade a `runtime-state.pending_journey_verifications`; en DAG-only el planner difiere solo tasks que referencian ese JID hasta que el usuario lance `/verify-journey <JID>` por separado (que escribe en `journey-handoffs/<JID>.md` y emite trailer reconocido por el hook).

`JOURNEY_VERIFIED_INLINE` sí lo procesa el hook: marca el journey como `verified`, limpia cualquier pending anterior y actualiza `last_journey_verified`. El campo `runtime-state.pending_journey_verifications` sigue siendo el mecanismo de bloqueo para journeys que quedaron en modo "aparte".

## Parallel-pair status ownership (validator‖tester)

When two subagents run in parallel and both finish on the same task (the canonical case is `validator ‖ tester`), only one of them owns the task's lifecycle `status`. The other's signals are stored as metadata so they survive but never overwrite the lifecycle:

- `tester` owns `task.status` (writes `ready_for_close` on pass, `needs_debug` on fail).
- `validator` is **informational** for the registry: the hook stores its trailer as `task.validator_outcome` + `task.validator_next_status`. It does NOT touch `task.status`. The validator's `OUTCOME` is still bloqueante for the `closer` — the closer reads the handoff and rejects the commit if validator did not approve.
- `official-docs-researcher` is informational for the same reason (parallel with `developer`).

The info-only/lifecycle classification lives only in `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` (`info_only`, `mutates_registry_lifecycle`). The hook derives behavior from that schema at runtime; there is no hardcoded agent whitelist in code. The lock around the registry write is still acquired (atomicity), but the read-modify-write decision is schema-aware, so the order of arrival of parallel stops no longer affects the final state.



## Journey handoffs

- `orchestrator-state/tasks/journey-handoffs/<JOURNEY_ID>.md` — escritos por `/verify-journey`. Esquema:
  - `TIMESTAMP: <ISO-8601>`
  - `MODE: pre-next-slice | post`
  - `JOURNEY_VERIFY_OUTCOME: verified | issues_found`
  - `MILESTONE: <Mn>`
  - `SLICES_COVERED: <lista TASK_IDs>`
  - `DATA_SETUP_CONSOLIDATED: <lista de datos reales/proporcionados cargados>`
  - `FLOWS_TESTED: <lista>`
  - `MARGINAL_STATES_TESTED: back, reload, empty, error_network, permission_denied, deep_link`
  - `NEXT_ACTION_VERIFIED: yes | no | n/a`
  - `FINDINGS: <bullets si issues_found>`
  - `EVIDENCE: orchestrator-state/tasks/evidence/journeys/<JID>/verify-*`
  - Waiver opcional explícito: `JOURNEY_VERIFY_WAIVED: <motivo>` (solo con firma humana).
- Una vez `JOURNEY_VERIFY_OUTCOME: verified` queda escrito, el SubagentStop hook quita `<JID>` de `runtime-state.pending_journey_verifications` y marca `registry.journeys[<JID>].verification_status: verified`.

## Journey state in runtime-state.json

Campos añadidos a `runtime-state.json` por la feature de journey-verification:

- `pending_journey_verifications`: list[str] — JOURNEY_IDs cuyos slices están todos `done` pero aún no tienen `/verify-journey` o verificación inline. En DAG-only difiere solo tasks que referencian esos JIDs; ramas independientes pueden seguir.
- `last_journey_verified`: str | null — último JOURNEY_ID verificado (informativo, surface en SessionStart hook).

## Journey state in registry.json

Campo añadido a `registry.json` por bootstrap (parsea la Journey Coverage Matrix de `instrucciones.md`, localizada por nombre — §3.5 en baseline snapshot, §3.7 en feature-app):

- `journeys`: list[dict] — uno por fila de la matriz, con `id`, `title`, `milestone`, `screens`, `actions`, `endpoints`, `tables`, `client_state`, `task_ids` (con rangos expandidos), `verification` (texto de la columna), `verification_status` (`pending|verified|waived`), `verified_at`, `verify_handoff`.
- Si `instrucciones.md` no tiene Journey Coverage Matrix → `journeys: []` (back-compat con proyectos pre-matriz).

## Reversibility

Prefer small reversible tasks over large diffs. Every migration has an `up` and `down`. Every feature flag has a documented rollback.

Git close note: `hook_update_ledger.py` writes Bash PostToolUse events to `orchestrator-state/tasks/bash-ledger.jsonl`, which is runtime-only and ignored by Git. This prevents Bash hooks from re-dirtying the working tree after the atomic commit/push in DAG close. Do not use `git stash` as the normal closer flow; stage required changes into the slice commit before running `./scripts/git-workflow.sh`.
