---
name: write-handoff
description: Standard format for task handoff files. One file per task — `developer` initializes, `validator`/`tester`/`debugger` append sections. Never overwrite.
user-invocable: false
allowed-tools: Read Write Edit
---

Every slice produces exactly one handoff: `orchestrator-state/tasks/handoffs/<TASK_ID>.md`. In explicit DAG mode the handoff TASK_ID must match `CLAUDE_ACTIVE_TASK_ID` and `orchestrator-state/tasks/task-packs/<TASK_ID>.md`; never append to a handoff for another task even if `active-task.md` points there.

## Base structure (initialized by `developer`)

```
# Task Handoff — <TASK_ID>

## Metadata
- Task ID:
- Phase / Slice:
- Timestamp:
- Workers involved: developer[, validator, tester, debugger, closer]

## Scope
- Goal of the task:
- Files changed:

## Developer run
- Commands executed:
- Important decisions (+ doc source reference):
- Official docs consulted (if any):
- Verification results:
- Evidence paths:

## Risks / open points (initial)
- Remaining risk:
- Follow-up actions:

## Acceptance coverage (initial)
- Item by item vs task pack:
```

## Appended sections

Sections are appended in execution order; workers never overwrite earlier sections. Validator/tester/debugger append only to the current `<TASK_ID>` file; if the requested path, trailer, pack or environment disagree, stop instead of writing. The closer's pre-check verifies these sections exist with the expected trailer values.

- `validator` appends **## Validator review** with: scope OK/issues, arquitectura OK/issues, logging OK/issues, tests realness OK/issues, PROGRESS.md OK/issues, security scope disparado/no, hallazgos críticos, `OUTCOME: approved|changes_requested|blocked`, `SECURITY_GATE: pass|warn|fail`.
- `tester` appends **## Tester run** with: servers status, tests backend (count + status), tests frontend (count + status), curl checks, logging check verbose on/off, hallazgos críticos, `OUTCOME: pass|fail|blocked`, evidence dir.
- `debugger` appends **## Debugger fix** with: hipótesis inicial, causa raíz, fix aplicado, verificaciones reejecutadas. On the 4th failed cycle appends **## debugger-exhausted** instead with `RECOMMENDED_NEXT_ACTION`.
- `/verify-slice` (human gate) appends **## verify-slice** with: `TIMESTAMP`, `MODE: pre-closer|post-closer`, `VERIFY_OUTCOME: verified|issues_found`, `FIXTURES` (what was injected), `FLOWS_TESTED`, `FINDINGS` (bullets if issues_found, empty if verified), `EVIDENCE` path. The closer's pre-check requires this section with `VERIFY_OUTCOME: verified` — **or** an explicit line `VERIFY_WAIVED: <reason>` if the user waived verification manually for a slice without UI.
- `closer` reads the handoff and writes the evidence report in `orchestrator-state/tasks/reports/<TASK_ID>.md`. It does not append to the handoff.

## Trailer lines

At the end of each worker's FINAL assistant message (not in the handoff file — in the chat), always add machine-readable lines. The SubagentStop hook parses them and syncs registry.

```
CLAUDE_TRAILER:
TASK_ID: <TASK_ID>
OUTCOME: <agent-specific>
NEXT_STATUS: <agent-specific>
HANDOFF: orchestrator-state/tasks/handoffs/<TASK_ID>.md
[EVIDENCE: orchestrator-state/tasks/evidence/<TASK_ID>/]   ← tester/closer only
```

The `CLAUDE_TRAILER:` marker is mandatory. It keeps the hook from parsing an
example log or markdown snippet earlier in the answer as the final state.
