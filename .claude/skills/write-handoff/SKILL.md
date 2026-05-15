---
name: write-handoff
description: Standard format for task handoff files. One file per task — `developer` initializes, `validator`/`tester`/`debugger` append sections. Never overwrite.
user-invocable: false
allowed-tools: Read Write Edit
---

Every slice produces exactly one handoff: `orchestrator-state/tasks/handoffs/<TASK_ID>.md`. In explicit DAG mode the handoff TASK_ID must match `CLAUDE_ACTIVE_TASK_ID` and `orchestrator-state/tasks/task-packs/<TASK_ID>.md`; never append to a handoff for another task and never use `implicit selector` to infer the destination.

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

- `developer` initializes **## Developer run** and must include handoff result lines: `AGENT: developer`, `TASK_ID: <TASK_ID>`, `OUTCOME: success|blocked|failed`, `NEXT_STATUS: validator_tester_pending|blocked`, `TIMESTAMP: <ISO-8601>`.
- `validator` appends **## Validator review** and must include handoff result lines: `AGENT: validator`, `TASK_ID: <TASK_ID>`, `OUTCOME: approved|changes_requested|blocked`, `NEXT_STATUS: ready_for_close|needs_debug|blocked`, `TIMESTAMP: <ISO-8601>`, then scope/architecture/logging/tests/progress/security gates.
- `tester` appends **## Tester run** and must include handoff result lines: `AGENT: tester`, `TASK_ID: <TASK_ID>`, `OUTCOME: pass|fail|blocked`, `NEXT_STATUS: ready_for_close|needs_debug|blocked`, `TIMESTAMP: <ISO-8601>`, then servers/tests/curl/logging/evidence fields.
- `debugger` appends **## Debugger fix** and must include handoff result lines: `AGENT: debugger`, `TASK_ID: <TASK_ID>`, `OUTCOME: fixed|blocked|failed`, `NEXT_STATUS: validator_tester_pending|blocked`, `TIMESTAMP: <ISO-8601>`, then hypothesis/root cause/fix/verification. On the 4th failed cycle appends **## debugger-exhausted** instead with `RECOMMENDED_NEXT_ACTION`.
- `slice-verifier` (launched by `/verify-slice`) appends **## verify-slice** and must include handoff result lines: `TASK_ID: <TASK_ID>`, `MODE: pre-closer|post-closer`, `MCP_BROWSER: chrome-devtools|claude-in-chrome|agent360-browser-mcp|browser-mcp`, `VERIFY_OUTCOME: verified|issues_found|blocked`, `DATA_CONTRACT_ROWS`, `DATA_SETUP`, `PERSISTED_DATA_OBSERVED`, `FLOWS_TESTED`, `FINDINGS`, `EVIDENCE`. The closer's pre-check requires this full section with `VERIFY_OUTCOME: verified` — **or** an explicit line `VERIFY_WAIVED: <reason>` if the user waived verification manually for a slice without UI.
- `closer` reads the handoff and writes the evidence report in `orchestrator-state/tasks/reports/<TASK_ID>.md`. It does not append to the handoff.

Important: the chat trailer and the handoff section are different artifacts. A worker must emit the chat trailer so hooks can sync registry, and must also write the equivalent result lines inside the handoff so `closer` can audit after `/clear`. Do not rely on one to replace the other.


## Follow-up entries

If a worker references a `FOLLOWUP_ID`, the handoff must record why it is a real out-of-scope FU, not an in-scope defect: `scope_classification`, `why_not_debugger`, affected `write_set`/`conflict_group`, and whether the slice is blocked until human decision. In-scope defects belong to `debugger` + retest, not FU.

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
