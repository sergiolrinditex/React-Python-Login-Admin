# Test Count Reconciliation — P00-S02-T003
Generated: 2026-05-09

## Summary

| Source | Claimed | Actual | Match |
|--------|---------|--------|-------|
| Full suite total | 63 | 63 | YES |
| Pass | 62 | 62 | YES |
| Fail | 1 | 1 | YES |
| Failing test name | test_ready_returns_200_when_db_ok | test_ready_returns_200_when_db_ok | YES |

## Discrepancy with "T002 closed at 48/48 PASS"

PROGRESS.md records T002 as "48/48 PASS". T003 adds 11 new seed tests:

- tests/integration/test_seed_idempotency.py: 3 tests
- tests/integration/test_seed_namespaces.py: 3 tests
- tests/integration/test_seed_missing_bundle.py: 5 tests

Total after T003: 48 (T002 baseline) + 11 (T003 new) + 4 (T004 new logging tests) = 63 tests.

The PROGRESS.md "T002 closed at 48/48" refers to the state at T002 commit time. The T004 logging tests were added by a parallel developer agent but not yet committed. At the time of T002 close:

- Backend tests: 48 (39 smoke + 9 health)
- All 48 passed at that time (with DB up on :5432)

After T003 + T004 developer implementations (not yet committed):
- 63 total tests
- 62/63 pass

## The failing test

**File**: `backend/tests/test_health.py`
**Test**: `test_ready_returns_200_when_db_ok`
**Failure**: `assert 503 == 200` (HTTP 503 returned instead of 200)

**Root cause**: The app's ASGI test client uses the `DATABASE_URL` env var from `.env` which is `postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@localhost:5432/hilopeople_dev` — note **port 5432**. The actual postgres container runs on **port 5433** (to avoid conflict with local postgres). The test skip guard checks TCP connectivity on port 5433 (which succeeds), so the test runs. But the app tries to connect on 5432 (from env var) — which either fails to connect or uses a different postgres instance, leading to `InvalidPasswordError: authentication failed for user "hilopeople"`.

The error message in the test output: `InvalidPasswordError: authentication failed for user "hilopeople"` confirms this is a credentials/port mismatch, not a T003-introduced regression.

## Git attribution

**When was test_health.py authored?**

```
git log --oneline -- backend/tests/test_health.py
a6a3d86 feat(api): P00-S02-T002 — /health refactor + /live + /ready (DB probe) + X-Request-ID middleware
```

Only one commit touches this file: `a6a3d86` which is **P00-S02-T002** (not T003).

T003 has NO committed code yet (all T003 changes are in working tree, pre-close). The failing test was authored in the P00-S02-T002 commit (`a6a3d86`) dated 2026-05-09T07:14:33.

## Conclusion

The failing test is **PRE-EXISTING** from T002. It was NOT introduced by T003. Evidence:

1. Git log: only commit is `a6a3d86` (T002), predates T003 work
2. T003 changes are not yet committed (currently in working tree)
3. The failure is a config mismatch (port 5432 in DATABASE_URL vs port 5433 actual) that exists since T002

This is correctly documented in the developer handoff: "test_ready_returns_200_when_db_ok fails because the app's SQLAlchemy engine reads credentials from environment variables (hilopeople_dev_pwd), while postgres running on :5433 in this development environment has different credentials."

The developer PROGRESS.md note about "T002 closed at 48/48" is consistent IF the T002 closer ran when `DATABASE_URL` pointed to port 5432 and a postgres instance was running on 5432. The local dev environment has changed (postgres now mapped to 5433).

**VERDICT: Not a T003 regression. Pre-existing from T002.**
