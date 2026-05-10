# official-docs-researcher agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.2026-05-09-221733.md`
- Original lines: 658
- Original SHA-256: `4a22d0e9a07d05ed38b25e51af640dd7b588dc41925fed3ec3e15c43f4938d9b`
- Compacted at: `2026-05-09-221733`
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

### Entry 2026-05-10 — P00-S02-T010 cryptography 48 Fernet + SQLAlchemy 2 async upsert + structlog masking (SHALLOW/TARGETED PASS)

**Sources consulted**:
- MEMORY cache hit: cryptography 48 Fernet (2026-05-09 T005, 2026-05-10 T011) — within 7-day window, stable
- Context7 `/websites/sqlalchemy_en_20` — async upsert ON CONFLICT DO UPDATE, engine.begin() transaction pattern
- Context7 `/hynek/structlog` — secret masking processors, DropEvent pattern

#### Verdicts (2026-05-10)

| # | Topic | Status | Key finding |
|---|---|---|---|
| 1 | `cryptography.Fernet(key_bytes)` + encrypt/decrypt | VERIFIED (CACHE HIT) | API unchanged in 48.x. `Fernet(bytes).encrypt(plaintext.encode()).decode()` is idiomatic. Key NEVER logged in `security.py` — only `key_source` field. No deprecations. MultiFernet: informational, not needed here. |
| 2 | SQLAlchemy 2.0 async `text()` upsert | VERIFIED | `text()` with `:param` binding for `INSERT ... ON CONFLICT ... DO UPDATE` is valid and safe. The preferred idiomatic path is `from sqlalchemy.dialects.postgresql import insert` + `on_conflict_do_update(index_elements=[...], set_=...)` but `text()` is fully accepted for seed/CLI code. No migration required. |
| 3 | `async with engine.begin() as conn:` transaction pattern | VERIFIED | Canonical SQLAlchemy 2.0 Core async pattern. `engine.begin()` auto-commits on exit. `await session.commit()` is the ORM Session path — different interface. Seed loader correctly uses Core path. |
| 4 | `ON CONFLICT (name)` vs `ON CONFLICT (provider_id, model_id)` | TASK DESIGN — NOT API ISSUE | Column choice in ON CONFLICT depends on which UNIQUE constraint exists in DB schema. Not a library API discrepancy. T010 must use the constraint matching the actual DB unique index. |
| 5 | structlog 25.5.0 secret masking | VERIFIED | Recommended pattern: custom processor that redacts fields (`event_dict["key"] = "***REDACTED***"`). Codebase approach (never passing sensitive value to logger at all) is **strictly safer** — value never enters event dict. No change needed. `structlog.DropEvent` for filtering entries is also documented. |

**Discrepancies**: NONE. All patterns in codebase align with or exceed official guidance.

Re-verify after 2026-05-17 (7-day window; all three are stable mature libraries).

### Entry 2026-05-10 — P00-S02-T009 httpx 0.28.1 logger names + structlog stdlib integration (DEEP PASS)

**Sources consulted**:
- Context7 `/encode/httpx` — logging docs, MockTransport docs
- WebFetch `https://www.python-httpx.org/logging/` — official logging page
- WebFetch `https://www.python-httpx.org/advanced/transports/` — official transports page
- WebFetch `https://raw.githubusercontent.com/encode/httpx/master/docs/logging.md` — raw logging.md
- WebFetch `https://github.com/encode/httpx/blob/0.28.1/httpx/_transports/mock.py` — MockTransport source at tag 0.28.1
- Context7 `/hynek/structlog` — stdlib integration docs

#### httpx 0.28.1 Logger Names (VERIFIED — CRITICAL)

Two distinct loggers, both official, both documented:

| Logger name | Level | What it emits |
|---|---|---|
| `httpx` | **INFO** | `"HTTP Request: GET https://example.com?key=AIza... HTTP/1.1 200 OK"` — the full URL WITH query string |
| `httpcore` | **DEBUG** | TCP/TLS connection details, request headers, response headers, body bytes |

**KEY FINDING**: The URL-with-query-string line (`?key=AIza...`) is emitted by the `httpx` logger at **INFO level** — not DEBUG. This means `ENABLE_VERBOSE_LOGGING=false` does NOT suppress it by default (INFO is above DEBUG but both are emitted by default if root logger is at WARNING or lower). Setting `logging.getLogger("httpx").setLevel(logging.WARNING)` WILL suppress it.

**No third logger**: There is no separate transport-layer logger beyond `httpcore`. The fix targeting only `logging.getLogger("httpx").setLevel(logging.WARNING)` is sufficient to suppress the URL line. `httpcore` does NOT emit the URL at INFO — only TCP-level details at DEBUG.

#### Structlog stdlib interaction (VERIFIED)

When `structlog.stdlib.LoggerFactory()` is used, structlog delegates to stdlib `logging.Logger`. Setting `logging.getLogger("httpx").setLevel(logging.WARNING)` via stdlib is the correct and sufficient approach — it operates at the stdlib layer before structlog ever sees the record. No `ProcessorFormatter` changes needed for suppression of third-party loggers. The structlog ProcessorFormatter only processes records that pass the stdlib level gate; if stdlib rejects the record, structlog never sees it.

#### httpx.MockTransport (VERIFIED — stable, idiomatic)

- `httpx.MockTransport(handler)` — documented, stable, no version caveats.
- Handler signature: `def handler(request: httpx.Request) -> httpx.Response:`
- For `AsyncClient`: handler can be `async def` — `handle_async_request()` detects coroutine and awaits it.
- A sync handler CANNOT be used directly with `AsyncClient`; use `async def handler` for async tests.
- Idiomatic for unit tests; official docs acknowledge it; no deprecation or instability noted in 0.28.1.

#### Plan alignment (VERIFIED — no discrepancy)

The planner's strategy (`logging.getLogger("httpx").setLevel(logging.WARNING)`) is correct and complete:
- Targets exactly the right logger (`httpx`, not `httpcore`)
- Suppresses the INFO-level URL line (which contains `?key=...`)
- Does not require structlog changes
- MockTransport with async handler is idiomatic for the unit test reproducing the leak vector

Re-verify after 2026-05-17 (7-day stability window for mature library).

### Entry 2026-05-10 — P00-S02-T011 cryptography 48 Fernet.generate_key + pydantic-settings 2.14.1 AliasChoices + POSIX bash sed (SHALLOW PASS — all verified)

**Sources consulted**:
- Context7 `/websites/cryptography_io_en` — Fernet docs, generate_key API, KDF/password usage
- Context7 `/pyca/cryptography` — fernet.rst canonical source
- Context7 `/pydantic/pydantic-settings` — AliasChoices, validation_alias, multiple env var names (cache hit 2026-05-09)
- POSIX sed spec + GNU sed manual (well-known, no MCP needed; cache knowledge confirmed against docs)

#### Verdicts (2026-05-10)

| # | Topic | Status | Key finding |
|---|---|---|---|
| 1 | `Fernet.generate_key()` return type | VERIFIED | Returns `bytes` — "A URL-safe base64-encoded 32-byte key." `.decode()` to get `str` for `.env` is correct and idiomatic. |
| 2 | Fernet key length | VERIFIED | 32 bytes of entropy, base64url-encoded = 44 ASCII chars. No change in cryptography 44-48. |
| 3 | Fernet deprecations/AEAD replacement in cryptography 48 | VERIFIED — NONE | No deprecations for Fernet API in cryptography 48.x. Fernet remains the recommended symmetric encryption recipe. No AEAD replacement is pushed by the docs for this use case. |
| 4 | KDF for direct key gen (no password) | VERIFIED | KDF (PBKDF2HMAC/Argon2/Scrypt) is only documented for the "derive key from password" use case. For `Fernet.generate_key()` (machine-generated random key), no KDF is needed or recommended. Dev `.env` usage is correct. Production should use KMS/secrets manager — out of scope. |
| 5 | pydantic-settings 2.14.1 AliasChoices | VERIFIED (CACHE HIT 2026-05-09) | `Field(validation_alias=AliasChoices('ENCRYPTION_KEY', 'PROVIDER_ENCRYPTION_KEY'))` is canonical. Uses first env var found. No API change in 2.13.x → 2.14.x. |
| 6 | bash `sed -i.bak` portability | VERIFIED | `-i.bak` is portable: BSD sed (macOS) requires backup extension; `-i.bak` + `rm -f .bak` works on both BSD and GNU. Alternative: `sed '...' file > file.tmp && mv file.tmp file` also portable. Both idioms are correct. |
| 7 | Idempotent append `grep -q \|\| echo >> ` | VERIFIED | `grep -q '^ENCRYPTION_KEY=' .env \|\| echo "ENCRYPTION_KEY=$key" >> .env` is standard POSIX idiom. Correct and robust. |

**Discrepancies**: NONE. Plan KISS is fully aligned with cryptography 48.x + pydantic-settings 2.14.1 + POSIX bash.

Re-verify after 2026-05-17 (7-day window; cryptography is a stable mature library).

## High-signal preserved notes
- # official-docs-researcher MEMORY
- **Source**: Installed venv source `backend/.venv-t003/lib/python3.11/site-packages/pydantic_settings/` (version verified: 2.14.1). Context7 `/pydantic/pydantic-settings` + `/websites/alembic_sqlalchemy`.
- #### DotenvType (verified from installed source, types.py line 35)
- - Neither defaulted to anything different in prior versions that would require a change here.
- Task pack §8 plan (Option A with `str(_PROJECT_ROOT / ".env")`) is correct and idiomatic. No deprecations. Path objects are first-class in `DotenvType`. No discrepancy note required.
- ### Entry 2026-05-09 — P00-S02-T002 Health live/ready endpoints (SHALLOW PASS — all verified)
- **Note file**: `orchestrator-state/memory/official-doc-notes/P00-S02-T002-health-endpoints-patterns-2026-05-09.md`
- | 1 | FastAPI router include + ops | VERIFIED | `app.include_router(router)` canonical; `@app.middleware("http")` for request_id middleware |
- | 2 | SQLAlchemy 2.0 async SELECT 1 | VERIFIED | `async with engine.connect() as conn: await conn.execute(text("SELECT 1"))` |
- | 3 | SQLAlchemy/asyncpg exception for DB down | VERIFIED | Catch `sqlalchemy.exc.SQLAlchemyError` — covers OperationalError + InterfaceError; asyncpg raw exceptions NOT exposed |
- | 4 | structlog 25.5.0 contextvars API | VERIFIED | `structlog.contextvars.bind_contextvars` / `clear_contextvars` confirmed present and unchanged |
- | 5 | httpx 0.28 ASGITransport | VERIFIED | `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` — `app=` param removed in 0.28 |
- | 6 | pytest-asyncio 1.3.0 auto mode | VERIFIED | `asyncio_mode="auto"` confirmed in pyproject.toml line 122; no decorator needed |
- System `python3` has FastAPI 0.135.2; project venv `.venv-t003` has 0.136.1 (correct). Developer must use project venv.
- - Context7 `/i18next/i18next/v26.0.2` — init API, fallbackLng, ns, defaultNS, resources, supportedLngs, interpolation
- - Context7 `/i18next/react-i18next` — initReactI18next, useSuspense, I18nextProvider, TypeScript
- - Context7 `/websites/vite_dev` — JSON imports, publicDir behavior, import.meta.glob eager
- #### Pinned versions confirmed (from frontend/package.json read 2026-05-09)
- | Package | Pinned version | Status |
- | i18next | 26.0.10 | Current stable in Context7 catalog (v26.0.2 docs apply — same major.minor) |
- | vite | 8.0.11 | Confirmed; publicDir behavior verified |
- #### Verified API patterns for i18next 26 + react-i18next 17
- | `fallbackLng: 'es'` (string, singular) | YES | Docs show `fallbackLng: 'en'` (string) as primary example; `string \| string[]` both valid |
- - `whitelist` → `supportedLngs` (changed in i18next 21, still current in v26) — developer must NOT use `whitelist`.
- - `cleanCode`/`lowerCaseLng`: no changes noted in v26 docs for these defaults.
- **DISCREPANCY NOTE WRITTEN**: `orchestrator-state/memory/official-doc-notes/P00-S01-T005-i18n-vite-public-vs-src-import.md`
- `orchestrator-state/memory/official-doc-notes/P00-S01-T005-i18n-vite-public-vs-src-import.md`
- - Context7 `/vitejs/vite/v8.0.0` — Vite 8 entry pattern, vite.config.ts defineConfig, test config co-location
- - Context7 `/vitest-dev/vitest/v4.0.7` — Vitest 4 defineConfig, environment jsdom, setupFiles
- - Context7 `/remix-run/react-router` — v7 minimal createBrowserRouter + RouterProvider pattern
- - Context7 `/facebook/react/v19_2_0` — React 19 createRoot, main.tsx mount pattern
- - Context7 `/testing-library/jest-dom` — v6 Vitest-specific setup file import path
- #### Verified patterns (2026-05-09)
- | @testing-library/jest-dom v6 Vitest setup | **ACTIONABLE**: Setup file must use `import '@testing-library/jest-dom/vitest'` NOT `extend-expect`. Note written. | NOTE |
- `orchestrator-state/memory/official-doc-notes/P00-S01-T004-testing-library-vitest-setup.md`
- Severity: warn-only. Developer must use the correct import path. Note contains `RESOLVED:` line.
- All stack components verified 2026-05-09 — re-verify after 7 days (2026-05-16).
- ### Entry 2026-05-09 — P00-S02-T005 Gemini models, MCP LangChain, deepagents supervisor, argon2, Fernet (DEEP PASS)
- - WebFetch `https://ai.google.dev/gemini-api/docs/models` — Gemini model catalog
- - WebFetch `https://ai.google.dev/gemini-api/docs/models/gemini` — Gemini model details
- - WebFetch `https://ai.google.dev/api/generate-content` — API base URL version
- - Context7 `/googleapis/python-genai` v1.33.0 — Gen AI Python SDK (current, NOT deprecated)
- - Context7 `/langchain-ai/deepagents` — deepagents GitHub repo
- - Context7 `/websites/langchain_oss_python_deepagents` — deepagents official docs
- - WebFetch `https://docs.langchain.com/mcp` — MCP server endpoint
- - WebFetch `https://pypi.org/pypi/argon2-cffi/25.1.0/json` — package info
- - WebFetch `https://argon2-cffi.readthedocs.io/en/stable/api.html` — PasswordHasher API
- - WebFetch `https://cryptography.io/en/latest/fernet/` — Fernet API
- - WebFetch `https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html` — OWASP 2024
- #### Unknown #1 — Gemini model IDs (VERIFIED — all correct)
- | `text-embedding-004` | NOT IN DOCS | Does NOT appear in current model catalog. Do not use. |
- Note file: `orchestrator-state/memory/official-doc-notes/2026-05-09-gemini-models.md`
- #### Unknown #2 — OpenAI model IDs (PARTIALLY VERIFIED — platform docs 403)
- OpenAI platform docs returned 403 (auth required). PyPI openai SDK confirms v2.36.0 current
- These are the `openai-direct` INACTIVE provider in T005 bundle. Low risk — provider inactive by default.
- #### Unknown #3 — LangChain MCP server `https://docs.langchain.com/mcp` (VERIFIED — ACTIVE)
- The URL responded with a valid MCP server configuration (not 404):
- - **Server name**: "Docs by LangChain"
- - **Tools**: `search_docs_by_lang_chain` + `query_docs_filesystem_docs_by_lang_chain`
- Implication for T005: `docs-langchain` server entry with `access_token=null` is CORRECT.
- Note file: `orchestrator-state/memory/official-doc-notes/2026-05-09-mcp-langchain-server.md`
- #### Unknown #4 — deepagents 0.5.7 Supervisor pattern (VERIFIED — important nuance)
- Note file: `orchestrator-state/memory/official-doc-notes/2026-05-09-deepagents-supervisor.md`
- #### Unknown #5a — argon2-cffi 25.1.0 PasswordHasher API (VERIFIED)
- - `time_cost=3`, `memory_cost=65536` (64 MiB), `parallelism=4`, `hash_len=32`, `salt_len=16`
- #### Unknown #5b — cryptography 48.0.0 Fernet API (VERIFIED)
- - `ENCRYPTION_KEY` env var must be a valid 32-byte URL-safe base64-encoded key
- - Context7 `/fastapi/fastapi` (versions listed: 0.115.13, 0_116_1, 0.118.2, 0.122.0, 0.128.0) — Source Reputation: High
- - Context7 `/facebook/react` (versions listed: v18_3_1, v19_1_1, v19_2_0, v17.0.2) — Source Reputation: High
- - Context7 `/vitejs/vite` (versions listed: v7.0.0, v5.4.21, v8.0.0, v7.3.1, v8.0.7, v8.0.10) — Source Reputation: High
- - Context7 `/vitest-dev/vitest` (versions listed: v3_2_4, v4.0.7) — Source Reputation: High
- #### Verified versions (2026-05-08)
- | FastAPI | **0.128.0** | Highest version in Context7 catalog; confirmed stable. Import: `from fastapi import FastAPI`. `app = FastAPI()` + `@app.get("/health")` pattern unchanged from 0.10x. |
- | React + react-dom | **19.2.0** (latest), 18.3.1 also stable | Both are stable. React 19 is the current recommended version. react-dom must match react version. |
- Verified for: P00-S01-T001 (scaffold only — `backend/app/main.py` + `frontend/package.json` stubs).
- NOT verified yet (reserved for their respective tasks):
- - LangChain, LangGraph, LiteLLM, DeepAgents — T003 (AI/ML volatile, MUST re-verify)
- - npm registry live queries (2026-05-08): `npm view <pkg> version peerDependencies --json`
- - Context7 `/remix-run/react-router` (Source Reputation: High) — v7 breaking changes + package consolidation
- - Context7 `/react-hook-form/resolvers` (Source Reputation: High) — zod v3/v4 resolver support

### Entry 2026-05-10 — P00-S02-T007 Frontend: react-router v7, TanStack Query v5, i18next 26, Vitest 4, React 19, Zod v4 (TARGETED PASS)
- Context7 `/remix-run/react-router/react_router_7_8_2` — createBrowserRouter route config, children, index routes
- Context7 `/tanstack/query/v5.90.3` — useMutation flags: isPending, isError, isSuccess, mutate, mutateAsync, data
- Context7 `/colinhacks/zod/v4.0.1` — uuid validation, z.string().uuid() deprecated
- Context7 `/vitest-dev/vitest/v4.0.7` — vi.spyOn, vi.fn, waitFor, findByText, async mocking
- MEMORY cache hit: i18next 26 + react-i18next 17 (2026-05-09), React 19 (2026-05-08), Vite 8 (2026-05-09)
#### Verified verdicts (2026-05-10)
| # | Topic | Status | Key finding |
|---|---|---|---|
| 1 | react-router-dom v7.15.0 createBrowserRouter | VERIFIED | `createBrowserRouter([{ path, element, children }])` + `RouterProvider` is still canonical in v7.8.2+ (latest in Context7). Route config object shape unchanged. `children` array works, `index: true` marks index routes. No breaking changes to flat route array ordering. Adding 2 flat routes to existing array is safe. |
| 2 | TanStack Query v5.90.3 useMutation flags | VERIFIED | `isPending` (not `isLoading`) is the v5 canonical name. `isLoading` renamed to `isPending` since v5. Exposed: `mutate`, `mutateAsync`, `isPending`, `isError`, `isSuccess`, `data`, `error`, `reset`. Developer pack §12.2 can skip useMutation entirely and use fetch+useState — both patterns valid. |
| 3 | i18next 26 + react-i18next 17 useTranslation namespace | VERIFIED (CACHE HIT 2026-05-09) | `useTranslation('admin-ai')` namespace lookup stable. JSON eager-import pattern stable. `fallbackLng: 'es'` honored. `whitelist` → `supportedLngs` (changed in v21, still current). No new issues. |
| 4 | Vitest 4.0.7 vi.spyOn / vi.fn / waitFor | VERIFIED | `vi.spyOn(globalThis, 'fetch')` pattern stable. `vi.fn()` + `mockResolvedValueOnce` / `mockRejectedValueOnce` confirmed. `waitFor` still available (RTL); Vitest v4 docs note `await expect.element()` as preferred in browser mode, but `waitFor` + `findByText` remain valid for jsdom mode. `--run` flag still single-pass CI mode. |
| 5 | React 19 StrictMode + useEffect double-invocation | VERIFIED (CACHE HIT 2026-05-08) | StrictMode double-invokes effects in dev. Developer MUST put discover POST in event handler (button onClick), NOT in useEffect. This is the correct pattern regardless — confirm the task pack already instructs this (§5.2 step 2: "Click Discover → step 2"). |
| 6 | Zod v4.4.3 z.string().uuid() | DISCREPANCY | `z.string().uuid()` is DEPRECATED in v4. Canonical form is `z.uuid()` (top-level). Still works at runtime but marked `// ❌ deprecated` in official changelog. Discrepancy note written. |
#### Discrepancy note written
- `orchestrator-state/memory/official-doc-notes/P00-S02-T007-zod-v4-uuid-deprecation.md`

## Original heading index
- # official-docs-researcher MEMORY
- ## Session cache
- ### Entry 2026-05-09 — P01-S01-T004 pydantic-settings 2.14.1 env_file absolute path + alembic 1.18.4 Settings injection (DEEP PASS)
- #### DotenvType (verified from installed source, types.py line 35)
- #### Idiomatic pattern for cwd-independent resolution (both options valid)
- #### Alembic 1.18.4 — Settings injection via get_engine()
- #### env_file_encoding and case_sensitive defaults (pydantic-settings 2.14.1)
- #### Discrepancies: NONE
- ### Entry 2026-05-09 — P00-S02-T002 Health live/ready endpoints (SHALLOW PASS — all verified)
- #### Cache stamps (2026-05-09)
- #### Environment finding (non-blocking)
- #### Discrepancies: NONE
- ### Entry 2026-05-09 — P00-S01-T005 i18n resources ES/EN/FR (DEEP PASS — targeted)
- #### Sources consulted
- #### Pinned versions confirmed (from frontend/package.json read 2026-05-09)
- #### Verified API patterns for i18next 26 + react-i18next 17
- #### Deprecations / renamed props confirmed
- #### Critical finding — Vite publicDir + static import conflict
- #### Vitest + JSON imports
- #### Note file written
- #### Freshness window
- ### Entry 2026-05-09 — P00-S01-T004 Design tokens + editorial system (shallow pass)
- #### Sources consulted
- #### Verified patterns (2026-05-09)
- #### Note file written
- #### Discrepancies found
- #### Freshness window
- ### Entry 2026-05-09 — P00-S02-T005 Gemini models, MCP LangChain, deepagents supervisor, argon2, Fernet (DEEP PASS)
- #### Sources consulted
- #### Unknown #1 — Gemini model IDs (VERIFIED — all correct)
- #### Unknown #2 — OpenAI model IDs (PARTIALLY VERIFIED — platform docs 403)
- #### Unknown #3 — LangChain MCP server `https://docs.langchain.com/mcp` (VERIFIED — ACTIVE)
- #### Unknown #4 — deepagents 0.5.7 Supervisor pattern (VERIFIED — important nuance)
- #### Unknown #5a — argon2-cffi 25.1.0 PasswordHasher API (VERIFIED)
- #### Unknown #5b — cryptography 48.0.0 Fernet API (VERIFIED)
- #### Discrepancies found
- ### Entry 2026-05-08 — P00-S01-T001 scaffold pass
- #### Sources consulted
- #### Verified versions (2026-05-08)
- #### Canonical FastAPI pattern (unchanged from 0.10x)
- #### Key compatibility matrix
- #### Discrepancies found
- #### Freshness window
- #### Task scope
- ### Entry 2026-05-08 — P00-S01-T002 Frontend dependency pack
- #### Sources consulted
- #### Verified versions (2026-05-08)
- #### Additional testing-lib packages queried (also for T002)
- #### Key compatibility findings
- #### Discrepancies / notes opened
- #### Freshness window
- #### Task scope
- ### Entry 2026-05-09 — P00-S02-T001 Docker compose image tags (DEEP PASS — all new topics)
- #### Cache stamps (2026-05-09)
- #### Discrepancies found (require developer action)
- ### Entry 2026-05-08 — P00-S01-T003 Backend dependency pack (DEEP PASS — user requested re-verify all)
- #### Verified versions (2026-05-08)
- #### Key findings from T003 deep pass
- ### Entry 2026-05-09 — P00-S02-T003 Seed data + verification bundle (SHALLOW/TARGETED PASS)
- #### Topic verdicts (2026-05-09)
- #### Key findings
- #### Sources consulted
- ### Entry 2026-05-09 — P00-S02-T004 structlog 25.5.0 RichTracebackFormatter / ConsoleRenderer / frame-locals redaction (DEEP PASS)
- #### Sources consulted
- #### Verified API surface for structlog 25.5.0
- #### Planner's Option C validation
- #### Additional finding — `format_exc_info` processor (JSON path)
- #### Discrepancies: NONE
- ### Entry 2026-05-09 — P01-S01-T001 Alembic async env.py + SQLAlchemy 2 DeclarativeBase + pgcrypto/pgvector (DEEP PASS — targeted patterns)
- #### Sources consulted
- #### Verified API patterns (2026-05-09)
- #### CRITICAL FINDING — Async env.py API correction
- #### Naming convention key format — minor discrepancy
- #### Discrepancies found (for developer awareness)
- #### No note file needed — not a blocker, developer guidance inline above. No RESOLVED line required.

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.2026-05-09-221733.md`
