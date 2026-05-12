# Verify-slice Evidence Summary — P01-S01-T001

TASK_ID: P01-S01-T001
Mode: pre-closer
Timestamp: 2026-05-11T15:05:00Z
Verifier: main-orchestrator (verify-slice command)
Verify outcome: **VERIFIED**

## Worktree used

Developer worktree (not yet merged to main):
`.claude/worktrees/agent-a9c2e2f9442e1f02f/` (branch `worktree-agent-a9c2e2f9442e1f02f`, base e30c547).

The closer will merge it into main.

## Hard reset performed

- alembic downgrade base (from head 0001) → 9 tables dropped reverse-FK; pgcrypto kept (D2).
- alembic upgrade head (verbose=true) → 9 tables + pgcrypto recreated with BEFORE/AFTER INFO logs.
- alembic downgrade -1 → 9 tables dropped again; alembic_version preserved.
- alembic upgrade head (verbose=false) → 9 tables recreated with EMPTY stdout (silent mode confirmed).
- After integration tests (which run their own teardown) → re-upgrade head to leave DB at head for next slices.

DB seed (verification_data loader) intentionally skipped — pre-existing :meta::jsonb cast bug already captured as out-of-scope FU; not a T001 defect.

## SQL probes (real INSERT/DELETE, no mocks)

| # | Probe | Result |
|---|-------|--------|
| P1 | CHECK ck_users_users_language_chk rejects 'pt' | PASS — CheckViolation as expected |
| P2 | UNIQUE users_email_key rejects duplicate email | PASS — UniqueViolation as expected |
| P3 | FK CASCADE on user delete clears employee_profiles + refresh_tokens + user_roles | PASS — all child rows = 0 |
| P4 | FK SET NULL on audit_logs.actor_user_id preserves audit row (GDPR Art. 30) | PASS — actor_user_id=NULL, action='LOGIN' preserved |
| P5 | gen_random_uuid() + now() defaults work on INSERT | PASS — UUID + timestamp emitted |

## Schema introspection (live DB)

- Tables: 9 (no missing, no extra)
- CHECK constraints: 1 (users.preferred_language ∈ {es,en,fr})
- UNIQUE constraints: 4 (users.email, employee_profiles.employee_id, roles.name, permissions.key)
- FOREIGN KEYS: 7 (6× CASCADE on user-derived children, 1× SET NULL on audit_logs.actor_user_id)
- D6 NOT NULL: refresh_tokens.user_id and password_reset_tokens.user_id confirmed
- D7 indexes: token_hash, user_id+revoked_at, role_id, audit actor+created, audit entity, audit created_at — all present
- TIMESTAMPTZ: 7 columns (users.created_at/updated_at, refresh_tokens.expires_at/revoked_at, password_reset_tokens.expires_at/used_at, audit_logs.created_at) all `timestamp with time zone`; 0 naive timestamps

## Tests re-run

- 6/6 PASS — backend/tests/integration/test_migrations_0001_auth.py (10.99s)
- 37/37 PASS — full backend suite excluding 2 known-broken P00-S02-T003 tests (14.60s)
- Ruff: All checks passed!

## Logging verification

- verbose=true: BEFORE/AFTER INFO per table create/drop; only structural references (table names); zero leaked secret-like values
- verbose=false: EMPTY stdout (silent mode correct)

## Backend smoke (running pre-T001 backend)

- GET /health → 200 `{"status":"ok","version":"0.1.0","uptime":2894s}`
- GET /live → 200 `{"status":"ok"}`
- GET /ready → 200 `{"db":"ok","redis":"ok","litellm":"unknown"}`

## Screen/Journey review

Status: **not_applicable**. This slice has `kind: db`, empty `route`/`endpoint`, and no UI surface. `journey_refs:[J100,J102]` only document which journeys these tables enable; `list_journey_closures.py P01-S01-T001 --json` returns `closing_journeys:[]`. Validator already gated `marginal_states_gate: n/a` (DB-only, no pantallas, UX_CONTRACT §3.7 N/A confirmed by planner).

## Discrepancy notes

- `P01-S01-T001-sqlalchemy-timestamptz-2026-05-11.md` — RESOLVED on disk; resolution verified against live DB (7 TIMESTAMPTZ, 0 naive).
- `P00-S02-T002-sqlalchemy-sync-ping-2026-05-11.md` — RESOLVED implicitly by this slice (env.py NullPool pattern confirmed working; line in §J of handoff).
- `P00-S02-T001-infra-compose` and `P00-S02-T002-fastapi-healthcheck` notes — warn-only carryover from P00 slices; not relevant to T001.

## Open follow-ups (info)

- `FU-20260511145446-fix-verification-data-loader-meta-jsonb-sql-cast` — proposed, medium, out_of_scope, origin P00-S02-T003. Does NOT block this closer (severity below high/critical/blocker; outside T001 write_set).

## Evidence files

- `verify-01-pre-state.txt` — alembic current/heads/history from worktree
- `verify-02-downgrade-base.txt` — hard reset to base
- `verify-03-upgrade-head-verbose-on.txt` — upgrade with verbose logs + PII scan
- `verify-04-schema-introspect.txt` — tables, constraints, FKs, indexes
- `verify-04b-employee-profiles-columns.txt` — column shapes for P3 retry
- `verify-05-sql-probes.txt` — 5 real SQL invariant probes
- `verify-06-downgrade-cycle.txt` — downgrade -1 + verbose=false re-upgrade
- `verify-07-backend-smoke.txt` — backend health + ruff
- `verify-08-integration-tests.txt` — 6 + 37 pytest runs
- `verify-09-timestamptz-confirm.txt` — TIMESTAMPTZ authoritative check
