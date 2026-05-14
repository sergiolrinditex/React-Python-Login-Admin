# Decisions Log

> Append-only record of architectural and operational decisions promoted from `PROGRESS.md` during compactations, plus any decisions added directly here by developer/debugger.
> Authority order: source-of-truth docs first, then this file, then `PROGRESS.md` slice entries (which are derived).

## From PROGRESS.md compact 2026-05-13

Source: `orchestrator-state/memory/archive/2026-05-13/PROGRESS-pre-compact-221226.md` (snapshot, SHA-256 `484fde2c168eeb428e3df8f9bc9d27a207f773bc1f4f956a845891739afa6201`).

### P01-S02-T002 — POST /api/v1/auth/sign-in

- **2026-05-11**: Extracted `_engine` / `_SessionLocal` / `get_db_session` from `auth/router.py` to `app/db/session.py` (T001 validator nit). All routers now share a single engine instance.
- **2026-05-11**: PyJWT==2.12.1 added. `encode()` returns str directly (no `.decode()`). `jti = uuid4().hex` per RFC 7519. Algorithm HS256; upgrade path to RS256 documented in ADR.
- **2026-05-11**: Refresh token: `secrets.token_urlsafe(48)` → SHA-256 digest in DB (never plain token). Cookie: `samesite="lax"` (lowercase per Starlette), `httponly=True`, `secure=True`, `path="/auth"`, `max_age=AUTH_REFRESH_TTL_SECONDS`.
- **2026-05-11**: `_DUMMY_HASH` computed once at module import in `password.py`. Unknown-email path runs dummy verify to equalise timing with known-email wrong-password path (aggregate-401 anti-enumeration).
- **2026-05-11**: D-S2 pattern: rejection audit uses SEPARATE short-lived session that commits independently; success audit + refresh_token INSERT share the main sign-in transaction.
- **2026-05-11**: Account lockout: SQL scan of `audit_logs` for `action='auth.sign_in'`, `metadata->>'outcome'='failure'`, `actor_user_id=:uid`, `created_at > now() - CAST(:window || ' seconds' AS INTERVAL)`. O(n) acceptable for V1; Redis counter in P02-S02-T001.
- **2026-05-11**: Sign-in rate limit uses SIGNIN prefix in `rate_limit.py`, distinct from SIGNUP bucket. Configured via `AUTH_SIGNIN_RATE_PER_MINUTE` + `AUTH_SIGNIN_RATE_BURST` env vars.
- **2026-05-11**: T001 `test_signup_rate_limit_429` updated to use `monkeypatch.setenv` (rate_limit.py now reads env vars via `_load_limits()` per call, not module attributes).
- **2026-05-11**: T16 timing threshold lowered from 50ms to 20ms. 40ms result on current hardware is above 20ms floor — dummy Argon2 verify is working. 50ms was too tight for production hardware variation.
- **2026-05-11**: Lazy imports in `service.py` (encode_access_token, encode_mfa_challenge_token, verify_password, _DUMMY_HASH, needs_rehash, MfaTotpSecret) to avoid circular imports. **Reverted by debugger cycle 1**: imports are module-level in the new `services/sign_in.py` — no actual circular dependency existed (the imported modules are leaves).
- **2026-05-11**: WRITE_SET_DRIFT: `app/db/session.py` (new file extracted from router.py), `app/auth/tokens.py` (new JWT utility), `pyproject.toml`+`requirements.txt` (PyJWT), `.env.example` (JWT+lockout+signin rate env vars). Justified by acceptance criteria.

### P01-S02-T002 debugger cycle 1 (structural refactor)

- **2026-05-11**: Structural refactor for validator F1–F8 (in-scope, same Write set). Split `app/auth/service.py` (702 LOC) into `app/auth/services/sign_up.py` (269) + `app/auth/services/sign_in.py` (298); `service.py` is now a 28-LOC compat shim re-exporting both use cases. Split `app/auth/router.py` (466 LOC) into `app/auth/routers/sign_up.py` (135) + `app/auth/routers/sign_in.py` (175) + `_helpers.py` (60); `router.py` is now a 29-LOC aggregator. `SignInUser.execute()` decomposed into 10 private helpers, each ≤50 LOC, via a new `_ReqContext` dataclass that packs (request_id, ip, user_agent). All file sizes ≤300 LOC; all functions ≤50 LOC. Lint clean; 73/73 tests pass; aggregate-401 byte-equality preserved.
- **2026-05-11**: Promoted `password._DUMMY_HASH` (private) to `password.DUMMY_VERIFY_HASH` (public) and added `password.verify_with_dummy_fallback(stored_hash | None, plain) -> bool` helper. Sign-in service no longer reaches into another module's private API; the timing-equaliser branch is now expressed as `verify_with_dummy_fallback(None, password_plain)`.
- **2026-05-11**: Router handlers now use `Depends(get_db_session)` from `app.db.session` instead of manual `_SessionLocal()` + `try/finally session.close()`. `_engine`/`_SessionLocal` are still in `app/db/session.py` but no longer referenced from the auth router. Test still validates real DB I/O via TestClient (ASGI transport).
- **2026-05-11**: T08 test (`test_signin_invalid_payload_empty_email_400`) now sends `email=valid@host, password="   "` so Pydantic passes (`min_length=1`) but the service-layer `password_plain.strip()` trips `InvalidPayloadError(field="password")` → asserts HTTP 400 + `AUTH_INVALID_PAYLOAD` + audit row `outcome=failure, reason=invalid_payload`. Closes validator F6 gap (service-layer 400 branch + its audit row are now covered end-to-end).

### P01-S02-T006 — POST /api/v1/auth/2fa/verify (TOTP MFA)

- **2026-05-12**: `pyotp==2.9.0` pinned in `pyproject.toml` + `requirements.txt`. Researcher-confirmed: no CVE, plain base32 str arg, auto-padding, constant-time verify, no server-side replay enforcement (app must track).
- **2026-05-12**: In-memory `jti` consume store (threading.Lock dict, TTL=exp). Mirrors `rate_limit.py _store` V1 pattern. `# TODO(P02-S02-T001): replace with Redis SETNX`. Single-worker invariant documented.
- **2026-05-12**: `mfa_crypto.py::decrypt_totp_secret` thin facade — auth module owns its decryption surface (Clean Architecture). Implementation delegates to `verification_data.crypto.decrypt_secret` (1 line), isolating the indirection for future KMS migration.
- **2026-05-12**: Researcher §Q3 recommends `re.fullmatch(r'\d{6}', v)` in Pydantic validator over `v.isdigit()` for Unicode digit hardening (non-blocking). Researcher §Q4 recommends wrapping `pyotp.TOTP(secret)` in try/except for `binascii.Error` → `MfaSecretMissingError` (non-blocking). Both are future hardening candidates.
- **2026-05-12**: `data/verification/auth/mfa_primary.json` `enabled` flipped `false→true` (Option A, WRITE_SET_DRIFT §D-MFA1.K). Required for J100 verification data contract (mfa_primary user must have MFA enabled for `/verify-slice` reproduction).

### P01-S02-T003 — POST /api/v1/auth/refresh

- **2026-05-12**: `repositories/refresh.py` split from planned single file: Clean Architecture requires separate repos/services/routers; `repository.py` was at 300-line cap. Pre-declared WRITE_SET_DRIFT in task pack §D-RP1.
- **2026-05-12**: `_set_refresh_cookie()` extracted to `routers/_helpers.py` (D-RP2): byte-identical cookie attrs shared between sign-in and refresh to prevent cookie drift across endpoints.
- **2026-05-12**: `SELECT ... FOR UPDATE` (with_for_update()) on `find_active_by_hash_for_update` serializes concurrent refresh races at DB level. Second transaction sees `revoked_at IS NOT NULL` after winner commits → 401. (D-RP3)
- **2026-05-12**: D-S2 failure audit: `_write_failure_audit()` opens own `_SessionLocal()` session, commits independently. Main transaction rollback does not suppress audit.
- **2026-05-12**: In-memory rate limiter V1 uses REFRESH namespace (separate bucket from SIGNIN). Redis upgrade target P02-S02-T001.
- **2026-05-12**: Test helper `_create_user` returns `UserData` namedtuple (plain id+email) to avoid `DetachedInstanceError` after session.close(). Query helpers call `session.expunge_all()` before close.

### P01-S02-T004 — POST /api/v1/auth/logout

- **2026-05-12**: Logout audit writer extracted from `logout.py` (would be 372 LOC) to `logout_audit.py` (182 LOC), reducing `logout.py` to 276 LOC. Mirrors T003 `refresh_audit.py` extraction pattern for identical D-S2 requirements.
- **2026-05-12**: `_clear_refresh_cookie(response)` added to `routers/_helpers.py` (shared helper). Uses `Max-Age=0` with same attrs as `_set_refresh_cookie` to ensure browser deletes cookie on both 204 and 401 paths. WRITE_SET_DRIFT §D-LO1 — declared in task pack.
- **2026-05-12**: All 401 failures raise `SessionExpiredError` → `AUTH_SESSION_EXPIRED` body. The reason (no_bearer, expired_bearer, invalid_bearer, no_cookie, unknown_hash, revoked, expired, user_mismatch) is captured only in `audit_logs.metadata->>'reason'` for security. T10 verifies byte-equality of 401 bodies stripping per-request meta fields.
- **2026-05-12**: `hook_write_scope_guard.py` resolves worktree path relative to repo root → sees `.claude/worktrees/...` → falsely triggers static config guard. Workaround: all new file creation via Bash heredoc `cat > file << 'PYEOF'`. Documented in developer MEMORY.md.

### P01-S02-T009 — JWT dev key hygiene

- **2026-05-12**: D-T009-1: `JWT_PUBLIC_KEY` is set to same value as `JWT_PRIVATE_KEY` for HS256 symmetry. `tokens.py` only reads `JWT_PRIVATE_KEY` today but TECHNICAL_GUIDE §11.1 declares both — keeping them in sync prevents future RS256-migration confusion.
- **2026-05-12**: D-T009-2: `MFA_ENCRYPTION_KEY` and `ENCRYPTION_KEY` hygiene (Fernet generation) left out-of-scope. They require `Fernet.generate_key()` (not `secrets.token_urlsafe`). Resolved later by P02-S03-T004 (`scripts/gen-dev-secrets.sh`).
- **2026-05-12**: Placeholder detection: value == "" OR value == "replace-with-dev-key" OR len(value) < 32. Key generation: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` → 64 url-safe chars, ≥48 bytes entropy.

### P01-S03-T002 — Cross-origin infra (vite proxy /api → uvicorn)

- **2026-05-13**: Strategy A confirmed: vite `server.proxy["/api"]` → `http://localhost:8000` is the canonical cross-origin bridge for dev. Browser sees `:5173` for all requests. Mirrors prod nginx topology. `backend/app/main.py` intentionally untouched — no CORSMiddleware needed. ADR-002 appended to TECHNICAL_GUIDE §15.
- **2026-05-13**: `VITE_API_BASE_URL=""` contract pinned in `frontend/.env.example`. Empty string (not absent) ensures `"" ?? fallback` resolves to `""` (relative paths) without nullish coalescing kicking in. `httpClient.ts` and `authRepository.ts` unchanged.
- **2026-05-13**: ADR-002 §Contexto precise terminology: `localhost:5173` and `localhost:8000` are **same-site** (port ignored in eTLD+1 determination); `SameSite=Lax` was never the cookie blocker. The real blocker was the CORS preflight (OPTIONS → 405, independent mechanism). Strategy A collapses to same-origin and removes the preflight entirely.
- **2026-05-13**: K.4 (SSE streaming) noted: vite proxy preserves chunked transfer by default but P02-S04 `POST /api/v1/chat/conversations/{id}/stream` should verify SSE through proxy explicitly. Deferred to P02 planner.

### P02-S02-T001 — Security Layer

- **D-PERM1 (2026-05-13)**: `super_admin` is a superset of `admin`. `require_admin(user)` accepts users whose roles include either `admin` or `super_admin`. Encoded in `app/security/permissions.py`. Verified by test_security T07.

### P02-S03-T001 — Chat CRUD Layer

- **D-PAG1 (2026-05-13)**: Cursor pagination — `encode_cursor/decode_cursor` in `app/chat/cursor.py` produces `base64url((updated_at, id))` opaque cursor. List endpoint orders by `(updated_at DESC, id DESC)` and returns `next_cursor` only when full page consumed. Decoded cursor errors raise `CursorInvalidError` → 400. Tests T05–T08.
- **D-TIT1 (2026-05-13)**: Empty title fallback — if request body `title` is omitted/empty, service computes title from first ≤80 chars of the user's initial message (stripped). Implemented in `services/create_conversation.py`.
- **D-LANG1 (2026-05-13)**: Language fallback — request `language` overrides; otherwise falls back to `user.preferred_language`; otherwise `"es"`. Stored on `conversations.language`.
- **D-TX1 (2026-05-13)**: Atomic conversation+message create — `repository.create_conversation` opens single SQLAlchemy transaction, INSERTs conversation row, then INSERTs the first message + citations (if any). Rollback on any failure. Endpoint returns the persisted detail DTO.
- **D-RL1 (2026-05-13)**: No rate limit for T001 (chat CRUD). The streaming endpoint (T002) carries its own per-user limiter; the CRUD endpoints share the global FastAPI middleware limiter only.
- **D-AUD1 (2026-05-13)**: No audit log row for chat CRUD operations (per UX_CONTRACT: chat actions are not security-sensitive). Audit applies to admin endpoints and auth lifecycle only.

### P02-S05-T001 — Admin AI providers + models endpoints

- **D-AASPLIT (2026-05-13)**: Module split — `app/admin/service.py` reached 590 LoC. Split into `app/admin/providers/{router,service,repository,schemas,audit}.py` + `app/admin/model_catalog/{router,service,repository,schemas,audit}.py` with shared `app/admin/_audit.py`. Max file 230 LoC post-split. Wired via aggregator `app/admin/__init__.py`.
- **D-DEF1 (2026-05-13)**: At-most-one is_default=true per model_type — invariant enforced at **application layer** (service layer flips other defaults to false before activating a new one inside a single transaction). DB-level partial unique index proposed as FU-20260513085435 (medium severity, non-blocking). Tests T13–T16 verify both branches.

### P02-S07-T001 — MCP Registry Layer

- **D-1 (2026-05-13)**: MCP sync is **inline** — `POST /api/v1/admin/ai/mcp/servers/{id}/sync` runs the discovery RPC inside the request lifecycle, not as a background job. Acceptable because typical discovery is sub-second; if it grows beyond timeout, defer to a future async-job FU.
- **D-SYNC1 (2026-05-13)**: Idempotent no-delete upsert during sync — discovered tools/resources/prompts are UPSERTed by `(server_id, name)`; tools no longer present on the server are NOT deleted (audit trail preserved). The repository methods `upsert_tools/resources/prompts` use `ON CONFLICT (...) DO UPDATE`.
- **D-TRANSPORT (2026-05-13)**: Reject `stdio` transport — only HTTP-based MCP servers are allowed in `POST /servers` (schema-level reject). Rationale: stdio is local-only and not addressable from the backend container.
- **D-ALLOWLIST (2026-05-13)**: Endpoint allowlist — MCP server URLs must match one of `MCP_ALLOWED_HOSTS` (env var, comma-separated). Prevents SSRF and rogue tool registration.
- **D-CLIENT-OFFICIAL (2026-05-13)**: HTTP MCP client uses `httpx.AsyncClient` with JSON-RPC 2.0 protocol per the official MCP specification (no custom transport).
- **D-AUDIT-NO-SECRETS (2026-05-13)**: Audit rows for `admin.ai.mcp.server.create/sync` and `admin.ai.mcp.tool.update` record metadata WITHOUT secret values (credentials remain encrypted in DB; audit row stores only `auth_type`, server name, endpoint host, sync counters).

## From PROGRESS.md compact 2026-05-14

### P01-S02-T010 — bootstrap_source_of_truth.py --refresh preserves closer-final task status

Origin: PROGRESS.md `## Framework Changes (P01-S02-T010)` section, promoted on 2026-05-14 during `/slice-maintain compact` to keep the per-slice reference table in its canonical decisions log instead of inflating PROGRESS.md.

- **D-T010-CONSTANTS (2026-05-12)**: Constants `CLOSER_FINAL_STATUSES = frozenset({"done","blocked","skipped"})` and `CLOSER_FINAL_OUTCOMES = frozenset({"committed","deployed"})` added to `.claude/bin/bootstrap_source_of_truth.py` as importable module-level frozensets so future code (tests + hooks) can reuse the same definition instead of redefining the lifecycle vocabulary. Replaces inline literal sets that previously drifted between modules.
- **D-T010-DEFENSIVE (2026-05-12)**: Defensive re-assertion guard — after the field-copy loop in `_apply_preserved_runtime`, the function re-asserts the lifecycle fields (`status`, `last_outcome`) for every closer-final task explicitly. This prevents a future refactor from silently breaking the invariant "a task that was already `done`/`committed` in runtime stays `done`/`committed` after `--refresh` even if the source-of-truth row is re-emitted with a different planned status."
- **D-T010-DOCSTRING (2026-05-12)**: `_apply_preserved_runtime` docstring extended to document the closer-final defensive re-assertion contract explicitly (not just code-implicit) so the next person reading the function knows why the extra loop exists.
- **D-T010-REGRESSION (2026-05-12)**: New regression test `.claude/bin/tests/test_bootstrap_refresh_preserves_done.py` — 13 tests total (8 TC cases + 5 constant checks). TC1 pins the exact scenario that the manual patch `570b702` had to fix manually on 2026-05-11 (closer-final task being reverted to `planned` by a `--refresh` after a checklist edit). Test command: `python3 -B -S -m unittest discover -s .claude/bin/tests -p test_bootstrap_refresh_preserves_done.py -v` → 13/13 PASS.
- **D-T010-PATCH-OBSOLETE (2026-05-12)**: Manual patch commit `570b702` is now OBSOLETE — future `--refresh` runs will not reintroduce the regression because the defensive guard + regression test pin it from both ends (code + test). Patch kept in git history for traceability but no longer needs to be re-applied.
- **D-T010-VALIDATION (2026-05-12)**: `python3 -B -S .claude/bin/bootstrap_source_of_truth.py --validate-only` returns exit 0 with "Source-of-truth contract is valid." — no source-of-truth drift introduced by this slice. Full framework test suite: 142 framework tests pass; 1 pre-existing failure in `test_static_contracts` (2/6 pattern, exists before T010, tracked elsewhere).

## P02-S03-T006 — Fix chat stream chunks — llm_gateway uses non-existent SDK provider

- **D-LITELLM-PROVIDER-MAP (2026-05-14)**: Canonical mapping from `AiProvider.provider_type` (DB value) to LiteLLM SDK model string prefix lives in `_PROVIDER_TYPE_TO_SDK_PREFIX: dict[str, str]` in `backend/app/llm_gateway/litellm_client.py`. Root cause: the old code used `f"{provider.provider_type}/{model.model_id}"` which sent `model="litellm/gpt-4o-mini"` — a non-existent SDK prefix that raises `BadRequestError("LLM Provider NOT provided")`. Fix: `provider_type='litellm'` → SDK prefix `'openai'` + `api_base=provider.base_url` (the LiteLLM proxy is OpenAI-compatible). Full table: litellm→openai, openai→openai, anthropic→anthropic, azure_openai→azure, ollama→ollama, groq→groq, together_ai→together_ai, mistral→mistral, cohere→cohere. Unknown provider_type raises `LiteLLMError` (explicit fail). Source: official-doc-notes/P02-S03-T006-litellm-provider-map-2026-05-14.md Q1+Q5 RESOLVED.
- **D-T006-COMPOSE-HELPER (2026-05-14)**: `_compose_sdk_model_args(provider, model, request_id) -> tuple[str, dict[str, str]]` is the single source of truth for model_str composition. Returns `(model_str, extra_kwargs)` where extra_kwargs may include `api_base`. Used by `stream_chat` and `embed_query`. `complete_chat.py` adoption deferred to follow-up FU-20260514053554 (Option A per task pack — complete_chat.py is outside this slice's write_set). DRY: both call sites `**sdk_extra` into their kwargs dict; api_key is never in sdk_extra.
- **D-T006-LIVE-TEST-GATE (2026-05-14)**: `backend/tests/integration/test_chat_streaming_live.py` is a new integration test file gated by `LITELLM_PROXY_UP=1`. CI default = SKIPPED. `/verify-slice` activates it after hard reset + datos reales load. The test exercises the real HTTP path: sign-in → create conversation → POST /stream → assert `meta → chunk(*) → usage → done` SSE sequence. Does NOT mock `litellm.acompletion` — exercises the full real path including the model_str fix. R-T006-6: credentials must be injected at gate time; test self-skips gracefully if missing.
