# T014 Tester Evidence Summary

**TASK_ID**: P00-S02-T014
**Date**: 2026-05-10
**Tester**: tester agent

## Test Results

| Test | Description | Status | Notes |
|------|-------------|--------|-------|
| T1 | `bash -n setup-from-scratch.sh` syntax check | PASS | exit 0 |
| T2 | First run (sandbox idempotency) | PASS | PEM generated, "generated fresh RSA 2048 keypair" log |
| T3 | Idempotency (run 2) | PASS | sha256sum identical, "already valid" log line |
| T4 | RS256 sign+verify roundtrip | PASS | alg=RS256, key_size=2048, payload verified |
| T5a | Edge: empty values | PASS | regenerated as pair |
| T5b | Edge: `<change-me>` placeholder | PASS | regenerated as pair |
| T5c | Edge: garbage-not-pem | PASS | regenerated as pair |
| T5d | Edge: partial (valid priv + placeholder pub) | PASS | regenerated as pair |
| T5e | Edge: desynchronized keypair | PASS | deep validation caught mismatch → regenerated |
| T6 | CWE-532 logging hygiene | PASS | 0 PEM lines in script stdout/stderr |
| T7 | ENABLE_VERBOSE_LOGGING (bash script) | PASS | no set -x; PEM never echoed |
| T8 | Backend regression tests | PASS | 153 pass + 19 skipped + 0 failures |

## Acceptance Coverage (vs task pack §2.3)

| Acceptance Item | Status |
|----------------|--------|
| PEM real blocks with BEGIN/END markers | PASS |
| Valid 2048+ bits RSA | PASS (key_size=2048 confirmed) |
| pydantic-settings Settings load: priv+pub as SecretStr with real newlines | PASS |
| RS256 sign+verify roundtrip with generated keys | PASS |
| Idempotent: rerun leaves .env untouched | PASS |
| No PEM in stdout/stderr (CWE-532) | PASS |
| Backend tests not broken (regression guard) | PASS |

## Risks Verified

| Risk | Status |
|------|--------|
| R1: multi-line dotenv parse | PASS — pydantic-settings reads PEM correctly with real newlines |
| R3: --check mode position | DOCUMENTED — ensure_jwt_keypair runs before CHECK_MODE (by design, mirrors ensure_encryption_key) |
| R5: sign-up JWT acceptance | PASS — RS256 smoke substitutes per §2.3 D1 |
| R8: base64 `=` in PEM via cut -d= -f2- | PASS — greedy cut used correctly |

## Servers Status

- Backend: http://localhost:8000/health → 200 {"status":"ok",...}
- Frontend: http://localhost:5174/ → 200 OK

## Critical Findings

NONE

## Evidence Files

- `T1-syntax.txt` — bash -n check
- `T2-first-run.txt` — first run output (sandbox)
- `T3-pre-sha.txt`, `T3-post-sha.txt`, `T3-second-run.txt`, `T3-diff.txt` — idempotency
- `T4-rs256-smoke.txt` — RS256 roundtrip
- `T5-edge-cases.txt` — edge cases (a-e)
- `T6-logging-hygiene.txt` — CWE-532 guard
- `T7-verbose-flag.txt` — verbose flag analysis
- `T8-backend-smoke.txt` — backend test suite
