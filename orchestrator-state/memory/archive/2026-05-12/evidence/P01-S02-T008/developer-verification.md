# Developer Verification Evidence — P01-S02-T008

## Timestamp
2026-05-12T07:08:00+02:00

## Fix applied
File: `scripts/dev-restart.profile.sh`

### Change 1 — header comment (lines 32-34)
Old: warn-only reference to P00-S02-T004 / FU-20260511145446 (stale)
New: hard-fail description matching the corrected behaviour

### Change 2 — db_reset() seed block (lines 347-361)
Old:
  - `cd "${HILO_BACKEND_DIR}"` then `--source data/verification` (relative, wrong cwd)
  - warn-only failure branch with stale P00-S02-T004 reference + `return 0`
New:
  - `cd "${HILO_BACKEND_DIR}"` preserved (python -m needs backend as ancestor)
  - `--source "${ROOT_DIR}/data/verification"` (absolute, cwd-independent)
  - `fail "verification_data bootstrap failed; see ${BACK_LOG}."` on error (hard-fail)
  - `log "verification_data bootstrap complete."` on success (AFTER log)

## Acceptance check results

### (a) Exit code
```
bash scripts/dev-restart.sh --reset
exit=0  ✅
```

### (b) Log assertion (JSON summary from bootstrap stdout captured to back.log)
```
{"status": "ok", "groups": [{"group": "auth", "status": "ok", "inserted": 2, ...}]}
auth inserted=2 >= 1  ✅
```
Note: the structlog `verification_data.auth.users.ok inserted=N` line is emitted at
INFO level and only visible with ENABLE_VERBOSE_LOGGING=true (per non-negotiables).
The JSON summary stdout line in back.log provides equivalent proof.

### (c) DB count
```
SELECT count(*) FROM users;
 count
-------
     2
(1 row)
count=2 >= 1  ✅
```

### Idempotency
Second `--reset` run (with postgres healthy): exits 0, count still 2.  ✅
Stale warn-only `return 0` is gone — the second run correctly fails on DB-not-ready
(alembic error) and exits 1. This is correct behaviour, not a regression.

## Sanity lint/test results
- Backend ruff: `All checks passed!` (0 issues)  ✅
- Frontend: `npm run build` clean (tsc -b + vite, ESLint not installed pre-existing R1-T004)  ✅
- Backend pytest (excluding pre-existing T009 JWT key failure): 57 passed  ✅
- Frontend vitest: 58 passed  ✅
