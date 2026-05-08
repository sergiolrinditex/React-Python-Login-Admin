# Three-doc execution index — Fullstack Edition

## CRITICAL — This is a REAL PRODUCTION product

- Not a prototype, not a mockup, not a demo.
- All code is PRODUCTION-QUALITY from day 1: real validations, real error handling, real security.
- All data flows are REAL: real API calls, real DB queries, real auth.
- All tests verify REAL behavior. No fake data, no hardcoded responses, no "TODO: implement later".
- E2E tests hit real backend + real DB. If a test passes without real services, it is not valid.

## Source of truth

The project is governed by the canonical source-of-truth set in `docs/source-of-truth/`:

1. `instrucciones.md` — goals, scope, business rules and Journey Coverage Matrix.
2. `*_IMPLEMENTATION_CHECKLIST.md` — phases, steps, Coverage Registry and DAG fields.
3. `*_TECHNICAL_GUIDE.md` — architecture, contracts, endpoints, DB and verification data contract.
4. `STACK_PROFILE.yaml` — stack-specific paths, commands, visual-token enforcer and Git workflow.
5. `UX_CONTRACT.md` — personas, screen inventory, UI states and UX verification rules.

Legacy 3-doc projects remain readable for compatibility, but production projects should use all five files. If any source-of-truth file is missing, duplicated, stale or contradictory — stop and repair the contract first.

## Phases are variable by source-of-truth (BASEAPP=13, MiniNotes/minimal examples=3)

0. **Scaffold + Design System** — backend + DB + frontend running, design tokens ready, showcase page.
1. **Auth + Data Foundation** — login/register on real backend + DB, protected routes, seed data.
2. **Core Features (the motor)** — each feature = complete screen (backend + frontend + tests + visual check).
3. **Complete Features** — secondary features, settings, admin, edge cases.
4. **Harden** — security, error handling, responsive, accessibility, Docker, performance.
5. **Release** — production build, deploy docs, rollback.

Every phase produces a VISIBLE, FUNCTIONAL, VERIFIABLE deliverable. Never build in the dark.

## Per-slice chain — max 20 spawns, parallelism first

```
── /next-slice pipeline (pausa en tester pass) ──
1. planner                               (fused: phase-controller + context-curator + technical-analyst)
2. developer ‖ official-docs-researcher  [PARALLEL — one message, two Agent calls]
                                          official-docs-researcher ALWAYS runs (cache keeps it ≤5s
                                          on shallow pass). Safety net for patterns the planner
                                          missed. On discrepancy → pauses developer, reconciles.
3. validator ‖ tester                    [PARALLEL — one message, two Agent calls]
4. debugger                              [only if tester fails → back to step 3]
   ── /next-slice termina aquí, no invoca closer ──

── (opcional pero recomendado) /clear para liberar ~150k tokens del pipeline ──

── /verify-slice (gate humano único + orquestación de cierre) ──
5. /verify-slice                         hard reset + fixtures + reproducción humana + logs vivos
   ├─ VERIFY_OUTCOME: verified
   │   └─ §5.bis si la slice cierra journey(s) → pregunta al usuario:
   │       ├─ "ahora"  → verify-journey INLINE con entorno ya cargado (un solo gate)
   │       │            apendiza ## verify-journey al handoff
   │       └─ "aparte" → JOURNEY_PENDING_VERIFY → frontier difiere solo tasks de ese journey
   │   → spawnea closer (paso 6)
   └─ VERIFY_OUTCOME: issues_found → spawnea debugger → vuelve a paso 3
6. closer                                (fused: evidence-reporter + git-manager) — commit + configured Git workflow
                                          pre-check rechaza si no hay sección verify-slice en el handoff
                                          si el handoff tiene ## verify-journey verified, NO emite
                                          JOURNEY_PENDING_VERIFY para esos JIDs (rama "ahora")
   └─ post-push: slice-clean + cleanup-worktrees (housekeeping silencioso y seguro)
```

`closer` NUNCA commitea código sin `VERIFY_OUTCOME: verified` en el handoff (procedente de `/verify-slice` humano o de `/auto-verify-slice` solo para slices `low+auto` no journey) o sin waiver explícito `VERIFY_WAIVED: <motivo>` firmado por el usuario. Esto garantiza que no hay commits de código sin verificación real y trazable.

`/verify-journey <JID>` sigue existiendo como **command de rescate manual** — para waivers, re-verificaciones aisladas, debug post-mortem, o casos donde el usuario eligió "aparte" en §5.bis. En el flujo normal, el journey se verifica inline en `/verify-slice` y este command queda dormido.

**Resiliente a `/clear`**: `/verify-slice` reconstruye TODO desde disco (PROGRESS.md, runtime-state, registry, handoff, TECHNICAL_GUIDE). Puedes y debes hacer `/clear` entre el tester pass y `/verify-slice` para liberar los ~100-200k tokens del pipeline previo. El SessionStart hook inyecta el estado de proyecto en la primera turn tras reiniciar.

## DAG wave mode — optional parallel slices

Default mode remains sequential. The bootstrap only enables DAG mode when the Coverage Registry in `*_IMPLEMENTATION_CHECKLIST.md` contains a dependency column named `Depends on`, `Dependencies`, `Deps`, `After`, `Blocked by` or `Dependencias`. In that case, each row is a node and the dependency cell is the source-of-truth adjacency list. Blank / `—` means a root node. Accepted refs: full `TASK_ID`, ranges (`P03-S02-T001..T004`), step refs (`P03-S02`), phase refs (`P03`), or `previous`.

Derived graph artifacts:

```text
orchestrator-state/memory/task-dag.json   adjacency_index + adjacency_matrix + levels
orchestrator-state/memory/task-dag.md     human-readable waves
orchestrator-state/tasks/registry.json    task_dag copy used by planner/checks
```

The matrix is derived, not authored. To change ordering or parallelism, edit only the Coverage Registry `Depends on`, `Conflict group` and `Write set` cells and rerun `bootstrap_three_docs.py --refresh` + `scripts/check-task-dag.sh --strict`. `Depends on` controls DAG readiness; `Conflict group`/`Write set` control safe same-wave scheduling.

For large products, the Coverage Registry is cumulative: `Product increment` labels `baseapp`, `v1`, `v2`, ... and `Build state` keeps already-built rows at `done` while new rows remain `planned`. This preserves full product context without rebuilding closed increments.

Parallel execution uses separate terminals, not extra agent types. Run `/next-wave` to list ready independent tasks, then start one terminal per selected task with both `CLAUDE_ACTIVE_TASK_ID=<TASK_ID>` and `CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md`, then run `/next-slice <TASK_ID>`. The task environment is critical: hooks use `CLAUDE_ACTIVE_TASK_ID` for spawn budget, ledger, session context and SubagentStop accounting; agents use the per-task pack so memory remains scoped to the correct slice even if another terminal moves the legacy `active-task.json` / `active-task.md` pointers. In explicit DAG mode, `orchestrator-state/memory/active-task.md` is advisory only and must never be the only task pack passed to subagents.

All existing gates still apply in each node: planner writes/enriches `orchestrator-state/tasks/task-packs/<TASK_ID>.md`, developer + official-docs-researcher run with that pack, validator + tester read that same pack, debugger loops on the same `TASK_ID`, then `/verify-slice`, closer, journey verification. A task is promotable only when every `depends_on` predecessor is `done`; a task is claimable only when no active task conflicts via `Conflict group`/`Write set`; the planner still respects phase order, phase gates and pending journey blocks.

## Central runtime contract

`.claude/orchestrator-contract.json` is the compact machine-readable index for what each agent may write, which files are generated core state, what trailer fields are required, and which UX fields must reach every UI task pack. The human-readable mirror is `.claude/rules/05-runtime-write-contract.md`.

Use this to keep prompts shorter: agents do not need to rediscover write policy. They load the contract, then write only their own slice artifacts. In DAG mode every artifact containing a `TASK_ID` must match `CLAUDE_ACTIVE_TASK_ID`; hooks enforce that mechanically.

`docs/base-app/` is the built baseline snapshot for the next ChatGPT planning pass. Closer runs `./scripts/sync-product-baseline.sh sync --version <increment> --task <TASK_ID>` before commit so BaseApp + v1 + v2 context is never lost.

## Agents

Total: 12 agents. Per slice max 20 spawns (steps above). Bootstrap-only: `document-analyzer`, `project-architect`, `task-planner`. Phase 5 only: `deployer`.

Manual-memory agents: `planner`, `developer`, `validator`, `debugger`, `official-docs-researcher`, `project-architect`, plus `task-planner` for bootstrap learnings. Memory is stored in `orchestrator-state/agent-memory/<agent>/MEMORY.md`; `.claude/` stays static.

Isolation (worktree): only `developer`, `debugger`, `deployer`.

## Rules

Note: the repeated "Startup obligatorio del agente" block in agent prompts is intentional. Claude Code does not currently provide a shared include primitive for subagent prompts, so each agent repeats the same startup contract to avoid runtime drift.


All project-wide non-negotiables live in `.claude/rules/`:

- `00-source-of-truth.md` — the source-of-truth contract.
- `01-non-negotiables.md` — production quality, tests real, logging, security, a11y, DRY/KISS/YAGNI, docs, file size, deps, DB, API contract.
- `02-phase-execution.md` — variable source-of-truth phases and the per-slice pipeline.
- `03-dev-loop.md` — dev servers, per-slice verification.
- `04-traceability.md` — handoffs, registry, close conditions, hooks.
- `05-runtime-write-contract.md` — centralized runtime write contract, DAG task scope, protected generated state, UX task-pack requirements.

Claude Code loads unscoped `.claude/rules/*.md` at session start. Subagents have isolated prompts, so every agent prompt also contains an explicit startup step to read the six rule files and `.claude/orchestrator-contract.json` directly before acting. If a rule appears to be ignored, read the rule file path explicitly and continue from disk, not from memory.

## Hooks

Four hook groups are wired in `settings.json`. They are intentionally small and capped with conservative timeouts:

- `PreToolUse` on `Agent` → `hook_spawn_budget.py`. Enforces the mechanical max-20-spawns-per-slice budget. On the 21st Agent call it returns `permissionDecision: deny`, so the invariant is code-enforced instead of cultural.
- `PreToolUse` on `Write|Edit|MultiEdit|NotebookEdit` → `hook_write_scope_guard.py` first, then `hook_docs_discrepancy_check.py`. The write-scope guard blocks DAG-corrupting writes: static `.claude/` edits during app execution, cross-task handoff/evidence/report/task-pack writes, source-of-truth edits while a TASK_ID is active, and direct edits to generated core state. The docs-discrepancy hook then warns about unresolved official-doc notes. If `orchestrator-state/memory/official-doc-notes/` has unresolved notes, it injects a visible warning so Claude reconciles before continuing. It is non-blocking by design; MCP/browser tools are excluded by the matcher.
- `PostToolUse` on `Write|Edit|MultiEdit|Bash|NotebookEdit` → `hook_update_ledger.py`. Logs every tool use to `orchestrator-state/tasks/ledger.jsonl`; in DAG worker terminals the log is scoped to `CLAUDE_ACTIVE_TASK_ID`.
- `SubagentStop` → `hook_capture_subagent_stop.py`. Parses the final `CLAUDE_TRAILER:` block (`TASK_ID` / `OUTCOME` / `NEXT_STATUS` / `HANDOFF` / `EVIDENCE` / `REPORT`), increments spawn counters, and syncs `registry.json` + `runtime-state.json` under ordered locks. If the trailer is missing or partial, it writes a visible error; it does not silently drop state. In DAG worker terminals, a trailer with a different `TASK_ID` is logged as a scope mismatch and cannot mutate another node.
- `SessionStart` → `hook_session_context.py`. Emits `additionalContext` with the project state, unresolved docs discrepancies, spawn counts, and recent hook errors.

All hook root resolution is worktree-safe: when a subagent runs with `isolation: worktree`, scripts resolve the canonical main repo before touching `orchestrator-state/tasks/` or `orchestrator-state/memory/`. Hook failures write a timestamped entry to `orchestrator-state/hook-errors.log`; the SessionStart hook surfaces recent entries at restart so corruption is visible instead of silent.

## Mutable state policy

`.claude/` is static Claude Code configuration: agents, skills, commands, rules, hooks and settings. Runtime writes go outside it:

- `orchestrator-state/memory/` — PROGRESS, active task/phase, architecture contract, decisions, risks, official-doc notes.
- `orchestrator-state/tasks/` — registry, runtime-state, work-items, per-task packs, handoffs, evidence, reports, ledger.
- `orchestrator-state/agent-memory/` — manual Reflexion-style memory per agent.
- `orchestrator-state/hook-errors.log` — visible hook failures.

Do not create hidden runtime folders such as `.orchestrator/`. The only hidden configuration directory in this project is `.claude/`.

## Commands

- `/next-wave` — lista la wave DAG actual y los TASK_ID ready paralelizables sin conflictos declarados; no implementa ni spawnea. Imprime exports copy/paste para `CLAUDE_ACTIVE_TASK_ID` + `CLAUDE_TASK_PACK`.
- `/next-slice` — arranca la siguiente slice con gate de aprobación y pipeline completo. El pipeline termina en `tester pass` — NO invoca `closer` directamente; deja ese paso a `/verify-slice`.
- `/verify-slice` — verificación humana-real con hard reset + fixtures + logs vivos. Si la slice queda verificada, orquesta al `closer` para commit atómico + configured Git workflow. Si encuentra issues, orquesta al `debugger`. Resiliente al `/clear`.
- `/revise-slice <TASK_ID> "motivo"` — reabre una slice canónica sin cambiar el DAG ni crear IDs temporales; corrige, revalida, verify y closer correctivo.
- `/phase-gate <PHASE_ID>` — valida que la phase está realmente cerrada antes de abrir la siguiente: tasks done, reports/evidence/handoffs, journeys verified/waived y Git limpio opcional.
- `/register-followup propose|promote|waive|list` — convierte hallazgos reales de validator/tester/verify en propuestas YAML y, tras aprobación humana, en tasks DAG persistentes en source-of-truth + registry + work-items.
- `./scripts/sync-product-baseline.sh status|sync` — mantiene `docs/base-app/` como snapshot construido acumulativo para el siguiente incremento.
- `/verify-journey <JID>` — gate humano end-to-end **a nivel journey** (multi-pantalla, no por slice). Se lanza tras el `closer` de la ÚLTIMA slice de un journey declarado en la Journey Coverage Matrix de `instrucciones.md` (sección §3.5 en base-app, §3.7 en feature-app — el bootstrap la localiza por nombre, no por número). `journey_gate_mode=frontier` es el default: `pending_journey_verifications[]` solo difiere tasks que referencian esos journeys; `strict` mantiene el rechazo global legacy de `/next-slice`. Hard reset + fixtures consolidados + reproducción del flujo entero + estados marginales (empty/error/permission/back/deep_link) + next action. Resiliente al `/clear`.
- `/slice-maintain clean|compact` — mantenimiento entre slices (limpieza + compactación de PROGRESS.md).

Recommended order when closing a slice: tester pass → (optional `/clear` to free context) → `/verify-slice` (spawns `closer` if verified) → `/slice-maintain clean` → `/clear` → `/next-slice`.

## Follow-ups formales

Si aparece trabajo real fuera del TASK_ID actual, no se deja en el handoff como nota suelta. Validator/tester/debugger/verify crean propuesta con `register-followup-task.sh propose`; el main-orchestrator promueve o waivea con decisión humana. Las propuestas `high|critical|blocker` bloquean nuevas waves, claims y cierre por closer hasta resolverse.

## PROGRESS.md

- `orchestrator-state/memory/PROGRESS.md` is the live project snapshot.
- `developer` updates it after EVERY slice.
- After `/clear`: read PROGRESS.md FIRST before any other action.
- All subagents' first read on start.
- PROGRESS.md is a DERIVED artifact — the five source-of-truth docs remain the authority when present; legacy 3-doc projects remain compatibility-only.

## Entry points

- Start: `claude --agent main-orchestrator --permission-mode bypassPermissions`.
- Bootstrap: run skill `bootstrap-three-doc-project` (once).
- Slice: `/next-slice`.
- Verify: `/verify-slice`.
- Maintain: `/slice-maintain clean` or `/slice-maintain compact`.

## Operating priorities

1. Validate the source-of-truth contract.
2. Backend lint + frontend lint must pass at all times.
3. Consult official frontend AND backend framework docs before implementation.
4. Execute only dependency-ready tasks.
5. After each slice: verify backend health + verify in browser + run ALL tests.
6. Require handoff, validator approval, tester pass, `VERIFY_OUTCOME: verified` from `/verify-slice`, closer baseline sync + commit + push before `done`, and (when the slice closes a journey) `JOURNEY_VERIFY_OUTCOME: verified` from `/verify-journey` before the next `/next-slice`.
7. Keep context small. Daily read = `PROGRESS.md` + per-task pack (`orchestrator-state/tasks/task-packs/<TASK_ID>.md` in DAG; `active-task.md` only in legacy/sequential mode).

## Compact instructions

During compaction preserve:

- current phase and task IDs + task status,
- source document paths,
- `orchestrator-state/memory/PROGRESS.md` path (read FIRST after compaction),
- frontend dev server status + URL,
- backend server status (running, port, health),
- database status (migrations applied, seed loaded),
- unresolved discrepancies with official docs,
- active risks, blockers, last test results.

**`/slice-maintain compact` (compactación operativa de PROGRESS.md)** se ejecuta solo bajo gate humano y con verificación post-compact obligatoria: snapshot previo, promoción append-only de decisions+risks a sus ficheros canónicos, preservación de TODOS los commit SHAs, UUIDs seed, must-carry bullets, last N slices verbatim. Si la verificación post-compact detecta que algún elemento crítico falta en el resultado, restaura desde snapshot y aborta. **Nunca pierde información crítica.**
