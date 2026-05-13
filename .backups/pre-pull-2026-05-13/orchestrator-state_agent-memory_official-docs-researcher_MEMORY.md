# official-docs-researcher agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.2026-05-11-141041.md`
- Original lines: 390
- Original SHA-256: `9c845e7486bb64f777b81e8eab8d5432371d543feb5d32b7815c01839970b2a5`
- Compacted at: `2026-05-11-141041`
- When a detail is not present below, read the full archive before making assumptions.

## Current operating invariants
- Use official, current/versioned documentation only unless the task explicitly permits otherwise.
- Fast lookup order: local/cache docs, ToolSearch/MCP, Context7, vendor MCP, then official WebFetch/WebSearch fallback.
- Fan out independent documentation checks in one tool batch; do not serialize unless a result depends on a prior result.
- Capture source, framework/library version, and concrete implementation implications.
- Mark missing or conflicting documentation as `insufficient` or `discrepancy`; do not invent certainty.

## Trailer vocabulary
- `OUTCOME`: `verified|discrepancy|insufficient`
- `NEXT_STATUS`: `<none>`
- Always read `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` before emitting trailers.

## High-signal preserved notes
- # Official Docs Researcher Memory
- Agent: official-docs-researcher
- Full note: `orchestrator-state/memory/official-doc-notes/P00-S02-T001-infra-compose-2026-05-11.md`
- #### Verified OK (cache valid until 2026-05-18 for stable; Docker tags are volatile, re-check before re-use)
- | postgres:17-alpine | Supported until 2029-11-08; latest minor 17.9; no critical CVEs | postgresql.org/support/versioning |
- | litellm v1.83.14-stable.patch.3 | Tag exists, stable (not prerelease); health endpoint = `/health/liveliness`; port 4000 | github.com/BerriAI/litellm/releases, docs.litellm.ai/docs/proxy/deploy |
- | litellm required env vars | `LITELLM_MASTER_KEY` (sk- prefix) required; `DATABASE_URL` optional for dev; `LITELLM_SALT_KEY` recommended | docs.litellm.ai/docs/proxy/deploy |
- | minio RELEASE.2025-09-07T16-13-09Z | Tag confirmed; server cmd `minio server /data --console-address ":9001"` correct; healthcheck `/minio/health/live` → 200 OK | github.com/minio/minio, docs.min.io |
- | mc sidecar pattern | `mc alias set` + `mc mb` + `mc admin policy attach` — all valid commands | docs.min.io |
- | Docker Compose `version:` key | Obsolete (informational only, ignored, triggers warning). Omitting it is CORRECT. | docs.docker.com/compose/compose-file/04-version-and-name |
- | `condition: service_healthy` | Valid in Compose v2 spec (moby/docker compose) | docs.docker.com/compose/compose-file/05-services/#depends_on |
- #### CRITICAL DISCREPANCY (UNRESOLVED)
- - `services.<SERVICE>.healthcheck` is explicitly listed as unimplemented in nerdctl compose docs.
- #### Minor discrepancy (UNRESOLVED)
- ## Cache entries (freshness windows: stable tech=7d, AI/ML volatile=always, Claude Code=14d)
- **Verified via npm registry + PyPI live + Context7:**
- | Package | Verified version | Source | Cache expires |
- - `__init__.py` required: YES — `backend/app/__init__.py` must exist for `uvicorn app.main:app`.
- **DISCREPANCY written:** `orchestrator-state/memory/official-doc-notes/frontend-stack-versions-2026-05-11.md`
- - Developer must escalate to human before picking React 18 vs 19.
- **Verified via PyPI live JSON + Context7 (litellm, langchain, langgraph, pgvector, tiktoken).**
- Full canonical table in: `orchestrator-state/memory/official-doc-notes/T003-pinned-versions.md`
- | pgvector | **0.4.2** | PyPI live + Context7 | 2026-05-18 |
- | litellm | **1.83.14** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |
- | langchain | **1.2.18** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |
- | langchain-core | **1.3.3** | PyPI live | ALWAYS re-verify (AI/ML) |
- | langchain-community | **0.4.1** | PyPI live | ALWAYS re-verify (AI/ML) |
- | langchain-text-splitters | **1.1.2** | PyPI live | ALWAYS re-verify (AI/ML) |
- | langgraph | **1.1.10** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |
- | deepagents | **0.5.9** | PyPI live | ALWAYS re-verify (AI/ML) |
- | mcp | **1.27.1** | PyPI live | ALWAYS re-verify (AI/ML) |
- | tiktoken | **0.12.0** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |
- #### Key gotchas verified this pass
- - **mcp**: official Anthropic MCP SDK. PyPI name = `mcp`. Maintained by Anthropic PBC. Import: `import mcp`.
- - **mypy 2.0.0**: major version bump from 1.x — verify changelog before strict mode config.
- #### Discrepancy notes written
- - `T003-discrepancy-deepagents.md` — Beta status + mandatory provider SDKs. RESOLVED: pending human decision on whether to include in T003 or defer. Not a blocker per §11.0 USAR classification.
- **Verified via npm registry live + Context7 + reactrouter.com + zod.dev/v4 + GitHub releases (testing-library).**
- - **DISCREPANCY**: Task pack says install `react-router-dom`; official v7 docs say install `react-router`.
- - Official migration: `npm uninstall react-router-dom && npm install react-router@latest`.
- - DISCREPANCY NOTE: `frontend-deps-T002-react-router-2026-05-11.md`
- - Downstream slices writing Zod schemas must use v4 API.
- - Language detector MUST NOT be registered in providers.tsx for T002 — defer to T005.
- - Minimum RTL version for React 19: **v16.1.0** (added 2024-12-05).
- #### Discrepancy notes written for T002
- **Sources**: Context7 /i18next/i18next v26.0.2, /i18next/react-i18next; i18next.com/misc/migration-guide; i18next.com/overview/configuration-options; react.i18next.com/misc/testing.
- #### i18next v26 breaking changes (verified)
- | `initImmediate` removed (use `initAsync`) | No impact — project never used `initImmediate` |
- - **VERIFIED OK**. `fallbackLng` accepts any language string. The default value in the docs is `'dev'` but any valid language code works. No documented caveat about using Spanish or any non-English language as fallback.
- - `ns: ["common","auth","chat","account","admin-ai","rag","mcp","errors"]` (8 namespaces) is the canonical pattern.
- - Official API: `missingKeyHandler` is called ONLY when `saveMissing: true`. With `saveMissing: false` (project setting), the handler is never invoked regardless of its value.
- - Setting `missingKeyHandler: false` (boolean) is non-standard (docs show function signature), but with `saveMissing: false` it has zero effect. Redundant, not a bug. No change needed.
- #### react-i18next 17 API patterns (verified)
- - No official Vite-specific i18next pattern documented.
- - Official approach: `i18n.init({ resources: { en: {...} }, lng: 'en', fallbackLng: 'en' })` inline in test setup — accepted pattern.
- - `await i18n.changeLanguage('fr')` in tests: returns a Promise. Must `await` in async test. `i18n.language` updates synchronously after resolution.
- #### Outcome: VERIFIED — all planner decisions confirmed
- No discrepancy notes written. Developer may proceed without reconciliation.
- **Verified via PyPI live JSON + argon2-cffi ReadTheDocs + Context7 (SQLAlchemy, Alembic, structlog, pydantic) + pgvector GitHub README.**
- #### Hook 1 — argon2-cffi — DISCREPANCY
- | DISCREPANCY NOTE | `P00-S02-T003-argon2-cffi-2026-05-11.md` |
- `from sqlalchemy.dialects.postgresql import insert; insert(table).values(...).on_conflict_do_update(index_elements=[col_name], set_={col: insert_stmt.excluded.col})` — official API unchanged.
- `from sqlalchemy import inspect; inspect(engine).has_table("tablename")` — official and unchanged in 2.x. Opción C is valid.
- `alembic init <dir>` generates: `alembic.ini`, `<dir>/env.py`, `<dir>/README`, `<dir>/script.py.mako`, `<dir>/versions/`. Minor: also creates a `README` file (not a `.gitkeep`). Harmless.
- Deferral to P01 is correct. When P01 switches, the correct tag is `pgvector/pgvector:pg17-trixie` (NOT `pg17-alpine` — alpine variant is not an official pgvector tag; must compile from source on alpine).
- #### Hook 7 — cryptography (Fernet) — DISCREPANCY
- NOT a transitive dep from argon2-cffi or psycopg. litellm pulls it only under `proxy` extra (older version 46.0.7) — not guaranteed. Must pin explicitly: `cryptography==48.0.0`.
- DISCREPANCY NOTE: `P00-S02-T003-cryptography-fernet-2026-05-11.md`
- - AI/ML packages (litellm, langchain, langgraph, deepagents, mcp) ALWAYS re-verify — volatile ecosystem.
- - deepagents discrepancy note `T003-discrepancy-deepagents.md` is `RESOLVED: pending` — developer documents in handoff.
- - Frontend deps T002 all verified 2026-05-11. Re-verify after 2026-05-18.
- - Zod v4 is current stable — downstream slices must use v4 API (no `.email()` chain; use `z.email()`).
- - i18next T005 fully verified 2026-05-11 (cache until 2026-05-18). All planner decisions confirmed. No discrepancy notes. See section above for full details.
- - P00-S02-T003 two discrepancy notes written 2026-05-11: argon2-cffi==25.1.0 (not ~23.x) and cryptography==48.0.0 (must be explicit dep).

### 2026-05-12 — P01-S02-T003 SQLAlchemy 2.0 sync `with_for_update()` + PostgreSQL 17 FOR UPDATE under READ COMMITTED

**Sources**: Context7 /websites/sqlalchemy_en_20_orm, /websites/sqlalchemy_en_20_core; PostgreSQL 17 official docs §13.2.1 READ COMMITTED (https://www.postgresql.org/docs/17/transaction-iso.html#XACT-READ-COMMITTED); PostgreSQL 17 SELECT FOR UPDATE docs (https://www.postgresql.org/docs/17/sql-select.html#SQL-FOR-UPDATE-SHARE).
**Cache valid until**: 2026-05-19 (stable tech — SQLAlchemy 2.x, PostgreSQL 17 isolation semantics are not volatile).

#### Key findings

- **Project is SYNC, not async**: `session.py` uses `create_engine` + `sessionmaker` + `Session`. D-DB1: "Async deferred to P02 (YAGNI)." Task-pack M.1 async framing is not applicable to the actual codebase.
- **`with_for_update(nowait=True)` is the recommended flag**: `nowait=False` (default) blocks until the concurrent tx commits; `nowait=True` raises `sqlalchemy.exc.OperationalError` (wrapping `psycopg.errors.LockNotAvailable`) immediately — faster fail for the losing race, same client-visible 401 outcome.
- **READ COMMITTED + FOR UPDATE is sufficient** — PostgreSQL 17 official docs §13.2.1 explicitly state: *"The search condition (WHERE clause) is re-evaluated to see if the updated version of the row still matches… In the case of `SELECT FOR UPDATE`, this means it is the updated version of the row that is locked and returned to the client."* Consequence: after Tx-A commits `revoked_at=now()`, Tx-B re-evaluates `WHERE revoked_at IS NULL` → gets zero rows → None → 401. No REPEATABLE READ or SERIALIZABLE upgrade needed.
- **D-S2 separate-session audit pattern is canonical**: SAVEPOINTs (`session.begin_nested()`) do not survive an outer tx rollback. Separate short-lived session is the only way to persist the rejection audit row independently.
- **Codebase uses legacy `session.query()` style** (1.x-compatible, still valid in 2.0.49). The 2.0-style `session.scalars(select(...).with_for_update())` is equally valid but inconsistent with existing code.
- **`OperationalError` catch pattern for NOWAIT**: `from sqlalchemy.exc import OperationalError; try: session.query(...).with_for_update(nowait=True).first() except OperationalError: raise SessionExpiredError()`.
- **No discrepancies** with task-pack D-RP3. NOWAIT is a recommendation (task pack says "researcher to confirm"), not a contradiction.

### 2026-05-11 — P01-S01-T001 Alembic migration + SQLAlchemy 2.0 models (auth baseline)

**Sources**: Context7 /websites/sqlalchemy_en_20_orm, /websites/sqlalchemy_en_20_core, /websites/alembic_sqlalchemy. Cache from P00-S02-T003 also reused (same-day).
**Cache valid until**: 2026-05-18 (stable tech — Alembic, SQLAlchemy are not AI/ML volatile).

#### All task-pack patterns verified CONFIRMED

| Pattern | Verification |
|---|---|
| `class Base(DeclarativeBase): pass` | Context7 SQLAlchemy ORM — canonical 2.0 style |
| `mapped_column(primary_key=True)` + `Mapped[T]` | Context7 SQLAlchemy ORM — canonical |
| `sa.Column(UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"))` | Context7 + cache P00-S02-T003 |
| `sa.CheckConstraint(expr, name=...)` inside `op.create_table` | Context7 SQLAlchemy Core DDL docs — table-level inline is canonical |
| `MetaData(naming_convention={...})` on `Base` | Context7 Alembic naming docs |
| `down_revision = None` (first migration) | Alembic tutorial + confirmed empty versions/ dir |
| `JSONB server_default sa.text("'{}'::jsonb")` | SQLAlchemy Core + cache P00-S02-T003 |
| `ForeignKey(..., ondelete="CASCADE"/"SET NULL")` | Cache P00-S02-T003 Hook 2 |
| `gen_random_uuid()` via pgcrypto in PG17 | Cache P00-S02-T003 Hook 6 |
| `TEXT` for `password_hash` (argon2 ~96-128 chars) | Cache P00-S02-T003 Hook 1 — TEXT is unbounded, confirmed sufficient |
| Alembic 1.18.4 API (`op.create_table`, `op.create_index`) | Cache P00-S02-T003 Hook 4 |

#### DISCREPANCY NOTE written (medium severity)

- `P01-S01-T001-sqlalchemy-timestamptz-2026-05-11.md` — `TIMESTAMPTZ` in DDL requires `sa.TIMESTAMP(timezone=True)` or `DateTime(timezone=True)` in SQLAlchemy. Using bare `sa.TIMESTAMP` emits `TIMESTAMP WITHOUT TIME ZONE` silently. Affects: users.created_at/updated_at, refresh_tokens.expires_at/revoked_at, password_reset_tokens.expires_at/used_at, audit_logs.created_at.
- RESOLVED line is empty — developer must confirm correct type used and add `RESOLVED: used sa.TIMESTAMP(timezone=True)` to the note.

#### No-op items (from prompt, not actually in this migration)

- `postgresql_where` partial unique index — NOT present in any of the 9 tables of this migration. No partial indexes in §4 plan. Prompt mentioned it as a topic but the DDL doesn't use it.
- `cryptography.Fernet` — confirmed NOT in scope for this slice (P02-S02 Security service).

### 2026-05-11 — P01-S02-T001 sign-up API (email-validator, Pydantic EmailStr, Argon2id OWASP params)

**Sources**: PyPI live JSON (email-validator 2.3.0), Context7 /joshdata/python-email-validator, Context7 /websites/pydantic_dev_validation, OWASP Password Storage Cheat Sheet (2026-05-11), argon2-cffi ReadTheDocs 25.1.0.
**Cache valid until**: 2026-05-18 (stable tech — email-validator, Pydantic, argon2-cffi, OWASP are not AI/ML volatile).

#### Q1 — email-validator pin + DNS-off behavior — VERIFIED

| Item | Value | Source |
|---|---|---|
| Latest stable | **2.3.0** | PyPI live JSON 2026-05-11 |
| Pydantic 2.12.5 requirement | `email-validator>=2.0.0` (under `pydantic[email]` extra) | PyPI pydantic/2.12.5/json |
| License | Unlicense | PyPI |
| DNS-off API | `validate_email(email, check_deliverability=False)` | Context7 joshdata/python-email-validator README |
| MATCH | YES — `check_deliverability=False` is the documented pattern for account-creation pages (no DNS, syntactic only) | README explicitly states this use case |
| pyproject.toml line | `"email-validator==2.3.0"` | — |
| requirements.txt line | `email-validator==2.3.0` | — |
| install as pydantic extra | `pydantic[email]==2.12.5` or separate `email-validator==2.3.0` | Both work; explicit pin preferred |

#### Q2 — Pydantic v2 EmailStr + custom domain validator — VERIFIED

Canonical pattern confirmed via Context7 pydantic_dev_validation:

```python
from pydantic import BaseModel, EmailStr, field_validator, ValidationError

class SignUpRequest(BaseModel):
    email: EmailStr  # handles RFC 5322 syntax + normalization

    @field_validator('email', mode='after')
    @classmethod
    def validate_corporate_domain(cls, v: str) -> str:
        domain = v.split('@')[1].lower()
        allowed = {d.strip() for d in os.getenv('CORPORATE_EMAIL_DOMAINS', '').split(',') if d.strip()}
        if not allowed or domain not in allowed:
            raise ValueError('email domain not in corporate allowlist')
        return v
```

- `mode='after'` runs AFTER EmailStr validation — guaranteed v is a valid email string.
- Raising `ValueError` inside `@field_validator` produces `errors[].type="value_error"` and `errors[].loc=["email"]` in Pydantic v2 ValidationError, which FastAPI surfaces as 422 with `errors[].field="email"`.
- No double-parsing cost: EmailStr runs the `email-validator` lib once; the domain check is pure string split — negligible overhead.
- Alternative (`PydanticCustomError`) allows custom error codes but `ValueError` is canonical and sufficient.
- MATCH with task pack §F.1 and §M.2.

#### Q3 — Argon2id OWASP 2026 params — DISCREPANCY (non-blocking)

**DISCREPANCY NOTE WRITTEN**: `P01-S02-T001-argon2-owasp-params-2026-05-11.md`

- Task pack §F.3 incorrectly characterizes argon2-cffi defaults as "OWASP 2024 minimums".
- OWASP 2026 minimums are actually MUCH LOWER: top config = 46 MiB / t=1 / p=1.
- argon2-cffi 25.1.0 defaults = 64 MiB / t=3 / p=4 — these EXCEED all 5 OWASP configs.
- Recommended action: use `PasswordHasher()` defaults as-is (no code change); correct docstring to say "EXCEED OWASP minimums".
- OWASP explicitly recommends Argon2id variant (Type.ID = default in argon2-cffi).
- OWASP does NOT specify salt_len / hash_len — library defaults (16/32) are fine.

### 2026-05-11 — P01-S02-T002 sign-in API (PyJWT pin, Starlette cookies, HS256, jti, argon2 check_needs_rehash)

**Sources**: PyPI live JSON (PyJWT 2.12.1), Context7 /jpadilla/pyjwt, Starlette docs (starlette.io/responses), RFC 7519 §4.1.7 (rfc-editor.org), RFC 7518 §3.2 (rfc-editor.org), argon2-cffi ReadTheDocs.
**Cache valid until**: 2026-05-18 (stable tech — PyJWT, Starlette, argon2-cffi, RFCs are not AI/ML volatile).

#### Q1 — PyJWT pin — VERIFIED

| Item | Value |
|---|---|
| Latest stable | **2.12.1** (2026-03-13) |
| Python 3.12 | Confirmed via PyPI classifiers |
| encode return | **str** (not bytes) in all 2.x |
| decode signature | `jwt.decode(token, key, algorithms=["HS256"], options={...})` |
| Exception hierarchy | `jwt.PyJWTError` → `jwt.InvalidTokenError` → `jwt.ExpiredSignatureError`, `jwt.InvalidSignatureError`, etc.; `jwt.MissingRequiredClaimError` for require-list misses |
| pyproject.toml | `"PyJWT==2.12.1"` |

#### Q2 — Starlette set_cookie API — VERIFIED

```python
response.set_cookie(
    key="refresh_token",
    value=opaque_token,
    max_age=2592000,
    path="/auth",
    secure=True,
    httponly=True,
    samesite="lax",   # lowercase "lax" NOT "Lax"
)
```
- All parameter names lowercase: `httponly`, `secure`, `samesite`, `path`, `max_age`.
- `samesite` valid values: `"lax"`, `"strict"`, `"none"` (all lowercase).
- `samesite="none"` requires `secure=True` (browser enforcement).
- FastAPI's `JSONResponse.set_cookie(...)` delegates to Starlette — same API.

#### Q3 — PyJWT HS256 best practice — VERIFIED

- `algorithm="HS256"` confirmed correct string.
- RFC 7518 §3.2: key MUST be ≥32 bytes (256 bits) for HS256; production: use ≥64 bytes.
- `iat`/`exp` accept both `int` (UNIX ts) and `datetime` (timezone-aware) in PyJWT 2.x.
- Canonical require list: `options={"require": ["exp", "iat", "sub", "jti"]}`.
- `datetime.now(tz=timezone.utc)` is preferred for `iat`/`exp` — cleaner code.

#### Q4 — jti strategy — VERIFIED

- RFC 7519 §4.1.7: jti is a case-sensitive string; no format mandated; UUID satisfies uniqueness.
- `uuid.uuid4().hex` (32-char no-hyphen hex) or `str(uuid.uuid4())` both compliant.
- No server-side deny-list required for V1: short access token TTL (1800s) + refresh rotation + `revoked_at` on `refresh_tokens` provides revocation. Blocklist upgrade path (Redis) deferred to future phase.

#### Q5 — argon2-cffi check_needs_rehash — VERIFIED

- `ph.check_needs_rehash(hash: str | bytes) -> bool` — pure string parsing of PHC header.
- I/O-free, microsecond-scale. No hashing, no DB, no network.
- Official docs: *"best practice to check – and if necessary rehash – passwords after each successful authentication."* — intended inline use pattern.
- Safe to call inline on every sign-in, inside the same transaction.

#### Note file

`orchestrator-state/memory/official-doc-notes/P01-S02-T002-pyjwt-cookies-argon2.md`
Status: `RESOLVED: yes` — no discrepancies; all items are decision-aids filling TECHNICAL_GUIDE gaps.

## Original heading index
- # Official Docs Researcher Memory
- ### 2026-05-11 — P00-S02-T001 Docker Compose infra pins
- #### Verified OK (cache valid until 2026-05-18 for stable; Docker tags are volatile, re-check before re-use)
- #### CRITICAL DISCREPANCY (UNRESOLVED)
- #### Minor discrepancy (UNRESOLVED)
- ## Cache entries (freshness windows: stable tech=7d, AI/ML volatile=always, Claude Code=14d)
- ### 2026-05-11 — P00-S01-T001 HILO_PEOPLE scaffold
- #### Backend
- #### Frontend
- #### Python packaging
- #### Python logging
- #### Health endpoint
- ### 2026-05-11 — P00-S01-T003 Backend dependency pack (full 20-package audit)
- #### Runtime packages
- #### Dev/test packages
- #### Key gotchas verified this pass
- #### Discrepancy notes written
- ### 2026-05-11 — P00-S01-T002 Frontend dependency pack
- #### React Router
- #### TanStack Query
- #### React Hook Form + resolvers + Zod
- #### i18next stack
- #### Test dependencies
- #### Discrepancy notes written for T002
- ### 2026-05-11 — P00-S01-T005 i18n resources ES/EN/FR — deep pass
- #### i18next v26 breaking changes (verified)
- #### init pattern (inline resources)
- #### fallbackLng = 'es' (non-English fallback)
- #### ns array + defaultNS
- #### missingKeyHandler: false (redundant but harmless)
- #### react-i18next 17 API patterns (verified)
- #### Vite + public/locales/ (inline import, no http backend)
- #### Vitest + jsdom + i18next (testing)
- #### Type augmentation (CustomTypeOptions)
- #### Outcome: VERIFIED — all planner decisions confirmed
- ### 2026-05-11 — P00-S02-T003 Verification data loader (8 hooks)
- #### Hook 1 — argon2-cffi — DISCREPANCY
- #### Hook 2 — SQLAlchemy 2.0.49 UPSERT — CONFIRMED
- #### Hook 3 — `inspect(engine).has_table()` SQLAlchemy 2.x — CONFIRMED
- #### Hook 4 — Alembic 1.18.4 init structure — CONFIRMED
- #### Hook 5 — structlog 25.5.0 redaction — CONFIRMED
- #### Hook 6 — pgvector deferral — CONFIRMED (with tag note for P01)
- #### Hook 7 — cryptography (Fernet) — DISCREPANCY
- #### Hook 8 — Pydantic v2.12.5 validators — CONFIRMED
- ## Notes for next researcher

### 2026-05-12 — P01-S02-T005 Resend Python SDK, aiosmtplib, OWASP forgot-password

**Sources**: PyPI live JSON (resend 2.30.0, aiosmtplib 5.1.0), Context7 /resend/resend-python, /websites/resend, /llmstxt/resend_llms-full_txt, /cole/aiosmtplib, resend.com/docs/send-with-python, resend.com/docs/dashboard/emails/idempotency-keys, cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html, cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
**Cache valid until**: 2026-05-19 (stable tech; resend is NOT AI/ML volatile, re-check if version bump suspected)
**Note file**: `orchestrator-state/memory/official-doc-notes/P01-S02-T005-resend-mail-2026-05-12.md`
**OUTCOME**: verified — no blocking discrepancy

#### Key findings

| Item | Value |
|---|---|
| `resend` PyPI | **2.30.0** (2026-05-04) |
| Init | `resend.api_key = os.environ["RESEND_API_KEY"]` (module singleton, NOT class instantiation) |
| Send sync | `resend.Emails.send(params)` → TypedDict `{"id": str}` |
| Send async | `await resend.Emails.send_async(params)` — **native coroutine**, no run_in_threadpool needed |
| Python casing | snake_case params (`reply_to`, NOT `replyTo`) |
| Idempotency | `options={"idempotency_key": "..."}` — officially supported |
| Sandbox/dry-run | **None** — zero mention in official docs; outbox-JSONL dev pattern is correct |
| Exceptions | `resend.exceptions.{ResendError, ValidationError, MissingApiKeyError, InvalidApiKeyError, RateLimitError, MissingRequiredFieldsError, ApplicationError}` |
| SMTP fallback | `aiosmtplib==5.1.0` (Production/Stable, Python>=3.10, zero deps) |
| SMTP port | 587+STARTTLS (`start_tls=None` default) recommended; 465+`use_tls=True` also valid |
| Anti-enum OWASP | Body byte-equal + timing-equal — confirmed 2026 |
| Token generation | `secrets.token_urlsafe(32)` (256 bits) — confirmed sufficient |
| Token storage | `sha256(raw).hexdigest()` — confirmed sufficient (256-bit entropy makes brute-force infeasible) |
| Token TTL | OWASP says "appropriate period" — 3600s (1h) is industry consensus, aligned |

### 2026-05-12 — P01-S02-T006 pyotp TOTP verify API

**Sources**: PyPI live JSON (pyotp 2.9.0), Context7 /pyauth/pyotp, GitHub pyauth/pyotp source (totp.py, otp.py), GitHub security advisories, OSV.dev + NVD search.
**Cache valid until**: 2026-05-19 (stable library; not AI/ML volatile)
**Note file**: `orchestrator-state/memory/official-doc-notes/P01-S02-T006-pyotp-2026-05-12.md`
**OUTCOME**: verified — no blocking discrepancy; two non-blocking recommendations

#### Key findings

| Item | Value |
|---|---|
| Latest stable | **2.9.0** (2023-07-27); 2.x is the latest series; no 3.x |
| Pin string | `"pyotp==2.9.0"` (pyproject.toml and requirements.txt) |
| `verify()` signature | `verify(otp: str, for_time=None, valid_window: int = 0) -> bool` |
| 2nd param name | `for_time` (NOT `timestamp`; Context7 summary used `timestamp` — source code is authoritative) |
| Return type | `bool` only; **never raises** on valid str input; constant-time via `utils.strings_equal` |
| Malformed code | `str(otp)` cast; non-matching str returns `False`; no exception raised |
| Code type | `str` only; bytes would stringify to `"b'...'"` → always `False` (no exception) |
| valid_window=1 | Accepts [-1, 0, +1] time steps ≈ 90s window; task pack §F.2 confirmed reasonable |
| Secret format | Plain base32 str (e.g. `"JBSWY3DPEHPK3PXP"`); NOT bytes; casefold=True; auto-padding |
| Invalid base32 | Raises `binascii.Error` from `byte_secret()`; recommend try/except in service |
| Replay prevention | pyotp has NONE; app MUST track consumed codes/jtis → confirms Decision F.1 |
| CVEs | **None** as of 2026-05-12 (GitHub advisories: 0; OSV.dev: 0; NVD: 0) |

#### Non-blocking recommendations to developer

1. Consider `re.fullmatch(r'\d{6}', v)` in Pydantic validator instead of `v.isdigit()` to block Unicode fullwidth digits (e.g. `"１２３４５６"`).
2. Wrap `pyotp.TOTP(seed)` construction in try/except `binascii.Error` → map to `MfaSecretMissingError` with audit reason `no_secret`.

### 2026-05-12 — P01-S03-T001 React Router v7, TanStack Query v5 single-flight, OWASP token storage, React 19 Context/use()

**Sources**: Context7 /remix-run/react-router (1115 snippets, v7.6.2 latest); Context7 /websites/tanstack_query_v5 (3008 snippets, v5.90.3 latest); Context7 /websites/react_dev_reference (React 19); react.dev/blog/2024/04/25/react-19; OWASP Session Management CS; OWASP CSRF Prevention CS.
**Cache valid until**: 2026-05-19 (stable tech: react-router, react-query, React 19 APIs, OWASP policies are not AI/ML volatile)
**Note file**: `orchestrator-state/memory/official-doc-notes/P01-S03-T001-owasp-samesite-2026-05-12.md`
**OUTCOME**: verified — one low-severity discrepancy note written (SameSite=Lax vs Strict preference language); RESOLVED inline (no code change required)

#### Q1 — React Router v7 protected route pattern (verified)

- `<BrowserRouter>` + `<Routes>` + `<Route>` are FULLY SUPPORTED in v7. No forced migration to `createBrowserRouter`.
- **Two canonical patterns coexist** and react-router v7 docs show BOTH with official examples:
  1. **Component wrapper** (`<RequireAuth>` reads auth context, returns `<Navigate to="/login" state={{ from: location }} replace />`). This is the CANONICAL pattern for client-side auth state in a Context Provider (the auth-example in the repo uses exactly this). Works with `<BrowserRouter>`.
  2. **Loader redirect** (`loader: () => redirect("/login?from=...")` returning `redirect()`). This is the data-router pattern — requires `createBrowserRouter` / `RouterProvider`. Does NOT work with the JSX `<Routes>` API.
- **Recommendation for this project**: Component wrapper with `<BrowserRouter>`. Loader redirect requires data-router migration and is NOT needed for client-side auth state.
- **`?next=` state pattern**: Official react-router example uses `state={{ from: location }}` (location object in router state, not URL query param). The data-router example uses `?from=...` query param. Both are valid; query param is more portable (survives page reload). No built-in open-redirect guard in either approach.

#### Q2 — TanStack Query v5 single-flight 401 refresh (verified)

- **No official v5 react-query docs page recommends a single-flight interceptor pattern at the react-query layer.** The docs cover `retry` (count/function), `retryDelay` (exponential backoff), `defaultQueryFn` (global queryFn), and `QueryCache.onError`. None of these handle single-flight refresh natively.
- **Canonical v5 recommendation**: Handle 401 → refresh → retry in the **fetch wrapper layer** (outside react-query). React-query's `retry` function can detect HTTP status but cannot do async side effects (the retry function is synchronous). The correct architecture is: custom `httpClient` that (a) intercepts 401 responses, (b) queues the failed request, (c) fires ONE refresh (in-flight promise shared), (d) on success replays all queued requests. React-query wraps this opaquely and sees only success or error.
- **`QueryCache.onError`** is a notification callback — appropriate for logging/toast but NOT for async retry coordination.
- **`defaultOptions.queries.retry` function** is synchronous (receives `failureCount, error`) — can return `false` to stop retries but cannot await a refresh call.
- Pattern for single-flight: exported singleton `let refreshPromise: Promise<string> | null = null` in `accessTokenStore.ts`; httpClient checks this before initiating a new refresh call.

#### Q3 — OWASP token storage 2025-2026 (verified, minor discrepancy written)

- OWASP CSRF CS: `SameSite=Lax` is the recommended default ("reasonable balance between security and usability"). CONFIRMED for our pattern.
- OWASP Session CS: `Strict` is "preferred"; `Lax` is "acceptable". This is preference language, not a prohibition.
- **DISCREPANCY NOTE**: `P01-S03-T001-owasp-samesite-2026-05-12.md` — RESOLVED: `SameSite=Lax` confirmed correct for our `Path=/api/v1/auth`-scoped cookie. No code change.
- BFF pattern: OWASP docs do NOT mandate BFF for all SPAs in 2025-2026. The in-memory access token + HttpOnly refresh cookie pattern is the documented OWASP-compliant approach (OWASP CSRF CS, HTML5 CS). Access token in JS memory (closure/module singleton) is explicitly safer than localStorage per OWASP HTML5 CS.
- No 2025-2026 updates change the documented BFF-or-memory pattern for SPAs.

#### Q4 — React 19 Context Provider / use() hook impact (verified)

- **`<Context.Provider>` is deprecated** (not removed) in React 19; new syntax is `<Context value={...}>`. The old form still works but will warn in future. Developer should use `<AuthContext value={...}>` in `AuthProvider.tsx`.
- **`useEffect(() => { fetch... }, [])` is still valid and documented** in React 19 for client-side data fetching. React docs explicitly show it as a `useEffect` pattern with ignore-flag for race-condition safety. Not deprecated.
- **`use(promise)` + Suspense**: available in React 19 for data fetching during render. BUT: (a) the promise must be created OUTSIDE render (e.g., passed as prop or created at module level); (b) React 19 docs explicitly warn "don't create promises in render". For `AuthProvider` mount-time `/refresh` this would require creating the promise outside the component — adds complexity with no benefit for a single fire-once call.
- **Recommendation**: Keep `useEffect(() => { doRefresh() }, [])` for `AuthProvider` mount-time hydration. This is the simpler, documented pattern and has NO breaking change in React 19. The `use(promise)` pattern is better suited for data-fetching components already in a Suspense tree (e.g., post-auth data), not for the auth bootstrap itself.
- **Automatic batching**: React 19 extends automatic batching further (was already improved in React 18). No breaking change for `AuthProvider` — state updates inside `useEffect` are batched together correctly in React 18+ and continue to be in React 19.
- Context value change re-renders consumers: no change from React 18. Same reference equality check applies — memoize the context value object if it's created inline.

#### Q5 — react-router v7 open-redirect guard (verified)

- **No built-in utility** in react-router v7 for validating `?next=` or any redirect target. The docs show raw path reads from `location.state` or `useSearchParams().get("from")` without validation.
- **Recommended manual guard** (industry consensus, no official react-router snippet): 
  ```ts
  function safeRedirectTarget(raw: string | null, fallback = "/chat"): string {
    if (!raw) return fallback;
    try {
      // Reject absolute URLs (protocol://, //host, data:, javascript:)
      if (/^(https?:|\/\/|javascript:|data:)/i.test(raw)) return fallback;
      // Reject backslash (IE path confusion)  
      if (raw.includes("\\")) return fallback;
      // Must start with /
      if (!raw.startsWith("/")) return fallback;
      return raw;
    } catch {
      return fallback;
    }
  }
  ```
- URL parsing + same-origin check is the standard approach. react-router does not abstract this.

### 2026-05-13 — P01-S03-T002 Vite proxy / FastAPI CORSMiddleware / SameSite=Lax / nginx Set-Cookie

**Sources**: Context7 /vitejs/vite v8.0.10 (server-options.md); http-proxy-3 README; Context7 /websites/fastapi_tiangolo (reference/middleware, tutorial/cors); Starlette docs (starlette.io/middleware); MDN Glossary/Site; MDN Set-Cookie/SameSite; web.dev same-site-same-origin; nginx ngx_http_proxy_module official docs.
**Cache valid until**: 2026-05-20 (stable tech — Vite proxy, FastAPI CORS, SameSite spec, nginx are not AI/ML volatile)
**Note file**: `orchestrator-state/memory/official-doc-notes/P01-S03-T002-cors-2026-05-13.md`
**OUTCOME**: discrepancy (two items — both low severity, no code change needed; STRATEGY-A-CONFIRMED)

#### Key findings

| Item | Value | Source |
|---|---|---|
| Vite version in project | ^8.0.12 | frontend/package.json |
| Starlette version | 1.0.0 | pip show starlette |
| `changeOrigin` effect | Rewrites Host header ONLY — NOT Set-Cookie Domain | http-proxy-3 README |
| `cookieDomainRewrite` default | `false` (disabled, cookies pass through unchanged) | http-proxy-3 README |
| `cookiePathRewrite` default | `false` (disabled) | http-proxy-3 README |
| `secure: false` | Only needed for http→https upstream; irrelevant for localhost:8000 | Vite docs |
| Custom request headers (X-Request-ID) | Forwarded to upstream by default | http-proxy-3 |
| Custom response headers | Forwarded back to browser by default | http-proxy-3 |
| WebSocket under `/api` | `ws: true` NOT needed for SSE; only for WebSocket upgrade | Vite docs |
| CORSMiddleware OPTIONS 405 without it | Expected — FastAPI has no implicit OPTIONS handler | FastAPI tutorial/cors |
| `allow_origins=["*"]` + `allow_credentials=True` | **Explicitly forbidden** — must use explicit list | Starlette docs + CORS spec |
| CORSMiddleware order | Must be registered LAST (outermost) via `add_middleware` | Starlette docs |
| `expose_headers=["X-Request-ID"]` | Required for Strategy B so JS can read response header | CORS spec / FastAPI docs |
| localhost:5173 vs localhost:8000 same-site? | **YES — same-site** (port ignored, eTLD+1=localhost, same scheme) | MDN Glossary/Site + web.dev |
| SameSite=Lax blocks :5173→:8000 cookie? | **NO** — they are same-site, Lax only restricts cross-site | MDN + web.dev |
| nginx proxy_pass + Set-Cookie | **Forwarded by default** — no proxy_pass_header needed | nginx official docs |
| nginx default hidden headers | Date, Server, X-Pad, X-Accel-* (Set-Cookie NOT in list) | nginx official docs |

#### Discrepancy #1 — §B.3 SameSite reasoning imprecise (low, no code change)
- Task pack §B.3: "SameSite=Lax does NOT block cross-origin XHR by itself" — directionally correct but imprecise.
- Official docs: localhost:5173 and localhost:8000 are same-site (port ignored). SameSite=Lax does not block cookies between same-site origins regardless of port difference. The blocker is CORS preflight (separate mechanism from SameSite).
- Developer may (optionally) correct ADR-002 wording. No code change required.

#### Discrepancy #2 — Initial nginx Set-Cookie claim self-corrected (low, confirmed correct)
- First fetch incorrectly suggested `proxy_pass_header Set-Cookie` is needed.
- Corrected by second authoritative nginx docs fetch: Set-Cookie IS forwarded by default.
- Strategy A prod topology (§11.4) is valid without extra nginx directives.

### 2026-05-13 — P02-S01-T001 pgvector index type + Docker image + SQLAlchemy mapping

**Sources**: pgvector GitHub README (raw, v0.8.2), Context7 /pgvector/pgvector (High, 275 snippets), pgvector-python GitHub README (raw), Context7 /pgvector/pgvector-python (High, 125 snippets), Docker Hub pgvector/pgvector tags (pg17 filter).
**Cache valid until**: 2026-05-20 (pgvector is NOT AI/ML volatile — it's a DB extension; Docker tags verified live).
**Note file**: `orchestrator-state/memory/official-doc-notes/P02-S01-T001-pgvector-2026-05-13.md`
**OUTCOME**: discrepancy — 3 items (1 high, 1 medium, 1 low)

#### Key findings

| Item | Official value | Source |
|---|---|---|
| pgvector stable version | **0.8.2** | Docker Hub (latest push ~3 months ago) |
| Recommended index type | **HNSW** for production | pgvector README + Context7 llms.txt |
| ivfflat on empty table | **Explicitly discouraged** ("create after table has some data") | pgvector README |
| HNSW on empty table | **Explicitly safe** (no training step) | pgvector README |
| HNSW defaults | `m=16, ef_construction=64` | pgvector README |
| ivfflat lists formula | `rows/1000` for <1M rows | pgvector README |
| Docker pg17 tags | `pg17`, `pg17-bookworm`, `pg17-trixie`, `0.8.2-pg17`, `0.8.2-pg17-bookworm`, `0.8.2-pg17-trixie` | Docker Hub live |
| Alpine variant | **DOES NOT EXIST** for pg17 | Docker Hub (confirmed again) |
| Recommended pinned tag | `pgvector/pgvector:0.8.2-pg17` (Bookworm/Debian 12) | Docker Hub |
| pgvector-python ORM import | `from pgvector.sqlalchemy import VECTOR` (**VECTOR** all caps) | pgvector-python README |
| SQLAlchemy 2.0.49 compat | Confirmed (uses mapped_column, select) | pgvector-python README |
| Alembic helper | **None** — use `Index(postgresql_using='hnsw', ...)` or raw `op.execute(...)` | pgvector-python README |
| register_vector() needed? | **No** for psycopg3 + SQLAlchemy — auto-registers on import | pgvector-python README |
| CREATE EXTENSION needed? | **YES** — image has binaries, but `CREATE EXTENSION IF NOT EXISTS vector` in migration still required | pgvector README |

#### Discrepancies vs internal §10.3

1. **HIGH** — ivfflat on empty table: internal guide uses ivfflat with no lists param on empty table. Official: use HNSW (safe on empty table) or defer ivfflat index post-load.
2. **MEDIUM** — Docker image: `postgres:17-alpine` → must change to `pgvector/pgvector:0.8.2-pg17` (pre-approved by user).
3. **LOW** — ORM type name: `VECTOR` (all caps), not `Vector`. Only matters in ORM model files.

### 2026-05-13 — P02-S04-T001 pgvector-python 0.4.2 cosine_distance + psycopg3 async binding + HNSW ef_search

**Sources**: pgvector-python v0.4.2 README (raw tag), Context7 /pgvector/pgvector-python (High, 125 snippets), Context7 /pgvector/pgvector (High, 275 snippets).
**Cache valid until**: 2026-05-20 (pgvector-python 0.4.2 is a pinned version — stable).
**Note file**: `orchestrator-state/memory/official-doc-notes/P02-S04-T001-pgvector-2026-05-13.md`
**OUTCOME**: verified — no discrepancies with internal pack; 3 questions answered.

#### Key findings

| Item | Value | Source |
|---|---|---|
| `cosine_distance` method exists in 0.4.2 | **YES** | v0.4.2 README verbatim |
| SQL operator emitted by cosine_distance | `<=>` | pgvector operator mapping (L2=`<->`, cosine=`<=>`, IP=`<#>`) |
| HNSW `vector_cosine_ops` uses `<=>` | **YES** — index IS used by cosine_distance | pgvector README |
| Import at v0.4.2 | `from pgvector.sqlalchemy import Vector` (title-case) | v0.4.2 README |
| query_vec Python type | `list[float]` is fine; `numpy.ndarray` also works | v0.4.2 README examples |
| register_vector for SQLAlchemy ORM + psycopg3 | **REQUIRED** via `event.listens_for(engine, "connect")` | v0.4.2 README |
| Async engine pattern | `event.listens_for(engine.sync_engine, "connect")` + `dbapi_connection.run_async(register_vector_async)` | v0.4.2 README |
| Per-call registration needed? | **NO** — event listener fires once per new connection | v0.4.2 README |
| hnsw.ef_search default | **40** | pgvector README |
| ef_search=40 on ~30 rows | Sufficient — ef_search > table_size = full index scan | pgvector README |
| HNSW determinism on equal-distance vectors | **NON-DETERMINISTIC** for tie-breaking | pgvector ANN nature |
| Smoke test assertion strategy | Set membership (doc_id IN results), not exact rank order | — |

#### Note on `Vector` vs `VECTOR` naming across versions

- 0.4.2 README: `from pgvector.sqlalchemy import Vector` (title-case)
- Latest/current (Context7): `from pgvector.sqlalchemy import VECTOR` (all-caps)
- Both may be exported as aliases. For 0.4.2, use `Vector` per pinned README.
- P02-S01-T001 note said "use VECTOR (all-caps)" based on current docs — may need to recheck against actual installed 0.4.2 package if import errors occur.

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.2026-05-11-141041.md`
