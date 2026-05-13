# Tester Summary — P02-S02-T001

## OUTCOME: fail

## Servers Status
- backend :8000 — UP (confirmed via curl /health → 200)
- frontend :5173 — UP (confirmed via HTTP 200)
- Redis — UP (redis://localhost:6379/0, confirmed via python3 redis.ping() → True)
- Postgres — UP (hilo_dev, users table confirmed present)

## Test Results

### Unit test_security.py — Run in isolation (from backend/ dir):
- 18/18 PASS (TestEncryption 6/6 + TestPermissions 6/6 + TestRateLimit 6/6)
- Command: pytest tests/unit/test_security.py -v

### Acceptance gate — pytest backend/tests -k security -v (from worktree root):
- 14 PASS, 4 FAIL, 1 SKIP, 167 DESELECTED
- FAILED: TestPermissions T03–T06 (in-scope defect — see below)
- FAILED (pre-existing): test_users_me SecurityShape T27, T28

### Full suite — pytest backend/tests -v:
- 163 PASS, 23 FAIL
- New failures vs baseline (22): +4 (TestPermissions T03–T06)
- Pre-existing failures: 19 (migration ordering + MFA T06 + signin + dev_restart)

## In-Scope Defect: TestPermissions T03–T06

ROOT CAUSE: backend/tests/unit/test_security.py has module-level constant:
  _JWT_KEY: str = os.getenv("JWT_PRIVATE_KEY", "")

When pytest collects all tests from backend/tests/, integration conftest 
(no .env loading) is discovered before tests/unit/conftest.py loads .env.
At collection time test_security.py is already imported, so _JWT_KEY = "".
Tokens minted with empty key → app's get_current_user sees invalid_token → 401.

WARNING in output: "InsecureKeyLengthWarning: The HMAC key is 0 bytes long"

FIX NEEDED (in-scope, write_set: backend/tests/unit/test_security.py):
Change _JWT_KEY to lazy function _get_jwt_key() called at mint time.

## Lint: 0 issues (ruff clean)

## Logging:
- verbose=true: DEBUG BEFORE/AFTER logs for all 3 services
- verbose=false: WARNING only (root logger at WARNING level confirmed)
- No PII/tokens/passwords in any log output

## Redis: 0 residual keys after test teardown
