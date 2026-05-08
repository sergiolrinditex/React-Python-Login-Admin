# Validation report — external-state audited orchestrator

> Nota 2026-05-05: este informe se conserva como reporte historico del orquestador original external-state. La auditoria vigente de produccion DAG, con BaseApp refactorizada a 13 phases, 84 tasks, 8 journeys y 8 waves, esta en `AUDIT_REPORT.md`. Los conteos antiguos de este documento no son el contrato operativo actual.

Date: 2026-04-30

## Scope

Audited the Claude Code orchestrator, docs, templates, hooks, scripts, agents and BASEAPP source-of-truth flow.

Primary goals:

1. Keep `.claude/` as static Claude Code configuration only.
2. Move mutable state to `orchestrator-state/`.
3. Keep autonomous mode with `bypassPermissions`.
4. Enforce spawn budget as 20 everywhere.
5. Ensure rules are visible to commands and subagents.
6. Validate templates fail when unfilled and BASEAPP works when copied to `docs/source-of-truth/`.
7. Keep macOS/Linux portability.

## Key fixes validated

- Runtime state writes now go to:
  - `orchestrator-state/tasks/`
  - `orchestrator-state/memory/`
  - `orchestrator-state/agent-memory/`
  - `orchestrator-state/dev-logs/`
  - `orchestrator-state/hook-errors.log`
- Hook commands run with `python3 -B -S` to avoid Python bytecode writes under `.claude/`.
- `scripts/dev-restart.sh` writes logs to `orchestrator-state/dev-logs/`.
- Legacy migration utility that modified another checkout's Claude config was removed from the clean engine package.
- `slice-clean.sh` does not prune Claude static configuration.
- Agents no longer use Claude project auto-memory; manual memory is explicit and external.
- Every agent has a mandatory startup section to read the five `.claude/rules/*.md` files directly.
- Every command has an explicit rule-loading note.
- Spawn budget is 20 in settings, docs, agents, rules, tests, runtime defaults and bootstrap output.

## Static validation executed

```bash
python3 -B -S -m compileall -q .claude/bin scripts
python3 -B -S -m unittest discover -s .claude/bin/tests
python3 -B -S -m json.tool .claude/settings.json
bash -n scripts/*.sh
bash -n .claude/scripts/*.sh
```

Result:

```text
compile_ok
69 tests passed
settings_json_ok
shell_syntax_ok
```

The design-token suite intentionally prints one violation fixture during its negative test; the test result is still green.

## Source-of-truth flow validation

### Empty `docs/source-of-truth/`

```text
EMPTY_SOURCE_FAILS_OK
```

Expected: the engine ZIP is not an active app, so bootstrap must fail until the source-of-truth docs are present.

### Templates accidentally copied as active docs

Copied the three templates into `docs/source-of-truth/` under active filenames.

```text
TEMPLATES_FAIL_OK
```

Expected: bootstrap rejects template markers and prevents Claude Code from building from unfilled docs.

### BASEAPP active app simulation

Copied the three BASEAPP docs into `docs/source-of-truth/` and executed:

```bash
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
./scripts/reset-for-new-project.sh
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-journey-matrix.sh --strict
```

Result:

```text
BASE_COUNTS phases=6 tasks=84 journeys=11 budget=20
Journey matrix coherent — 11 journeys validadas, 0 drifts
```

## Hook smoke validation

Simulated Claude Code hook payloads using stdin JSON.

### SubagentStop — developer trailer

Input trailer:

```text
CLAUDE_TRAILER:
TASK_ID: P00-S01-T001
OUTCOME: pass
NEXT_STATUS: review_pending
HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md
EVIDENCE: orchestrator-state/tasks/evidence/P00-S01-T001
```

Result:

```text
HOOK_STATUS review_pending developer subagent_stop 20
```

### PreToolUse Agent — spawn budget

Preloaded `spawns_in_current_slice` to 20.

Result:

```text
SPAWN_DECISION deny
```

The 21st Agent call is denied with `permissionDecision: deny`.

### SessionStart

Result:

```text
SESSION_OK
```

The injected context includes active task, spawn count and `Mutable state root: orchestrator-state/`.

## Write-location audit

Validated in a temporary copy after bootstrap and hook simulation:

```text
NO_MUTABLE_WRITES_IN_CLAUDE_OK
```

No generated Python bytecode or mutable task/memory directories appeared under `.claude/`.

Final packaging cleanup removes Python caches, test caches, generated task state, generated memory state, dev logs, hook-error logs, lock files and runtime evidence.

The package keeps only:

```text
.claude/                  static Claude Code configuration
orchestrator-state/README.md
```

## Audit conclusion

The orchestrator is ready as an autonomous Claude Code engine:

- `.claude/` remains static.
- Runtime state persists safely outside `.claude/`.
- Memory quality is preserved through `orchestrator-state/memory/` and `orchestrator-state/agent-memory/`.
- Rules are explicit for both commands and subagents.
- Spawn budget is mechanically enforced at 20.
- BASEAPP source-of-truth validates and bootstraps.
- Unfilled templates are rejected.
- Hooks are worktree-safe and write to the canonical main repo state root.
