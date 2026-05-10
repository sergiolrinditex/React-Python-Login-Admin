# /verify-slice P00-S02-T011 — evidence summary

Generated: 2026-05-10T07:00:21Z
Mode: pre-closer (no commit yet, evidence report not yet written)

## Hard reset path executed (worktree)
- worktree: `.claude/worktrees/agent-a7c1e8d887fd75bdc`
- branch: `worktree-agent-a7c1e8d887fd75bdc` (HEAD aaf9e84 = T007)
- venv: symlink to main `backend/.venv-t003` (fast non-destructive)
- data/: symlink to main `/data` (verification bundle live there)
- profile: copied main's fixed `dev-restart.profile.sh` (matches what closer commits)

## Acceptance criteria results
- AC1 (ensure_encryption_key idempotent + valid Fernet generation): PASS
  - rm worktree .env → setup-from-scratch.sh → .env auto-created with len=44 valid base64 url-safe key (****y7A=); legacy PROVIDER_ENCRYPTION_KEY removed; key never echoed.
- AC2 (bootstrap_verification_data --only auth exit 0 without manual export): PASS
  - exit_code=0; auth namespace seeded (mfa_totp_secrets encrypted via pydantic-settings ENCRYPTION_KEY).
- AC3 (Fernet encrypt/decrypt round-trip + discover-models endpoint sanity): PASS
  - in-process round-trip: 32-byte plaintext encrypted+decrypted cleanly with worktree .env key (****y7A=).
  - curl POST /api/v1/admin/ai/providers/<id>/discover-models → 401 (auth guard, NOT 502 CryptoError).

## Security verification (cycle-1 fix on dev-restart.profile.sh)
- main's dev-restart.profile.sh (uncommitted, M) does NOT persist key to disk → verified by restarting back with main's profile applied to worktree: encryption-key.runtime NOT created.
- .gitignore covers orchestrator-state/dev-logs/* with .gitkeep exception (lines 58-62).
- repo-wide tracked-file audit: 0 plaintext 44-char Fernet candidates outside package-lock.json (NPM sha512 false-positives).
- worktree .env never committed (gitignored).

## Out-of-scope findings discovered during verify (register as follow-ups)
1. **medium**: `.env.example` has `DATABASE_URL=postgresql+asyncpg://hilopeople:<change-me>@...` — bash `source .env` fails with `change-me: No such file or directory`. Fresh dev clone scenario after `setup-from-scratch.sh` cannot `source .env` because the angle-bracket placeholder is interpreted as redirection. Affects T011's claim "fresh dev clone … bootstrap_verification_data succeeds without manual export".
2. **medium**: `.env.example` has `JWT_PRIVATE_KEY=<dev-rsa-private-key-pem-placeholder>` and `JWT_PUBLIC_KEY=<dev-rsa-public-key-pem-placeholder>` — same root cause as (1).
3. **low**: `.env.example` has `RESEND_API_KEY=<change-me>` — same root cause.
   - Common fix: quote with single quotes or use a default that doesn't embed `<`/`>`. Out of T011 write_set (T011 scope only ENCRYPTION_KEY in .env via ensure_encryption_key).

## Pre-existing tracked findings (re-confirmed during verify)
- FU-20260508230723 (low): `MAIL_FROM_NAME=Hilo People` unquoted in .env (in main, also in worktree pre-quoting). Already promoted to P01-S01-T003.
- "Owed: rotate VERIFICATION_GEMINI_API_KEY in GCP" (T009 hygiene leftover). Confirmed: admin_ai seed fails when env var absent. Out of T011 scope.

## Evidence files
- verify-setup-from-scratch.log
- verify-dev-restart.log
- verify-dev-restart-soft.log
- verify-seed-only-auth.log
- verify-curl-discover-models.log
- verify-fernet-roundtrip.log
- verify-gitignore.log
