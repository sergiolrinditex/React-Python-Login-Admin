# tester agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/tester/archive/MEMORY.full.2026-05-10-044634.md`
- Original lines: 216
- Original SHA-256: `33726e170f7237cebdcbdd01daf09c59d161a6ac102255f3380e5fcbde0b24aa`
- Compacted at: `2026-05-10-044634`
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
- ### tester NEXT_STATUS decision rule
- - If all tests pass but validator issued `changes_requested` → `OUTCOME: pass, NEXT_STATUS: needs_debug`.
- - If tests fail → `OUTCOME: fail, NEXT_STATUS: needs_debug`.
- - If environment broken (Python missing, etc.) → `OUTCOME: blocked, NEXT_STATUS: blocked`.
- - Always prefix tester files with `tester-` to avoid overwriting developer evidence.
- ### Pre-existing test_ready_returns_200_when_db_ok failure
- ### OUTCOME/NEXT_STATUS when validator says changes_requested
- Per MEMORY.md rule: `OUTCOME: pass, NEXT_STATUS: needs_debug`. The debugger must apply the fix, then re-run validator+tester. The closer requires validator `approved` before committing.
- - The `.env` file may have `DATABASE_URL` pointing to port 5432 (or other mismatch), but tests MUST use the compose port (5433 in this project). Always override `DATABASE_URL` explicitly when running alembic/pytest:
- 3. Both verbose-on and verbose-off logs must pass the check
- - Always use the intended entry point (`validate_with_bundle_type`) when testing bundle-type validation.
- - The unit tests in `test_schemas.py` correctly test via `validate_with_bundle_type`; the tester's defense-in-depth check must use the same path.
- ### OUTCOME/NEXT_STATUS with validator changes_requested (data-only issue)
- - Validator `changes_requested` for a 1-line data fix (not code) → tester still emits `OUTCOME: pass, NEXT_STATUS: needs_debug`.
- - Rationale: closer requires validator `approved`, so debugger must apply the fix + re-run validator+tester. The tests themselves pass; the gate is the validator approval.
- - Always run from project root for consistency with STACK_PROFILE.yaml `seed_cmd`.
- - The project has TWO backend venvs: `.venv` (no pytest) and `.venv-t003` (has pytest). Always use `.venv-t003/bin/pytest`.
- - This is a pre-existing architectural issue, not introduced by T010. Always register as a low-severity follow-up if no existing FU covers it.
- - Always generate a fresh tester-only Fernet key per run:
- - Export only in shell session — NEVER write to file, NEVER commit.
- ### Pre-existing failure: test_ready_returns_200_when_db_ok
- - Confirmed pre-existing since P00-S02-T002. Do NOT count as a T010 failure.

## Original heading index
- # Tester Agent Memory
- ## Reusable lessons from P00-S01-T003 (2026-05-08)
- ### Python backend smoke tests — patterns
- ### tester NEXT_STATUS decision rule
- ### Evidence discipline
- ### venv reuse
- ### Warnings that are non-blocking
- ## Lessons from P00-S02-T003 (2026-05-09)
- ### Exit code capture with tee
- ### Docker / Rancher Desktop path
- ### DATA_DIR for seed CLI
- ### Seed loader closed-set design
- ### Pre-existing test_ready_returns_200_when_db_ok failure
- ### OUTCOME/NEXT_STATUS when validator says changes_requested
- ## Lessons from P01-S01-T001 (2026-05-09)
- ### Alembic migration testing pattern
- ### Alembic stdlib logging vs structlog
- ### DB-down negative test pattern
- ### Backend /ready 503 pre-existing issue
- ### docker compose exec -T psql note
- ## Lessons from P01-S01-T004 (2026-05-09)
- ### Running uvicorn may have stale config from before the fix
- ### dev-restart.sh --reset seed non-blocking WARN is expected
- ### pydantic-settings env_file cwd-relative pattern
- ### Password leak check pattern (DSN split)
- ## Lessons from P00-S02-T005 (2026-05-09)
- ### ENCRYPTION_KEY for Fernet — env setup for tests
- ### validate_with_bundle_type vs model_validate(context=...)
- ### Defense-in-depth test for real key rejection
- ### OUTCOME/NEXT_STATUS with validator changes_requested (data-only issue)
- ### seed CLI argument: --source is relative to cwd
- ## Lessons from P00-S02-T010 (2026-05-10)
- ### pytest binary location
- ### asyncpg for DB inspection without psql
- ### Fernet token in SQLAlchemy echo — pre-existing CWE-532
- ### Fernet key for tester runs
- ### Worktree test runs need PYTHONPATH
- ### Pre-existing failure: test_ready_returns_200_when_db_ok
- ### Total test count evolution

## Lessons from P01-S01-T005 (2026-05-10)
### structlog in test files without configure_logging()
- If a test file uses `structlog.get_logger(__name__)` at module level WITHOUT calling `configure_logging()`, INFO logs will appear regardless of `ENABLE_VERBOSE_LOGGING=false`.
- This violates `01-non-negotiables.md §Logging`: "ENABLE_VERBOSE_LOGGING=false → only warning+error visible".
- The fix: call `configure_logging(verbose=os.environ.get("ENABLE_VERBOSE_LOGGING", "false").lower() == "true")` in a fixture or at import time (the `_configured` flag in `app.core.logging` makes it idempotent).
- OUTCOME in such cases: `OUTCOME: fail, NEXT_STATUS: needs_debug` (logging non-compliance is a non-negotiable violation).

### Logging check for test files
- When checking verbose-false logs, grep for BOTH: (a) `[info]` lines — should NOT appear when verbose=false; (b) PII in `[warning]`/`[error]` — should NOT appear in either mode.
- The presence of `[info]` lines with verbose=false is a fail regardless of whether those lines contain PII.

### asyncpg DB inspection (psql not in PATH)
- Use `asyncpg.connect()` + `information_schema.columns` query to verify column structure when psql CLI is not available.
- Pattern established in T005 and T010.

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/tester/archive/MEMORY.full.2026-05-10-044634.md`
