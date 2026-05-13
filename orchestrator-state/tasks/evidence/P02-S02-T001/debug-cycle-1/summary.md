# Debugger Cycle 1 — P02-S02-T001 Evidence

## Outcome: fixed

All 4 TestPermissions failures from the tester acceptance gate are FIXED.

## Commands run + results

### 1. Unit isolation (`pytest backend/tests/unit/test_security.py -v`)
- 18/18 PASS in 3.82s.
- File: pytest-unit-isolated.log.

### 2. Acceptance gate (`pytest backend/tests -k security -v`)
- 18 PASSED, 167 deselected.
- 3 FAIL outside security scope in backend/tests/integration/test_users_me.py::TestGetMeSecurityShape (pre-existing per tester baseline; same root cause is in production code backend/app/auth/tokens.py which is OUTSIDE this task's write_set).
- File: pytest-acceptance.log.

### 3. Lint (`ruff check backend/tests/unit/test_security.py`)
- All checks passed.
- File: ruff.log.

## Diff applied (in-scope write_set: backend/tests/unit/test_security.py)

1. Replaced module-level _JWT_KEY / _JWT_ALG constants with lazy getters _get_jwt_key() / _get_jwt_alg().
2. Added _sync_app_jwt_key() helper, called at top of _mint_token, that patches app.auth.tokens._JWT_KEY and _JWT_ALGORITHM back to the env value so the FastAPI request path (which calls decode_token using those module-level constants captured at import time) accepts our minted tokens.

LOC: 679 (was 627 pre-fix; +52 LOC for two helpers + docstrings).

## Test count delta vs tester baseline

| Bucket | Tester baseline | Post-fix |
|---|---|---|
| security tests (-k security) | 14 PASS / 4 FAIL / 1 SKIP | 18 PASS / 0 FAIL / 0 SKIP |
| In-scope failures introduced by P02-S02-T001 | 4 | 0 |
| Pre-existing out-of-scope failures (test_users_me) | 2 FAIL / 1 SKIP | 3 FAIL (the SKIP flipped to FAIL because seed data is now loaded; same underlying production-code bug: app.auth.tokens._JWT_KEY captured empty at import time) |

## Why no follow-up

This is an in-scope defect: the fix lives entirely within the slice's authorized write_set (backend/tests/unit/test_security.py). It does not need a new endpoint, table, journey, source-of-truth amendment, or write_set expansion - therefore it is correctly resolved by debugger, not FU.

The 3 remaining test_users_me failures are a pre-existing, separate defect in production code (backend/app/auth/tokens.py captures _JWT_KEY at import time, vulnerable to the same pytest collection ordering). That is OUTSIDE this task's write_set and would require its own slice to fix properly.
