# Runtime write contract

This rule is the human-readable mirror of `.claude/orchestrator-contract.json`. Read the JSON when you need exact paths or per-agent permissions.

## Principle

`.claude/` is static orchestrator configuration. Runtime state, memory, evidence, handoffs and reports live under `orchestrator-state/`. During normal app-building slices, agents must not edit `.claude/`; use `CLAUDE_ALLOW_STATIC_CONFIG_WRITES=1` only for intentional orchestrator maintenance.

## DAG task scope

In explicit DAG mode, every worker terminal is scoped by:

```bash
CLAUDE_ACTIVE_TASK_ID=<TASK_ID>
CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md
```

The `TASK_ID` in the environment, the task pack name, handoff path, evidence dir and report path must all match. If they do not match, stop before writing. The legacy `orchestrator-state/memory/active-task.md` is advisory only and may belong to another terminal.

## Generated core state

Do not edit these files with Write/Edit/MultiEdit during a slice:

```text
orchestrator-state/tasks/registry.json
orchestrator-state/tasks/runtime-state.json
orchestrator-state/tasks/ledger.jsonl
orchestrator-state/memory/task-dag.json
orchestrator-state/memory/task-dag.md
orchestrator-state/memory/execution-graph.json
orchestrator-state/memory/active-task.json
orchestrator-state/memory/active-phase.json
```

They are written by bootstrap, claim scripts and hooks under locks. If repair is truly needed, stop and run the dedicated script or ask for explicit maintenance mode.


## Production DAG trailer vocabulary

Closed trailer enums live in `.claude/orchestrator-contract.json` → `trailer_schema.roles.<agent-name>.outcome_values` and `trailer_schema.roles.<agent-name>.next_status_values`. Read that path before emitting the trailer. Scope writes by `CLAUDE_ACTIVE_TASK_ID`/`CLAUDE_TASK_PACK`; never edit generated registry/runtime/task-dag directly. Use `/register-followup` for discovered work outside current slice.

The machine-readable source of truth for agent trailer values is:

```text
.claude/orchestrator-contract.json -> trailer_schema.roles.<agent-name>
```

Each role declares:

- `required_keys`
- `outcome_values`
- `next_status_values`
- whether the role mutates registry lifecycle or is info-only

Agent markdown may show examples, but the JSON schema is authoritative. `hook_capture_subagent_stop.py` loads `trailer_schema` first and falls back to legacy mirrors only for damaged/partial installs.

## Agent write map

- `planner`: writes/enriches `orchestrator-state/tasks/task-packs/<TASK_ID>.md`; may mirror to `active-task.md` only in legacy; does not write product code.
- `developer`: writes product code for the slice, `PROGRESS.md`, handoff and evidence under the same `TASK_ID`.
- `official-docs-researcher`: writes only official-doc notes and its memory.
- `validator`: append-only handoff review; no product code edits.
- `tester`: evidence under the same `TASK_ID` and append-only handoff test section; no product-code fixes.
- `debugger`: smallest safe product-code fix for the same `TASK_ID`, plus handoff/evidence.
- `closer`: report, sync product baseline, atomic commit plus configured Git workflow, `configured Git workflow (`./scripts/git-workflow.sh`)`, then safe worktree cleanup; no product-code edits and no `Co-authored-by: Claude` trailer.
- bootstrap agents (`document-analyzer`, `project-architect`, `task-planner`): may shape source docs and architecture memory before execution starts, not during an active DAG task.

## Product baseline snapshot

`docs/base-app/` is the cumulative built baseline passed back to ChatGPT for the next product increment. It mirrors the current accepted `docs/source-of-truth/` after verified closure and includes `BASELINE_MANIFEST.json`. Do not hand-edit it during an active task; closer/safe maintenance sync it with:

```bash
./scripts/sync-product-baseline.sh sync --version <baseapp|v1|v2|current> --task <TASK_ID>
./scripts/sync-product-baseline.sh status
```

The Coverage Registry columns `Product increment` and `Build state` are mandatory in new templates. Existing built rows should be `Build state=done`; new increment rows should start `planned` unless intentionally forced.

## Source-of-truth edits

`docs/source-of-truth/` may be edited while generating or reconciling the five source-of-truth docs. Do not edit it while a slice is active. If the contract changes, rerun:

```bash
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
```

## UX and verification-data contract

For UI work, the task pack must include the journey, route/page, endpoints consumed, client state/provider, required UI states and next action. A frontend slice is not complete until loading, empty, network error, validation error, permission denied and success states are either implemented or explicitly marked not applicable in the source-of-truth.

`/verify-slice` and `/verify-journey` must also use the `Verification Data Contract` from the TECHNICAL_GUIDE. Productive closure uses real or prod-like sandbox data, never decorative mocks. Evidence must state the contract rows used, fixtures injected and persisted data observed.

## Mechanical enforcement

`hook_write_scope_guard.py` blocks the dangerous cases: writing static `.claude/` config during app execution, writing another task's handoff/evidence/report/task-pack, editing source-of-truth/base-app during an active task, hand-writing follow-up YAML, or directly editing generated core state. `hook_capture_subagent_stop.py` also rejects false `done` from closer unless report, commit, push and worktree cleanup proof are present.

## Follow-up tasks from validator/tester findings

A real production finding must never remain only as prose in a handoff. Use this split:

- **In-scope bug for the current TASK_ID**: keep the same slice, mark the lifecycle `needs_debug`, run `debugger`, then rerun `validator ‖ tester` and `/verify-slice`.
- **Out-of-scope gap, missing wiring, missing real-data fixture, UX gap, or future production risk**: create a formal follow-up proposal YAML:

```bash
./scripts/register-followup-task.sh propose \
  --origin-task <TASK_ID> \
  --severity high|medium|low \
  --kind bug|ux|wiring|data|test|security|followup \
  --title "<short title>" \
  --description "<what was found and why it matters>" \
  --journey-ref <JID> \
  --conflict-group <group> \
  --write-set '<path-or-glob>' \
  --acceptance "<done means>" \
  --verify "<real/prod-like verification>"
```

Only the main orchestrator promotes or waives it after explicit human decision:

```bash
./scripts/register-followup-task.sh promote <FOLLOWUP_ID>
./scripts/register-followup-task.sh waive <FOLLOWUP_ID> --reason "<human decision>"
```

Promotion appends a `Runtime Follow-up Coverage Registry` row to the implementation checklist, updates `registry.json`, regenerates the DAG adjacency, writes `work-items/<TASK_ID>.yaml`, and updates runtime-state/ledger under locks. High/critical/blocker proposals block `/next-wave`, `claim_task.py`, and closer `done` until promoted or waived.
