# Risk register

> Append-only log of non-blocking risks, deferred work, and open issues extracted from PROGRESS.md compactions and slice handoffs.
> Each entry: `**Slice — Title** [severity]: description (≤30 words). Status: open|resolved|deferred. Source: <slice-id>.`
> Newest entries at the top of each compact group.

## From PROGRESS.md compact 2026-05-10

- **P00-S02-T001 — postgres host port 5433** [medium]: postgres mapped to host `:5433` (not 5432) to avoid local sibling-project conflict. Alembic from host MUST use port 5433. `.env.example` documents Mode A (host:5433) vs Mode B (in-compose:5432). Status: open. Source: P00-S02-T001.
- **P00-S02-T001 — LiteLLM ~2min cold start** [low]: `litellm:v1.83.14-stable` needs ~2min to initialize. Compose `start_period: 120s`. May slow CI pipelines — track for P05 hardening. Status: open (deferred to P05). Source: P00-S02-T001.
- **P00-S02-T001 — Worker Celery healthcheck pending** [low]: worker service has no HTTP port; compose healthcheck disabled. Real `celery inspect ping` healthcheck lands in P02-S04-T002. Status: deferred to P02-S04-T002. Source: P00-S02-T001.
- **P00-S02-T002 — DSN/password leak via exc_info=True** [resolved by P00-S02-T004]: structlog Rich-traceback `show_locals=True` was rendering frame locals (asyncpg `cparams` with host/user/password). Originally fixed locally in T002 by dropping `exc_info=True`; globally fixed in T004 with `RichTracebackFormatter(show_locals=False)` + extended `_REDACTED_KEYS`. Status: resolved. Source: P00-S02-T002 (origin), P00-S02-T004 (global fix).
- **P00-S02-T004 — exc_info=True now globally safe** [resolved]: T002's "no `exc_info=True` anywhere" cultural restriction is mechanically lifted by global structlog config. Defense-in-depth `_REDACTED_KEYS` (`pwd`, `dsn`, `database_url`, `connection_string`) covers residual risk. Status: resolved (fix verified by 12/12 leak grep checks). Source: P00-S02-T004.
