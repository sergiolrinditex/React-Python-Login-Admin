# Tester Cycle 2 Results — P00-S02-T011
# Timestamp: 2026-05-10T05:00:00Z

## Servers Status

- Backend: http://127.0.0.1:8000/health → 200 {"status":"ok","version":"0.0.0","uptime":1191.766}
- Frontend: http://localhost:5173/ → 200 OK
- DB: localhost:5433 (hilopeople_dev) → reachable via asyncpg

All servers UP.

## Test 1 — ENCRYPTION_KEY validation with new rotated key

### 1a — .env has valid rotated Fernet key (NOT the leaked QCg=)

```
PASS: .env has valid Fernet ENCRYPTION_KEY (len=44, masked ****qbQ=)
PASS: key was rotated (last4 != leaked QCg=)
```

### 1b — pydantic-settings loads new key correctly

```
encryption_key: len=44 masked=****qbQ=
```

PASS: pydantic-settings loads the new rotated key.

## Test 2 — Auth seed + Fernet round-trip with new key

### Auth seed (--only auth) with new key

Command: `ENCRYPTION_KEY=<from .env> python -m app.seeds.bootstrap_verification_data --source data/verification --only auth`

Result:
```json
{"namespace": "auth", "event": "seed.namespace.start", "bundle_type": "productive", ...}
{"namespace": "auth", "event": "seed.namespace.done", "duration_ms": 203.5, "persisted": 6, "skipped_missing_table": 0}
```

exit=0, encrypted=True, persisted=6

PASS: Auth seed succeeds with new key, no BundleLoadError.

### Fernet round-trip with new key

```
BEFORE encrypt_secret: encrypting credential
BEFORE _resolve_fernet_key: key resolved key_source=settings.encryption_key
AFTER encrypt_secret: credential encrypted successfully
BEFORE decrypt_secret: decrypting credential
AFTER decrypt_secret: credential decrypted successfully
PASS: encrypt/decrypt round-trip with new key works
```

PASS: Full round-trip encrypt/decrypt works.

## Test 3 — Discover-models endpoint NO CryptoError post-rotation

### Provider row updated with new-key-encrypted credential

Provider: gemini-direct (id=3cba3194-1cb8-4c87-b65b-98fdc5a8229c)
DB round-trip decrypt: PASS masked=****cle2 (synthetic-test-key-cycle2)

### Discover-models curl

```
curl -X POST http://127.0.0.1:8000/api/v1/admin/ai/providers/3cba3194.../discover-models
  -H "Authorization: Bearer dev-admin-tester-cycle2"
```

Response: {"detail":{"error":{"code":"upstream_provider_error","message":"Gemini API returned HTTP 400"}}}
HTTP status: 502

OUTCOME: PASS — Error is upstream_provider_error (Gemini rejected synthetic key), NOT CryptoError.
The Fernet decrypt step succeeded; the failure is at the Gemini API layer (expected with synthetic credential).

Note: The 3 pre-existing ai_provider_credentials rows were encrypted with the OLD key (residual risk
documented by debugger). The gemini-direct credential was manually updated to use a new-key-encrypted
synthetic value for this test. Full reseed requires --reset (blocks on VERIFICATION_GEMINI_API_KEY
in .env.local for admin_ai namespace, and on T010 api_key column bug being fixed).

## Test 4 — Backend tests (no new regressions)

Full suite: pytest tests/ (139 passed, 11 skipped, 1 failed)

Failed test: tests/test_health.py::test_ready_returns_200_when_db_ok
- Passes in isolation (1 passed in 0.50s)
- Fails in full suite due to asyncio event-loop ordering issue
- Status: PRE-EXISTING (documented in PROGRESS.md: "1 event-loop ordering issue in full suite")
- NOT a T011 regression

Test count comparison:
- Cycle 1: 139 pass + 11 skip + 1 fail (pre-existing)
- Cycle 2: 139 pass + 11 skip + 1 fail (same pre-existing)
- No new failures introduced.

## Test 5 — Security re-audit

All checks pass. See security-audit-cycle2.txt for full detail.

Key findings:
- Old leaked key (****QCg=): NO full 44-char key in ledger commands [PASS]
- New rotated key (****qbQ=): NOT exposed in ledger [PASS]
- encryption-key.runtime: does not exist [PASS]
- .gitignore covers dev-logs/*: PASS
- git ls-files dev-logs: only .gitkeep [PASS]
- dev-restart.profile.sh: plaintext persistence removed [PASS]

Caveat: ledger.jsonl contains partial fragments (FRzm_vOl, MKYeG_TI etc.) from the
debugger's own redaction script code — these are template string placeholders, NOT
the actual 44-char Fernet key.

## Test 6 — Logging in both ENABLE_VERBOSE_LOGGING modes

### verbose=true
- Shows BEFORE configure_logging, BEFORE/AFTER _get_engine, BEFORE/AFTER get_settings
- Shows BEFORE/AFTER load_fixture, BEFORE/AFTER table_exists
- Shows seed.namespace.start and seed.namespace.done with persisted count
- PASS: BEFORE/AFTER pattern present

### verbose=false
- Output is clean (no DEBUG output, only pre-config [logging] line)
- No warn/error raised during successful seed
- PASS: only warning+error visible

### Key NOT in logs (both modes)
- grep for ****qbQ= in verbose output: 0 occurrences [PASS]
- grep for QCg= in verbose output: 0 occurrences [PASS]

## Overall Verdict

All cycle 2 acceptance criteria met:

1. .env has valid Fernet ENCRYPTION_KEY (len=44, last4=****qbQ=) — PASS
2. Key was rotated from leaked ****QCg= to new ****qbQ= — PASS
3. pydantic-settings loads new key — PASS
4. Auth seed (--only auth) exit_code=0, persisted=6 — PASS
5. Fernet round-trip works with new key — PASS
6. Discover-models endpoint returns upstream_provider_error NOT CryptoError — PASS
7. Backend tests: 139 pass, 11 skip, 1 pre-existing fail (no new regressions) — PASS
8. Security: no full leaked key (old or new) in ledger — PASS
9. gitignore covers dev-logs — PASS
10. encryption-key.runtime absent — PASS
11. dev-restart.profile.sh no plaintext key persistence — PASS
12. Verbose logging shows BEFORE/AFTER; key NOT in logs — PASS

All leaks closed. No regressions introduced.
