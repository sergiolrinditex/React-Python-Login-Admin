---
name: close-task
description: Standard for closing or rejecting a task after validator + tester gates.
user-invocable: false
allowed-tools: Read Write
---

Before marking a task as `done`, verify ALL of the following:

1. Task pack acceptance is covered. Use `orchestrator-state/tasks/task-packs/<TASK_ID>.md`; implicit selector is removed from DAG-only mode and can belong to another terminal if present from migration.
2. `validator` review exists and outcome = `approved`.
3. `tester` run exists and outcome = `pass` (or explicitly waived with documented reason).
4. Handoff file exists with sections from developer + validator + tester (+ debugger if used).
5. Evidence directory populated.
6. Risks / open items documented (handoff + optionally risk-register.md).
7. Tests are REAL (no mocks of business logic — only external APIs).
8. EVERY function/endpoint/use case has logging (BEFORE + AFTER + ERROR).
9. `ENABLE_VERBOSE_LOGGING=true` shows full flow logs for the slice.
10. `orchestrator-state/memory/PROGRESS.md` was updated with current slice results.
11. EVERY new/modified file has a docstring (what it does, slice/phase, dependencies).
12. Human verification gate passed. The handoff MUST contain a `## verify-slice`
    section with EITHER `VERIFY_OUTCOME: verified` OR an explicit
    `VERIFY_WAIVED: <reason>` line signed by the human. Loose phrases like
    "browser check documented in handoff" are NOT acceptable substitutes —
    that loophole would let the closer commit code that no human ever ran.
    The `closer` regex this gate as a literal line match; anything else
    means the slice is not closeable yet, run `/verify-slice` first.

If ANY condition is missing, `closer` fails with `OUTCOME: blocked` and lists what is missing. After the evidence report and atomic commit, closer must run `configured Git workflow (`./scripts/git-workflow.sh`)` and safe worktree cleanup; if push fails, the slice is not fully closed. The SubagentStop hook refuses to mark `done` unless the closer trailer has `REPORT_READY: yes`, `GIT_READY: yes`, `PUSH_READY: yes` and `WORKTREES_CLEANED: yes`.

## Journey-closing slices (read this even if no journey applies)

When `list_journey_closures.py <TASK_ID>` says this slice makes a journey ready for verification,
the closer MUST emit a journey trailer line in addition to the standard
lifecycle trailer. Decision tree (read the handoff to decide):

- The handoff already contains `## verify-journey` with
  `JOURNEY_VERIFY_OUTCOME: verified` for that JID
  (the `/verify-slice §5.bis` "ahora" branch ran the journey gate inline)
  → emit `JOURNEY_VERIFIED_INLINE: <JID>` (the SubagentStop hook marks it
  `verified` under lock and does NOT add it to `pending_journey_verifications`).
- The handoff contains `## verify-journey` with `JOURNEY_VERIFY_OUTCOME: issues_found`
  → `OUTCOME: blocked`. The closer must NOT commit; the debugger picks up.
- Anything else (no inline section, the user picked "aparte", or the user
  skipped §5.bis) → emit `JOURNEY_PENDING_VERIFY: <JID>`. The hook adds the
  JID to `pending_journey_verifications`. In DAG-only the planner defers only tasks that reference that journey until `/verify-journey <JID>` resolves it.

A single slice may close more than one journey (rare). Emit one
`JOURNEY_PENDING_VERIFY:` (or `JOURNEY_VERIFIED_INLINE:`) line per JID.

To detect closure: load `registry.journeys[]` and find every entry where
`python3 -B -S .claude/bin/list_journey_closures.py <TASK_ID> --json` returns a non-empty `closing_journeys[]`. If none matches, no journey trailer is
needed.
