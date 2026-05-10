# Decisions log

> Append-only log of substantive architectural and operational decisions extracted from PROGRESS.md compactions and slice handoffs.
> Each entry is one line: `**Slice — Title**: decision summary (≤25 words). Source: <slice-id>.`
> Newest entries at the top of each compact group.

## From PROGRESS.md compact 2026-05-10

- **P00-S02-T005 — Productive verification bundle**: `bundle_type`-aware loaders (synthetic vs productive); auth loader SQL fully aligned to TECHNICAL_GUIDE §10.3 (`users.status`, argon2id `password_hash`, Fernet-encrypted `mfa_totp_secrets.secret_encrypted`); AgentSeed extra fields (`agent_type`, `framework`, `parent_agent_name`, `subagent_topics`); orphan synthetic `politica_vacaciones_es.json` removed; `.env.local` references via `*_env` JSON fields. Source: P00-S02-T005.
- **P00-S02-T004 — CWE-532 architectural fix**: structlog `ConsoleRenderer` configured with `RichTracebackFormatter(show_locals=False)` as global primary mitigation + `_REDACTED_KEYS` extended (`pwd`, `dsn`, `database_url`, `connection_string`) as defense-in-depth. This lifts the T002 "no `exc_info=True`" cultural restriction — future callers are mechanically safe. Source: P00-S02-T004.
- **P00-S02-T002 — Health endpoints shape**: `/health` and `/live` keep flat `{status, version, uptime}` for T001 compose backward-compat (NOT migrated to `{data:{...}}` envelope); redis/litellm reported as `not_implemented` (forward-compatible, not faked); `_sanitize_db_error()` strips DSN before returning. Source: P00-S02-T002.
- **P00-S02-T001 — Compose stack pins (Rancher-ready)**: `pgvector/pgvector:pg18-bookworm`, `redis:8-alpine`, `litellm:v1.83.14-stable`, `nginx-unprivileged:1.29-alpine`, `python:3.13-slim-bookworm`. Postgres host port `5433` (avoids local 5432 conflict). LiteLLM `start_period: 120s` (slow init). Worker healthcheck disabled until P02-S04-T002 Celery `inspect ping`. Source: P00-S02-T001.
- **P00-S01-T003 — Backend deps choice**: `pyjwt[crypto]` over `python-jose` (modern FastAPI standard 2026); `asyncpg`-only (no psycopg2-binary) — covers SQLAlchemy async + Alembic async; hatchling editable install via `[tool.hatch.build.targets.wheel] packages = ["app"]` + `backend/README.md`. Source: P00-S01-T003.
- **P00-S01-T002 — Frontend deps pins**: `react-router-dom@7` is a thin re-export of `react-router` (P01-S03-T001 planner must choose API intentionally); `zod@4.4.3` pinned with v3 → v4 breaking changes documented in handoff. Source: P00-S01-T002.
- **P00-S01-T004 — Design system architecture**: tokens via CSS custom properties in `shared/styles/tokens.css` + TS string mirror in `shared/styles/index.ts` (exports names as strings, not values); component naming `MobileFrame` (TECHNICAL_GUIDE wins over instrucciones `MobileShell`); `tsconfig.node.json` requires `"composite": true` for `tsc -b`; jsdom CSS-var test pattern: `getAttribute('style').toContain('var(...)')` not `toHaveStyle({ prop: 'var(...)' })`. Source: P00-S01-T004.
