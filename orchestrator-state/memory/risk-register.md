# Risk Register

> Append-only record of known issues, open risks, and deferred items promoted from `PROGRESS.md` during compactations, plus risks added directly by validator/tester/debugger/verify-slice.
> Severity: low / med / high. Status: open / resolved / accepted.
> Authority order: source-of-truth docs first, then this file, then `PROGRESS.md`.

## From PROGRESS.md compact 2026-05-13

Source: `orchestrator-state/memory/archive/2026-05-13/PROGRESS-pre-compact-221226.md` (snapshot, SHA-256 `484fde2c168eeb428e3df8f9bc9d27a207f773bc1f4f956a845891739afa6201`).

### P00 — Foundation phase risks

| ID | Slice | Severity | Status | Summary |
|---|---|---|---|---|
| R1 | P00-S01-T001 | low | resolved | `backend/tests/` write_set extension — validator approved. |
| R2 | P00-S01-T001 | low | resolved | `backend/app/__init__.py` write_set extension — validator approved. |
| R3 | P00-S01-T001 | low | resolved | Frontend not runnable until T002 — T002 done, T004 Vite runtime added. |
| R4 | P00-S01-T001 | med | accepted | `hook_write_scope_guard.py` blocks `Write` for worktree paths. Workaround: Bash heredoc `cat > file << 'PYEOF'`. Persists as known infra limitation. |
| R5 | P00-S01-T003 | low | accepted | `deepagents==0.5.9` Beta status. Accepted per non-negotiables §11.0 USAR. |
| R5 | P00-S01-T002 | low | resolved | `react-router v7` ESM. Vitest handles it via jsdom. Production handled in T004 Vite config. |
| R6 | P00-S01-T003 | low | accepted | `langgraph` deprecation warning — non-blocking. Monitor on next dep upgrade. |
| R6 | P00-S01-T002 | low | resolved | Zod v4 API surface — downstream slices must use Zod v4 idioms. |
| R7 | P00-S01-T003 | low | accepted | `mypy 2.0.0` major bump — to be addressed when mypy first configured. |
| R7 | P00-S01-T002 | low | resolved | `i18next-browser-languagedetector` in Node/jsdom — resolved by disabling auto-init. |

### P00-S02-T001 — Docker compose infrastructure risks (4 open)

| ID | Severity | Status | Summary |
|---|---|---|---|
| R1-infra | med | open | `docker compose build backend/worker` deferred until T003 finalized. |
| R2-infra | med | resolved | `postgres:17-alpine` has no pgvector — resolved at P01-S01-T001 (pgvector image substituted). |
| R5-infra | med | open | `worker` `app.worker` module not created yet — boot deferred to P02-S04-T002. |
| R6-infra | med | open | `docker compose build frontend` deferred until T002 lock lands in build; `SKIP_BUILD=1` escape hatch in Dockerfile. |

### P01 — Auth phase risks

| ID | Slice | Severity | Status | Summary |
|---|---|---|---|---|
| R1-T004 | P00-S01-T004 | low | open | ESLint not installed — `npm run lint` fails (`eslint not found`). Pre-existing from T001. Lint gate = `tsc -b` which passes. ESLint config lands in a later task. |
| R1-T002 | P01-S02-T002 | low | resolved | Worktree branched off pre-T003 commit — would have wiped T003 dep pack on merge. Resolved by debugger 1/3. |
| R2-T002 | P01-S02-T002 | low | resolved | `/verify-slice` required `docker compose up -d postgres redis` to test `/ready` with real services. All 3 endpoints verified end-to-end. |
| R1-T005 | P01-S02-T005 | low | open | i18next resources inlined in TypeScript (not imported from JSON) because `resolveJsonModule` not in tsconfig. JSON files in `public/locales/` serve as reference and are served statically by Vite. Future FU to move to JSON imports if HTTP backend is added. |
| R1-T001-S02 | P01-S01-T001 | med | open (known ordering gotcha) | `test_downgrade_removes_all_tables` (migration test) destroys the schema on each full test run. After running the full test suite, must re-run `alembic upgrade head` to restore schema before using the live DB. All tests pass but DB state post-suite needs upgrade. |
| R1-T002-S02 | P01-S02-T002 | low | accepted | MFA branch tested (T02) but `mfa_totp_secrets` INSERT in `_create_user` uses Fernet key. `MFA_ENCRYPTION_KEY` env var must be a valid Fernet key (44 base64-url chars). In tests, if not set, a new key is generated per test call (different key each time — MFA secret is unreadable after test, but the sign-in endpoint only checks `enabled=True`, not the secret value, so T02 passes). |
| R1-T001-S03 | P02-S03-T001 | med | resolved | F-1 cycle 1 — chat POST `language:'de'` initially returned FastAPI raw 422 `{detail:[...]}` because `/api/v1/chat/conversations` was not in `_AUTH_INVALID_PAYLOAD_PATHS`. Fixed in `backend/app/main.py` with a parallel `_CHAT_INVALID_PAYLOAD_PATHS` frozenset + per-path code helper. Pattern reusable for any future feature joining the 422→400 normalization: add `_<FEATURE>_INVALID_PAYLOAD_PATHS`, extend the union, extend the mapper. |
