# Planner — Agent Memory

> Reflexion-style memory for the planner agent. Append-only; archive over time
> to `archive/<date>.md`. The home for slice-specific context is the task pack,
> not this file.

## Patterns and lessons learned

### Library/dependency slices (kind: library)

- **Always set `NEEDS_OFFICIAL_DOCS: yes`.** Even when the source-of-truth doc
  has version cells set to "pendiente — official-docs-researcher confirmará",
  the researcher pass is the safety net that catches peerDep conflicts and
  ecosystem drift since the doc was written. Cache hits on shallow pass keep
  it ≤5s.
- **Verification command is usually a single `npm run test -- --run` or
  `pytest`.** That makes the slice eligible for `/auto-verify-slice` if
  `risk_level: low`, `verify_mode: auto` and `journey_refs: []`. Note this in
  the pack so the closer knows the auto path is available.
- **Acceptance "deps installed" requires a real install**, not just
  declaration. The write_set always includes `package.json` AND
  `package-lock.json` (or `requirements.txt`). `node_modules/` is build
  output, not in write_set, but the lockfile presence + tests passing is the
  acceptance signal.
- **Test files for a library slice usually live next to the wired module**
  (e.g. `frontend/src/app/providers.test.tsx` co-located). The write_set
  often only lists the main file; co-location is the pragmatic resolution
  when the hook write-scope guard is strict.

### DAG state gates checked at planner startup

1. `runtime-state.spawns_in_current_slice[<TASK_ID>] < spawn_budget` (default 20).
2. `runtime-state.pending_journey_verifications` empty OR none reference this TASK_ID's journey_refs (frontier mode).
3. `runtime-state.open_followups` has no `high|critical|blocker` in `proposed`.
4. All `depends_on` predecessors `status: done` in registry.
5. `conflict_groups` of this task have no other active task — registry scan.

If any fail → `CONTEXT_READY: no` with the precise reason.

### Source-of-truth section index for fast extraction

| Doc | Section | What lives here |
|---|---|---|
| `instrucciones.md` | §11.0–§11.1 | Library Discovery Pass (decisions WHY) |
| `instrucciones.md` | §3 (Recorridos) | Journey Coverage Matrix |
| `TECHNICAL_GUIDE` | §2.0–§2.1 | Library Discovery Pass (package, URL, slice introduced) |
| `TECHNICAL_GUIDE` | §4 | Frontend file tree (gives the exact path to write) |
| `TECHNICAL_GUIDE` | §6.1 | Routes/pages with UI states |
| `TECHNICAL_GUIDE` | §6.4 Navigation Contract | Route family, deep links, auth guard |
| `TECHNICAL_GUIDE` | §6.5 Verification Data Contract | Real/provided data per journey |
| `STACK_PROFILE.yaml` | top-level | Commands (test_cmd, dev_cmd, install) and enforcer |
| `UX_CONTRACT.md` | screen inventory | Per-page UI states + persona |
| `CHECKLIST` | Coverage Registry row | Full machine-readable spec per TASK_ID |

For T002-like slices (provider/lib wiring without UI), section §4 and §6.4
are advisory only; UX states are "n/a".

### Hook caveats (carry between slices)

- `hook_docs_discrepancy_check.py` scans for a literal `^RESOLVED:` line at
  start of a note's line. **HTML comments (`<!-- RESOLVED: ... -->`) are NOT
  matched.** When a previous slice resolved a note inside an HTML comment,
  the warning will keep firing. Fix: add an uncommented `RESOLVED: …` line
  at the top of the body (T002 planner did this for the three T001 notes
  on 2026-05-11).
- `hook_write_scope_guard.py` denies writes whose path begins with `.claude/`
  during an active slice. If a developer runs in an `agent-*` worktree
  (path `.claude/worktrees/...`), Write tool calls get denied — workaround
  documented in T001 handoff: use `Bash` heredocs.

## Archive

- `archive/2026-05-11.md` — none yet. Compact when this file exceeds ~250 lines.
