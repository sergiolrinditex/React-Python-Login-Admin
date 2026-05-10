# official-docs-researcher agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.2026-05-10-044634.md`
- Original lines: 298
- Original SHA-256: `4c8a3e2837bcc803268f4c60050e774d71b73ddb847cab9573d0e7b9c1e18b7e`
- Compacted at: `2026-05-10-044634`
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
- # official-docs-researcher agent memory
- - Original full file: `orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.2026-05-09-221733.md`
- ## Current operating invariants
- - Use official, current/versioned documentation only unless the task explicitly permits otherwise.
- - Fast lookup order: local/cache docs, ToolSearch/MCP, Context7, vendor MCP, then official WebFetch/WebSearch fallback.
- - Fan out independent documentation checks in one tool batch; do not serialize unless a result depends on a prior result.
- - Capture source, framework/library version, and concrete implementation implications.
- - Mark missing or conflicting documentation as `insufficient` or `discrepancy`; do not invent certainty.
- ## Trailer vocabulary
- - `OUTCOME`: `verified|discrepancy|insufficient`
- - `NEXT_STATUS`: `<none>`
- - Always read `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` before emitting trailers.
- - Context7 `/websites/sqlalchemy_en_20` — async upsert ON CONFLICT DO UPDATE, engine.begin() transaction pattern
- - Context7 `/hynek/structlog` — secret masking processors, DropEvent pattern
- **Discrepancies**: NONE. All patterns in codebase align with or exceed official guidance.
- - Context7 `/encode/httpx` — logging docs, MockTransport docs
- - WebFetch `https://www.python-httpx.org/logging/` — official logging page
- - WebFetch `https://www.python-httpx.org/advanced/transports/` — official transports page
- - WebFetch `https://raw.githubusercontent.com/encode/httpx/master/docs/logging.md` — raw logging.md
- - WebFetch `https://github.com/encode/httpx/blob/0.28.1/httpx/_transports/mock.py` — MockTransport source at tag 0.28.1
- - Context7 `/hynek/structlog` — stdlib integration docs
- #### httpx 0.28.1 Logger Names (VERIFIED — CRITICAL)
- Two distinct loggers, both official, both documented:
- #### Structlog stdlib interaction (VERIFIED)
- #### httpx.MockTransport (VERIFIED — stable, idiomatic)
- - `httpx.MockTransport(handler)` — documented, stable, no version caveats.
- - Idiomatic for unit tests; official docs acknowledge it; no deprecation or instability noted in 0.28.1.
- #### Plan alignment (VERIFIED — no discrepancy)
- ### Entry 2026-05-10 — P00-S02-T011 cryptography 48 Fernet.generate_key + pydantic-settings 2.14.1 AliasChoices + POSIX bash sed (SHALLOW PASS — all verified)
- - Context7 `/websites/cryptography_io_en` — Fernet docs, generate_key API, KDF/password usage
- - Context7 `/pyca/cryptography` — fernet.rst canonical source
- - Context7 `/pydantic/pydantic-settings` — AliasChoices, validation_alias, multiple env var names (cache hit 2026-05-09)
- - POSIX sed spec + GNU sed manual (well-known, no MCP needed; cache knowledge confirmed against docs)
- | 1 | `Fernet.generate_key()` return type | VERIFIED | Returns `bytes` — "A URL-safe base64-encoded 32-byte key." `.decode()` to get `str` for `.env` is correct and idiomatic. |
- | 2 | Fernet key length | VERIFIED | 32 bytes of entropy, base64url-encoded = 44 ASCII chars. No change in cryptography 44-48. |
- | 7 | Idempotent append `grep -q \|\| echo >> ` | VERIFIED | `grep -q '^ENCRYPTION_KEY=' .env \|\| echo "ENCRYPTION_KEY=$key" >> .env` is standard POSIX idiom. Correct and robust. |
- - # official-docs-researcher MEMORY
- - **Source**: Installed venv source `backend/.venv-t003/lib/python3.11/site-packages/pydantic_settings/` (version verified: 2.14.1). Context7 `/pydantic/pydantic-settings` + `/websites/alembic_sqlalchemy`.
- - #### DotenvType (verified from installed source, types.py line 35)
- - - Neither defaulted to anything different in prior versions that would require a change here.
- - Task pack §8 plan (Option A with `str(_PROJECT_ROOT / ".env")`) is correct and idiomatic. No deprecations. Path objects are first-class in `DotenvType`. No discrepancy note required.
- - ### Entry 2026-05-09 — P00-S02-T002 Health live/ready endpoints (SHALLOW PASS — all verified)
- - **Note file**: `orchestrator-state/memory/official-doc-notes/P00-S02-T002-health-endpoints-patterns-2026-05-09.md`
- - | 1 | FastAPI router include + ops | VERIFIED | `app.include_router(router)` canonical; `@app.middleware("http")` for request_id middleware |
- - | 2 | SQLAlchemy 2.0 async SELECT 1 | VERIFIED | `async with engine.connect() as conn: await conn.execute(text("SELECT 1"))` |
- - | 3 | SQLAlchemy/asyncpg exception for DB down | VERIFIED | Catch `sqlalchemy.exc.SQLAlchemyError` — covers OperationalError + InterfaceError; asyncpg raw exceptions NOT exposed |
- - | 4 | structlog 25.5.0 contextvars API | VERIFIED | `structlog.contextvars.bind_contextvars` / `clear_contextvars` confirmed present and unchanged |
- - | 5 | httpx 0.28 ASGITransport | VERIFIED | `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` — `app=` param removed in 0.28 |
- - | 6 | pytest-asyncio 1.3.0 auto mode | VERIFIED | `asyncio_mode="auto"` confirmed in pyproject.toml line 122; no decorator needed |
- - System `python3` has FastAPI 0.135.2; project venv `.venv-t003` has 0.136.1 (correct). Developer must use project venv.
- - - Context7 `/i18next/i18next/v26.0.2` — init API, fallbackLng, ns, defaultNS, resources, supportedLngs, interpolation
- - - Context7 `/i18next/react-i18next` — initReactI18next, useSuspense, I18nextProvider, TypeScript
- - - Context7 `/websites/vite_dev` — JSON imports, publicDir behavior, import.meta.glob eager
- - #### Pinned versions confirmed (from frontend/package.json read 2026-05-09)
- - | Package | Pinned version | Status |
- - | i18next | 26.0.10 | Current stable in Context7 catalog (v26.0.2 docs apply — same major.minor) |
- - | vite | 8.0.11 | Confirmed; publicDir behavior verified |
- - #### Verified API patterns for i18next 26 + react-i18next 17
- - | `fallbackLng: 'es'` (string, singular) | YES | Docs show `fallbackLng: 'en'` (string) as primary example; `string \| string[]` both valid |
- - - `whitelist` → `supportedLngs` (changed in i18next 21, still current in v26) — developer must NOT use `whitelist`.
- - - `cleanCode`/`lowerCaseLng`: no changes noted in v26 docs for these defaults.
- - **DISCREPANCY NOTE WRITTEN**: `orchestrator-state/memory/official-doc-notes/P00-S01-T005-i18n-vite-public-vs-src-import.md`
- - `orchestrator-state/memory/official-doc-notes/P00-S01-T005-i18n-vite-public-vs-src-import.md`
- - - Context7 `/vitejs/vite/v8.0.0` — Vite 8 entry pattern, vite.config.ts defineConfig, test config co-location
- - - Context7 `/vitest-dev/vitest/v4.0.7` — Vitest 4 defineConfig, environment jsdom, setupFiles
- - - Context7 `/remix-run/react-router` — v7 minimal createBrowserRouter + RouterProvider pattern
- - - Context7 `/facebook/react/v19_2_0` — React 19 createRoot, main.tsx mount pattern
- - - Context7 `/testing-library/jest-dom` — v6 Vitest-specific setup file import path
- - #### Verified patterns (2026-05-09)
- - | @testing-library/jest-dom v6 Vitest setup | **ACTIONABLE**: Setup file must use `import '@testing-library/jest-dom/vitest'` NOT `extend-expect`. Note written. | NOTE |
- - `orchestrator-state/memory/official-doc-notes/P00-S01-T004-testing-library-vitest-setup.md`
- - Severity: warn-only. Developer must use the correct import path. Note contains `RESOLVED:` line.
- - All stack components verified 2026-05-09 — re-verify after 7 days (2026-05-16).
- - ### Entry 2026-05-09 — P00-S02-T005 Gemini models, MCP LangChain, deepagents supervisor, argon2, Fernet (DEEP PASS)
- - - WebFetch `https://ai.google.dev/gemini-api/docs/models` — Gemini model catalog
- - - WebFetch `https://ai.google.dev/gemini-api/docs/models/gemini` — Gemini model details
- - - WebFetch `https://ai.google.dev/api/generate-content` — API base URL version
- - - Context7 `/googleapis/python-genai` v1.33.0 — Gen AI Python SDK (current, NOT deprecated)
- - - Context7 `/langchain-ai/deepagents` — deepagents GitHub repo
- - - Context7 `/websites/langchain_oss_python_deepagents` — deepagents official docs

### Entry 2026-05-10 — P01-S02-T001 Pydantic 2.12.5 EmailStr + argon2-cffi 25.1.0 + FastAPI 0.136.1 + SQLAlchemy JSONB (SHALLOW PASS — DISCREPANCY FOUND)

- **Sources**:
  - Context7 `/websites/pydantic_dev_validation` — EmailStr, email-validator requirement, Pydantic v2 migration note
  - Context7 `/hynek/argon2-cffi` — PasswordHasher defaults, hash/verify pattern
  - Context7 `/websites/fastapi_tiangolo` — APIRouter prefix/tags/Depends, status_code=201 pattern
  - Context7 `/websites/sqlalchemy_en_20` — AsyncSession add/commit, JSONB insert pattern
  - Installed `.venv-t003` — direct package verification (pydantic 2.12.5, argon2-cffi 25.1.0, structlog 25.5.0)
  - WebFetch OWASP Password Storage Cheat Sheet — Argon2id minimums
- **Re-verify window**: 14 days (pydantic volatile-adjacent; argon2 stable)

#### Pydantic 2.12.5 EmailStr (DISCREPANCY — BLOCKER)
- `from pydantic import EmailStr` — import path is correct.
- BUT `email-validator` is **NOT** installed in `.venv-t003` and **NOT** in `backend/requirements.txt`.
- Pydantic v2 treats `email-validator` as an **optional extra** (`pydantic[email]`), NOT a transitive dep.
- Effect: `class SignUpRequest(BaseModel): email: EmailStr` raises `ImportError` at class-construction time — the entire module fails to import.
- Fix: add `email-validator>=2.0.0` to `requirements.txt` and `pip install email-validator` in `.venv-t003`.
- **Discrepancy note**: `orchestrator-state/memory/official-doc-notes/2026-05-10-P01-S02-T001-email-validator-missing-dep.md`

#### argon2-cffi 25.1.0 PasswordHasher (VERIFIED — exceeds OWASP 2024)
- Pattern: `ph = PasswordHasher(); ph.hash(password)` and `ph.verify(hash, password)` — confirmed correct.
- Installed defaults: `time_cost=3, memory_cost=65536 (64 MiB), parallelism=4, type=Argon2id`.
- OWASP 2024 minimums: `m=19456, t=2, p=1`. Project defaults far exceed these — no issue.
- Constructor tunable: `PasswordHasher(time_cost=N, memory_cost=N, parallelism=N)` — all confirmed.
- `check_needs_rehash(hash)` also available for migration scenarios.

#### FastAPI 0.136.1 APIRouter (VERIFIED)
- `APIRouter(prefix="/auth", tags=["auth"])` — confirmed idiomatic and current.
- `Depends()` for session injection — confirmed standard.
- `status_code=201` on `@router.post(...)` decorator — confirmed idiomatic for resource creation.
- No deprecations found in 0.136.1 for these patterns.

#### SQLAlchemy 2.0.49 AsyncSession JSONB INSERT (VERIFIED)
- ORM pattern: `session.add(MyModel(jsonb_col={"key": "val"}))` then `await session.commit()` — dict is accepted directly for JSONB columns.
- `async with session.begin(): session.add(...)` — begin() returns AsyncSessionTransaction, handles commit/rollback.
- `expire_on_commit=False` on sessionmaker prevents lazy-load errors post-commit (important for returning data after commit).
- No deprecations in 2.0.49 for these patterns.

#### structlog 25.5.0 (VERIFIED — from cache 2026-05-09, still within window)
- `from structlog.contextvars import bind_contextvars, clear_contextvars` — confirmed present in installed 25.5.0.
- PII masking: use redaction processor already wired in `app.core.logging`; bind as `email_masked=`, never `email=`.

- **Discrepancies**: ONE — `email-validator` missing dependency (BLOCKER). All other patterns verified.

### Entry 2026-05-10 — P01-S01-T005 Alembic 1.18.4 + SQLAlchemy 2.0.49 INET + asyncpg 0.31.0 INET decode (DEEP PASS — DISCREPANCY FOUND)

- **Sources**:
  - Context7 `/websites/alembic_sqlalchemy` — revision file pattern, op.add_column
  - Context7 `/websites/sqlalchemy_en_20` — Mapped nullable, mapped_column, INET type
  - Installed `asyncpg/pgproto/codecs/network.pyx` (asyncpg 0.31.0)
  - Installed `sqlalchemy/dialects/postgresql/asyncpg.py` (SA 2.0.49)
- **Re-verify window**: 30 days

#### Alembic 1.18.4 revision pattern (VERIFIED — unchanged)
- `revision = "0002"`, `down_revision = "0001"` top-level string vars. No decorator/metadata change in 1.18.x.
- `op.add_column("table", sa.Column("col", SomeType(), nullable=True))` — correct, no batch_op needed for PostgreSQL.
- `op.drop_column("table", "col")` for downgrade. Safe for existing PG tables.

#### SQLAlchemy 2.0.49 `Mapped[str | None]` for INET (VERIFIED syntax; see decode discrepancy)
- `Mapped[str | None]` with `mapped_column(INET())` is syntactically correct and accepted by the ORM.
- `from sqlalchemy.dialects.postgresql import INET` import is correct.

#### asyncpg 0.31.0 INET bind/decode (DISCREPANCY)
- **Bind/INSERT**: `inet_encode` accepts plain `str` like `'192.168.1.1'` — coerced via `ipaddress.ip_address(obj)`. No issue.
- **Select/decode**: `inet_decode` returns `ipaddress.IPv4Address` (not `str`) by default because `native_inet_types` defaults to `None` (not `False`) and the text-passthrough codec is only activated with `native_inet_types=False`.
- **Test assertion fix**: use `str(row.ip) == '192.168.1.1'` not `row.ip == '192.168.1.1'`.
- **Discrepancy note**: `orchestrator-state/memory/official-doc-notes/2026-05-10-P01-S01-T005-asyncpg-inet-decode-ipaddress-not-str.md` (marked RESOLVED by developer)

### Entry 2026-05-10 — P01-S01-T003 dotenv quoting convention + pydantic-settings + Vite dotenv handling (SHALLOW PASS — all verified)
- **Sources**: Context7 `/websites/saurabh-kumar_python-dotenv` (score 95.9), Context7 `/pydantic/pydantic-settings` (score 84.7), pydantic-settings official docs explicit statement.
- **Re-verify window**: 90 days (stable, mature libraries with no volatile changes).
- | Topic | Status | Detail |
- | dotenv quoted values (python-dotenv) | VERIFIED | Values with spaces MUST use double or single quotes: `KEY="Value With Spaces"`. Quotes are stripped during parsing. Unquoted spaces cause parse errors or truncation. Official: "Keys and values can be unquoted or quoted, whitespace surrounding keys/equal/values is ignored." |
- | bash `source .env` with spaces | VERIFIED | `KEY=Value With Spaces` → bash treats `With` as a command → "command not found". `KEY="Value With Spaces"` → works correctly. |
- | pydantic-settings dotenv parsing | VERIFIED | Pydantic-settings uses python-dotenv internally (official docs: "Pydantic uses python-dotenv to parse files, which supports bash-like syntax such as export"). Quotes are stripped before the value reaches pydantic. `MAIL_FROM_NAME="My App"` → field value is `My App`. No breakage. |
- | Vite frontend dotenv | VERIFIED | Vite uses dotenv-style parsing. `VITE_KEY="Value With Spaces"` → `import.meta.env.VITE_KEY === "Value With Spaces"` (quotes stripped). No breakage. |
- **Discrepancies**: NONE. Quoting values with spaces in .env.example is correct, safe, and standard across all layers.

## Original heading index
- # official-docs-researcher agent memory
- ## Full history archive
- ## Current operating invariants
- ## Trailer vocabulary
- ### Entry 2026-05-10 — P00-S02-T010 cryptography 48 Fernet + SQLAlchemy 2 async upsert + structlog masking (SHALLOW/TARGETED PASS)
- #### Verdicts (2026-05-10)
- ### Entry 2026-05-10 — P00-S02-T009 httpx 0.28.1 logger names + structlog stdlib integration (DEEP PASS)
- #### httpx 0.28.1 Logger Names (VERIFIED — CRITICAL)
- #### Structlog stdlib interaction (VERIFIED)
- #### httpx.MockTransport (VERIFIED — stable, idiomatic)
- #### Plan alignment (VERIFIED — no discrepancy)
- ### Entry 2026-05-10 — P00-S02-T011 cryptography 48 Fernet.generate_key + pydantic-settings 2.14.1 AliasChoices + POSIX bash sed (SHALLOW PASS — all verified)
- #### Verdicts (2026-05-10)
- ## High-signal preserved notes
- ### Entry 2026-05-10 — P00-S02-T007 Frontend: react-router v7, TanStack Query v5, i18next 26, Vitest 4, React 19, Zod v4 (TARGETED PASS)
- #### Verified verdicts (2026-05-10)
- #### Discrepancy note written
- ## Original heading index
- ## Canonical references

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.2026-05-10-044634.md`
