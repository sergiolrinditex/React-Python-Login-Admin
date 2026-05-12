# Tester Summary — P01-S02-T008

**OUTCOME: pass**
**Timestamp: 2026-05-12T07:19:00+02:00**

## Acceptance Criteria vs Evidence

| # | Criterion | Evidence File | Grep Snippet | Result |
|---|-----------|---------------|-------------|--------|
| (a) | `scripts/dev-restart.sh --reset` exits 0 on clean DB | reset-run-1.log (last line: RESET1_EXIT=0) | `RESET1_EXIT=0` | PASS |
| (b) | `back.log` contains `verification_data.auth.users.ok inserted=N` with N>=1 | backlog-grep.txt | `inserted=2 skipped=0 updated=0` | PASS |
| (c) | `SELECT count(*) FROM users` >= 1 | psql-users-count.txt | `count = 2` | PASS |
| Idempotency | Second `--reset` exits 0, count still >= 1 | reset-run-2.log (last line: RESET2_EXIT=0); psql confirms count=2 | `RESET2_EXIT=0`, `count=2` | PASS |

## Fix Verification (git diff)

File: `scripts/dev-restart.profile.sh`
Evidence: git-diff-profile.patch

Key changes confirmed:
1. `--source "${ROOT_DIR}/data/verification"` (absolute path, cwd-independent)
2. `fail "verification_data bootstrap failed; see ${BACK_LOG}."` (hard-fail replaces warn-only return 0)
3. `log "verification_data bootstrap complete."` (AFTER log on success)
4. Stale "P00-S02-T004 (FU-20260511145446)" comment removed from header

## Servers Status
- Backend: UP (GET /health → 200)
- Frontend: UP (HTTP 200 at localhost:5173)
- Postgres: UP (via /ready and direct psql)

## Backend Tests
- Total in suite: 73 tests
- Passing: 71
- Failing: 2 (test_signin_success_no_mfa, test_signin_mfa_required_branch)
- Failure cause: Pre-existing T009 JWT key issue (InsecureKeyLengthWarning / InvalidSignatureError)
  — JWT_SECRET_KEY is 0 bytes (missing/placeholder); tracked by FU-20260512044309-generate-32-byte-jwt-dev-key
  — NOT introduced by P01-S02-T008 (this slice only edits scripts/dev-restart.profile.sh)
- Evidence: backend-tests.txt

## Frontend Tests
- Total: 58 tests
- Passing: 58
- Evidence: frontend-tests.txt

## Logging Verbosity
- BEFORE log: "==> Loading verification_data (real/provided fixtures)..." visible in reset-run-1.log
- AFTER log: "==> verification_data bootstrap complete." visible in reset-run-1.log
- structlog line: "verification_data.auth.users.ok inserted=2" visible in back.log
- No PII/tokens observed in logs (raw password/secret/sk- grepped — none found)

## Failure-path Sanity
- fail() helper defined in scripts/dev-restart.sh line 58: `fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }`
- Confirmed exit 1 semantics — script does not continue silently on seed error
- No destructive simulation performed (not needed per task pack)

## Data Contract
- Verification Data Contract row J100 auth-login: exercised
- Real/provided fixtures from data/verification/ loaded
- 2 users persisted in users table (confirmed psql count)
- Evidence: data-contract-used.txt, contract-observed.txt
