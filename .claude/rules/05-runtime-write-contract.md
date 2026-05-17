# Runtime write contract

This rule is human guidance for agents. `.claude/orchestrator-contract.json` is the only machine-readable runtime policy for hooks, exact paths and per-agent permissions.

## Principle

`.claude/` is static orchestrator configuration. Runtime state, memory, evidence, handoffs and reports live under `orchestrator-state/`. During normal app-building slices, agents must not edit `.claude/`; use `CLAUDE_ALLOW_STATIC_CONFIG_WRITES=1` only for intentional orchestrator maintenance.

## DAG task scope

In explicit DAG mode, every worker terminal is scoped by:

```bash
CLAUDE_ACTIVE_TASK_ID=<TASK_ID>
CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md
```

The `TASK_ID` in the environment, the task pack name, handoff path, evidence dir and report path must all match. If they do not match, stop before writing. There is no implicit selector in DAG-only mode; never infer work without explicit `TASK_ID`.

## Canonical vs workspace state

Worktree execution has two roots. Keep them separate:

- **Canonical root** (`$CLAUDE_ORCHESTRATOR_ROOT`): shared DAG state and generated memory (`registry.json`, `runtime-state.json`, `PROGRESS.md`, `task-dag.*`, `execution-graph.json`). Agents read this for scheduling truth; scripts/hooks mutate it under locks.
- **Workspace/worktree root** (`$PWD`, `CLAUDE_WORKTREE_ROOT`, or `CLAUDE_PROJECT_DIR`): per-slice artifacts that must be committed with the task branch (`handoffs/<TASK_ID>.md`, `evidence/<TASK_ID>/`, `reports/<TASK_ID>.md`, `task-packs/<TASK_ID>.md`).

Never copy scheduler truth from a task worktree back into the canonical root. Never stage shared runtime files to "fix" a dirty worktree. Use the scripts that know the split. The only close-state artifact that travels in a PR is `orchestrator-state/tasks/lifecycle-events/<TASK_ID>.json`; after merge, `sync-lifecycle-events.sh --apply` replays it into local `registry.json` under locks.


## Machine-readable handoff hygiene

Each agent-owned handoff section must use exactly one markdown heading for the logical section (`## Developer run`, `## Validator review`, `## Tester run`, `## Debugger fix`, `## verify-slice`, `## Screen/Journey review`). Inside that section, machine-readable fields must be plain key lines, preferably bullets:

```markdown
- AGENT: validator
- TASK_ID: P00-S01-T001
- OUTCOME: approved
```

Do not write field lines as markdown subheadings such as `### AGENT: validator` or `### OUTCOME: approved`; those can split sections in simple parsers. The checker tolerates this mistake for recovery, but agents must write the clean format. A heading hygiene defect is mechanical orchestration noise, not a product bug and not a follow-up candidate.

## Generated core state

Do not edit these files with Write/Edit/MultiEdit during a slice:

```text
orchestrator-state/tasks/registry.json
orchestrator-state/tasks/runtime-state.json
orchestrator-state/tasks/ledger.jsonl
orchestrator-state/tasks/bash-ledger.jsonl
orchestrator-state/memory/task-dag.json
orchestrator-state/memory/task-dag.md
orchestrator-state/memory/execution-graph.json
```

These are generated/derived files and only scripts/hooks may update them under locks.

`registry.json`/`runtime-state.json` are local scheduler state. They may be generated or repaired by hooks/scripts, but they are not slice PR payload. If a root sync/reset shows them dirty, do not create a manual `sync post-close state` commit; run `bash scripts/sync-lifecycle-events.sh --apply` or let `/next-wave`/SessionStart do it.

Removed removed singleton files:

```text
orchestrator-state/memory/implicit selector.json
orchestrator-state/memory/implicit selector
orchestrator-state/memory/implicit selector.json
orchestrator-state/memory/implicit selector.md
```

Bootstrap, claim scripts and hooks must never generate those singleton files. If they appear after upgrading an old repo, delete them; do not use them as context or task authority.


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

Agent markdown may show examples, but the JSON schema is authoritative. `hook_capture_subagent_stop.py` validates against `trailer_schema`; if the schema is unavailable or a role is missing, it logs a visible error and refuses lifecycle mutation.

## Agent write map

- `planner`: writes/enriches `orchestrator-state/tasks/task-packs/<TASK_ID>.md`; does not write product code.
- `developer`: writes product code for the slice, `PROGRESS.md`, handoff and evidence under the same `TASK_ID`.
- `official-docs-researcher`: writes only official-doc notes and its memory.
- `validator`: append-only handoff review; no product code edits.
- `tester`: evidence under the same `TASK_ID` and append-only handoff test section; no product-code fixes.
- `debugger`: smallest safe product-code fix for the same `TASK_ID`, plus handoff/evidence.
- `closer`: report, sync product baseline, atomic commit via configured Git workflow (`./scripts/git-workflow.sh`), then safe worktree cleanup; no product-code edits, no `Co-authored-by: Claude` trailer, and no `git stash`/`git stash pop` close flow. If pre-push changes are still required, amend/commit them explicitly instead of stashing generated hook state.
- bootstrap agents (`document-analyzer`, `project-architect`, `task-planner`): may shape source docs and architecture memory before execution starts, not during an active DAG task.

## Product baseline snapshot

`docs/product-baseline/` is the cumulative built baseline passed back to ChatGPT for the next product increment. It snapshots the current accepted `docs/source-of-truth/` after verified closure and includes `BASELINE_MANIFEST.json`. Do not hand-edit it during a DAG task; closer/safe maintenance sync it with:

```bash
./scripts/sync-product-baseline.sh sync --version <v0|v1|v2|current> --task <TASK_ID>  # closer only; requires verified handoff
./scripts/sync-product-baseline.sh status
```

The Coverage Registry columns `Product increment` and `Build state` are mandatory in new templates. Existing built rows should be `Build state=done`; new increment rows should start `planned` unless intentionally forced.

## Source-of-truth edits

`docs/source-of-truth/` may be edited while generating or reconciling the five source-of-truth docs. Do not edit it while a slice is active. If the contract changes, rerun:

```bash
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
```

## UX and verification-data contract

For UI work, the task pack must include the journey, route/page, endpoints consumed, client state/provider, required UI states and next action. A frontend slice is not complete until loading, empty, network error, validation error, permission denied and success states are either implemented or explicitly marked not applicable in the source-of-truth.

`/verify-slice` and `/verify-journey` must also use the `Verification Data Contract` from the TECHNICAL_GUIDE. Productive closure uses real/provided sandbox data, never decorative mocks. Evidence must state the contract rows used, provided verification data loaded and persisted data observed.

## Mechanical enforcement

`hook_write_scope_guard.py` blocks the dangerous cases: writing static `.claude/` config during app execution, writing another task's handoff/evidence/report/task-pack, editing source-of-truth/baseline snapshot during an DAG task, hand-writing follow-up YAML, or directly editing generated core state. `hook_capture_subagent_stop.py` also rejects false `done` from closer unless report, commit, push and worktree cleanup proof are present.

## Follow-up tasks from validator/tester/verify findings

A production finding must never remain only as prose in a handoff, but a follow-up is also **not** a substitute for debugger/retest. Use this split before creating any FU:

- **In-scope defect for the current `TASK_ID`**: acceptance is already in the task pack, paths are in `Write set`/`allowed_paths`, no new route/endpoint/table/journey/data contract is needed. Do **not** create FU. Mark lifecycle `needs_debug`; the main-orchestrator runs `debugger`, reruns `validator ‖ tester`, then reruns `/verify-slice`. Subagents must not spawn subagents.
- **Out-of-scope work / missing coverage**: requires source-of-truth amendment, new screen/endpoint/table/journey, `Write set` or `Conflict group` expansion, missing real/provided data contract, external dependency, or explicit human product decision. Create FU immediately with `register-followup-task.sh propose`; do not leave it as prose for the user to translate into YAML.
- **Unclear classification**: stop and ask the main-orchestrator/user. Do not create a blocking FU just to move on.

Every FU proposal must explain why it is not going through debugger/retest:

```bash
./scripts/register-followup-task.sh propose \
  --origin-task <TASK_ID> \
  --severity high|medium|low \
  --kind bug|ux|wiring|data|test|security|followup \
  --scope-classification out_of_scope|missing_coverage|missing_real_data|external_dependency|future_enhancement|scope_expansion|blocked_by_human_decision \
  --why-not-debugger "<why validator/tester -> debugger -> retest cannot fix this inside TASK_ID>" \
  --title "<short title>" \
  --description "<what was found and why it matters>" \
  --journey-ref <JID> \
  --conflict-group <group> \
  --write-set '<path-or-glob>' \
  --acceptance "<done means>" \
  --verify "<verification with real/provided data>"
```

The script rejects `--scope-classification in_scope_defect` and requires `--why-not-debugger` for `high|critical|blocker` proposals. `validator`, `tester` and `debugger` should normally emit `FU_PROPOSAL:*` machine-readable fields in their handoff instead of mutating runtime while the parallel pair is still racing. The main-orchestrator registers exactly one proposal with `propose`, after checking duplicates. No subagent calls `promote`; `screen-journey-reviewer` only writes `followup_candidate=yes` for `/verify-slice` to register. That prevents FU spam while keeping real out-of-scope debt visible.

Operational lessons:

- Do not create a FU to repair a stale `write_set` string. Resolve real paths with `find`/`grep`, document the drift in the task pack/handoff, and only block if product scope is ambiguous.
- A sibling/out-of-write_set bug is `missing_coverage` or `out_of_scope`; it is not an in-scope debugger fix.
- Duplicate FU triage is a waiver decision, not a promotion decision. Subagents may recommend `duplicate_of_done=<TASK_ID|FOLLOWUP_ID>`; only the main orchestrator/user runs `waive`.
- Promoted FU with missing checklist row: do not edit source-of-truth from a worker terminal. Use the registry/work-item/FU YAML linkage and fix source-of-truth from a clean orchestrator maintenance context.

Only the main orchestrator promotes or waives it after explicit human decision:

```bash
/promote-followup <FOLLOWUP_ID>
./scripts/register-followup-task.sh waive <FOLLOWUP_ID> --reason "<human decision>"
```

Promotion appends a `Runtime Follow-up Coverage Registry` row to the implementation checklist, updates `registry.json`, regenerates the DAG adjacency, writes `work-items/<TASK_ID>.yaml`, and updates runtime-state/ledger under locks. High/critical/blocker proposals block `/next-wave` and `claim_task.py` until promoted or waived; they do not block closer `done` for the origin slice when the FU YAML is formal, referenced in the report and staged into the PR.

Git close note: `hook_update_ledger.py` writes Bash PostToolUse events to `orchestrator-state/tasks/bash-ledger.jsonl`, which is runtime-only and ignored by Git. This prevents Bash hooks from re-dirtying the working tree after the atomic commit/push in DAG close. Do not use `git stash` as the normal closer flow; stage required changes into the slice commit before running `./scripts/git-workflow.sh`.

`/verify-slice` delegates real verification to `slice-verifier`; the hook records `verified_pending_close|needs_debug|blocked` and only `closer` may mark `done`.
