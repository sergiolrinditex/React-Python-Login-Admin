# validator agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/validator/archive/MEMORY.full.2026-05-09-221733.md`
- Original lines: 272
- Original SHA-256: `1eb485834e493aee49a9dc8dfc90ab4d4b33c1636812840fb2453d07a9f947aa`
- Compacted at: `2026-05-09-221733`
- When a detail is not present below, read the full archive before making assumptions.

## Current operating invariants
- Treat `.claude/orchestrator-contract.json` and `.claude/rules/` as the source of operational truth.
- Keep writes scoped to the active DAG task and agent write contract.
- Use follow-ups for out-of-slice work; do not mutate generated DAG/runtime files directly.

## Trailer vocabulary
- `OUTCOME`: `Read .claude/orchestrator-contract.json`
- `NEXT_STATUS`: `Read .claude/orchestrator-contract.json`
- Always read `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` before emitting trailers.

## High-signal preserved notes
- git status --porcelain | grep -E "^( M|MM)" | grep -E "(\.claude/|docs/source-of-truth/|...)"
- - `.env.example` audit: every secret-bearing var must be `<change-me>` or non-sensitive default. Flag any real-looking value (sk-..., real domains, real ports outside dev range, etc.).
- - Always check for `noqa`/`type: ignore`/`@ts-ignore` and require an inline justification.
- - `bash scripts/check-progress-updated.sh --auto` — exit 0 pass / 1 missing / 2 docs-only / 3 inconclusive / 4 error. Must run on every review.
- NEVER acceptable: `try: import x except ImportError: pass` — that pattern PASSES even if the import broke. Flag as critical.
- 4. Grep negative test: `grep -rEn "border-radius:\s*[1-9]" frontend/src/` and `grep -rEn "rounded-(sm|md|lg|...)"` MUST return zero hits outside the theme root.
- The `# noqa: F841` is the signal: locals are intentional, secrets must be IN the frame and NOT in the exception message — otherwise the test could pass for the wrong reason (sanitizer cleaning the message).
- - **Verbose-mode forced reset for log-pipeline tests**: `configure_logging` is idempotent via a module-level `_configured` guard. Tests that need to validate a different verbose mode must reset the guard:
- 3. `_common.py` (or `_shared.py`) hosts ONLY symbols genuinely used by ≥2 sibling modules — never speculative "might be useful later" types.
- 4. No cross-namespace imports inside the package (every sibling imports only from `_common`, never from another sibling) → eliminates circular-import risk by construction.
- - Verify the diff boundary: confirm the file's current state matches the user-approved values verbatim. Use a repo-wide grep for any leftover stale strings (must be 0 hits).
- ## Productive seed bundle data verification — repo-wide grep contract
- - Must show **0 hits for old_value** (clean revert) and **expected hit count for new_value** (typically just the JSON file itself).

## Original heading index
- # Validator memory — Hilo People
- ## Conventions established (verified live)
- ## Bootstrap-generated files vs developer edits
- ## Scaffold slice acceptance baseline
- ## Security checklist baselines
- ## Useful gates / scripts
- ## Red flags learned
- ### From P00-S01-T003 (backend dependency pack)
- ### Logging gate refinements
- ### Smoke test realness checks (sampling)
- ### From P00-S01-T004 (frontend design tokens & editorial system)
- ### From P00-S02-T001 (Docker compose stack — Rancher-ready)
- ### From P00-S01-T005 (i18n bundles ES/EN/FR)
- ### From P00-S02-T002 re-review (post-debugger CWE-532 fix)
- ### From P00-S02-T004 (CWE-532 architectural fix promoted from T002 follow-up)
- ### From P00-S02-T003 (seed loader + verification bundle)
- ### From P00-S02-T003 cycle 1 re-review (post-debugger split fix)
- ### From P01-S01-T001 (Alembic baseline migration + ORM models)
- ### From P01-S01-T004 (env_file path resolution + DATABASE_URL port fix)
- ### From P00-S02-T005 (productive verification bundle)
- ## Cycle-2 (post-debugger) review pattern — focused, not full
- ## Honest developer flag earns ratification credit
- ## Productive seed bundle data verification — repo-wide grep contract
- ## Cycle-3 (post-debugger + post-orchestrator-scrub) review pattern
- ## Test fixture using productive credentials as the test value — anti-pattern signature

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/validator/archive/MEMORY.full.2026-05-09-221733.md`
