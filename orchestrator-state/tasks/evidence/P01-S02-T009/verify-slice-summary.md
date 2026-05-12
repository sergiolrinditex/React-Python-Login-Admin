# verify-slice evidence summary — P01-S02-T009

Mode: pre-closer
Verifier: main-orchestrator (sandbox-tmpdir reproduction; live uvicorn probe on :18019; pytest regression)
Timestamp: 2026-05-12T07:34:00+02:00

## Sandbox tests (CLAUDE_PROJECT_DIR=tmpdir)

| # | Test | Expected | Observed | Pass |
|---|------|----------|----------|------|
| S1 | Run 1 on placeholder .env | changed=3, JWT len=64, HS256 symmetric, ENABLE_VERBOSE_LOGGING=true | exactly that | ✅ |
| S2 | Run 2 on rotated .env (idempotency) | changed=0, SHA unchanged | exactly that | ✅ |
| S3 | Fresh-clone (no .env, only .env.example) | script copies .env.example→.env then rotates | exactly that | ✅ |
| S4 | No-secret-leak (key prefix grep in evidence logs) | no leak | no leak | ✅ |

## Live backend probe (uvicorn :18019, source project .env)

| # | Test | Expected | Observed | Pass |
|---|------|----------|----------|------|
| L1 | Application startup complete | banner appears | banner appears (3s to /live=200) | ✅ |
| L2 | No `tokens.jwt_key.too_short` warning | no match | no match | ✅ |
| L3 | No `tokens.jwt_key.missing` warning | no match | no match | ✅ |
| L4 | No other WARNING/ERROR at startup | none unrelated | none | ✅ |
| L5 | /live returns `{"data":{"status":"ok"}}` | 200 OK | 200 OK | ✅ |

## Pytest regression (DB up, .env sourced)

| # | Test | Expected | Observed | Pass |
|---|------|----------|----------|------|
| R1 | `pytest backend/tests -q` | 73/73 pass | 73/73 pass in 23.06s | ✅ |

## Environmental note (NOT a T009 defect)

First pytest run after entering this verify session reported 20 failures: all `relation "users" does not exist`. The Postgres database (`hilo_dev`) had only the `alembic_version` table — schema had been dropped between tester run (07:35 earlier today) and this verify (~07:33 now). Re-running `alembic upgrade head` (using `~/Library/Python/3.11/bin/alembic`) recreated all 9 auth tables and pgcrypto extension, then 73/73 tests pass.

Root cause: a sibling slice verify (T008 dev-restart `--reset` race per FU-20260512052820) or manual restart between runs likely tore the DB down without re-applying migrations.

T009 changed only `.env.example`, `scripts/setup-from-scratch.sh`, and added `scripts/gen-dev-secrets.sh` — none touch DB schema, migrations, or test setup. T009 cannot have caused this and the existing FU-20260512052820 already tracks the dev-restart race. No new FU needed.

## Decision

VERIFY_OUTCOME: verified
