# Verbose Modes Summary — P01-S02-T011

## ENABLE_VERBOSE_LOGGING=true

**How tested**: Spun up a temporary uvicorn instance on port 8012 with
`ENABLE_VERBOSE_LOGGING=true`. Redirected stdout+stderr to
`logs-verbose-on.txt`. Executed:
- POST /api/v1/auth/sign-up (happy path → 201)
- POST /api/v1/auth/sign-up (duplicate → 409)

**Result**: PASS
- BEFORE/AFTER/ERROR log entries visible for every function/endpoint in the flow:
  - `BEFORE auth.sign_up.start: validating sign-up request`
  - `BEFORE auth.repository.insert_user`
  - `AFTER auth.repository.insert_user`
  - `BEFORE auth.repository.insert_employee_profile`
  - `AFTER auth.repository.insert_employee_profile`
  - `BEFORE auth.repository.insert_audit_log`
  - `AFTER auth.repository.insert_audit_log`
  - `AFTER auth.sign_up.ok: user created`
  - `ERROR auth.repository.insert_user: IntegrityError (duplicate email)` (duplicate path)
- `$argon2id$` count in logs-verbose-on.txt: **0** (ACCEPTANCE GATE PASS)
- Emails appear as `p***@example.com` (masked — no PII leak)
- No passwords, tokens, or hashes in any log line
- sqlalchemy.engine logger: NO bind-param records (echo=False permanent, T012)

## ENABLE_VERBOSE_LOGGING=false

**How tested**: Used the already-running production backend on port :8000 which
reads `ENABLE_VERBOSE_LOGGING=false` from root `.env`. Measured `back.log` file
size before and after a sign-up call.

**Result**: PASS
- Log file size before sign-up: 36914 bytes
- Log file size after sign-up: 36914 bytes (no change)
- Interpretation: no INFO/DEBUG lines emitted — only WARNING+ visible
- This is the correct behavior per `01-non-negotiables.md §Logging`:
  "ENABLE_VERBOSE_LOGGING=false shows only warning+error"

## Contract-observed

- Structlog `_REDACTED_KEYS` contains `password_hash` (T1 unit verifies directly)
- `_redaction_processor` replaces `$argon2id$...` values under `password_hash` key
  with `***REDACTED***`
- SQLAlchemy engine `echo=False` permanent (T012 / commit 4ccf7b0) — zero
  bind-parameter records emitted through stdlib `sqlalchemy.engine` logger
- Both defense layers confirmed active and effective

## curl-check endpoints

- `curl POST /api/v1/auth/sign-up (happy)` → 201 `{"data":{"mfa_required":true,...}}`
- `curl POST /api/v1/auth/sign-up (dup)` → 409 `{"errors":[{"code":"AUTH_EMAIL_TAKEN",...}]}`
- No `$argon2id$` in either response body
