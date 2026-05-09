# /verify-slice P00-S02-T006 — Evidence summary
Mode: pre-closer (T006 ready_for_close, no report yet, validator approved + tester pass)

## Hard-reset performed
- Stopped backend (PIDs 68750/80558/88472).
- Alembic downgrade base + upgrade head (0001 → 0003 confirmed).
- Reseed (auth seed OK; admin_ai seed FAILED with column "api_key" of relation "ai_providers" does not exist — proves FU-20260509220235).
- Restarted backend manually with ENCRYPTION_KEY (real Fernet key) + ENABLE_VERBOSE_LOGGING=true.
- Direct prod-like seed via parametrized SQL: 4 providers (gemini-direct, litellm-local, unsupported anthropic, gemini-nocred) + 3 encrypted credentials.

## Scenarios run (live curl from human caller)
| # | Scenario | Expected | Observed | Pass |
|---|----------|----------|----------|------|
| S1 | POST without auth | 401 + code=unauthorized | 401, code=unauthorized | YES |
| S2 | POST with non-admin Bearer token | 403 + code=forbidden | 403, code=forbidden | YES |
| S3 | POST with admin token, unknown provider UUID | 404 + code=provider_not_found | 404, code=provider_not_found | YES |
| S4 | POST with admin token, provider_type=anthropic | 422 + code=unsupported_provider_type | 422, code=unsupported_provider_type | YES |
| S5 | POST with admin token, provider has no credential row | 502 + code=upstream_provider_error msg="No active credential found" | 502, msg matches | YES |
| S6 | POST with admin token, malformed UUID (not-a-uuid) | 422 (FastAPI native uuid_parsing) | 422 uuid_parsing | YES |
| S7 | POST with admin token, LiteLLM provider | 502 (no-DB upstream env) — tester saw 200/total_seen=0 with different LiteLLM state | 502 upstream_provider_error HTTP 400 from LiteLLM ("No connected db.") | YES (mapping correct; tester's 200 path requires LiteLLM with DB/config) |
| S8 | POST with admin token, real Gemini provider | 200, total_seen >= 3, all auto_discovered=true | 200, added=50, existing=0, total_seen=50, latency 223ms | YES |
| S9 | Re-call S8 (idempotency) | 200, added=0, existing=50 | 200, added=0, existing=50, total_seen=50, latency 144ms | YES |

## DB persistence (post S9)
- ai_models: 50 rows, all auto_discovered=true. Real Gemini model_ids (models/gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash, models/aqa, deep-research-*, etc).
- audit_logs: 2 rows for action='ai.provider.discover_models', entity_type='ai_provider', entity_id matches gemini-direct provider, metadata has request_id/total_seen/added_count/existing_count/skipped_count/provider_type.

## Logging (verbose=true)
- BEFORE/AFTER visible for app.features.admin_ai.service and app.features.admin_ai.provider_clients.
- AFTER service log: latency_ms=203 (S8) and latency_ms=98 (S9).
- App-level loggers: NO Gemini key, NO encrypted_secret value present. encrypted_secret appears only as a SELECT column NAME from sqlalchemy engine echo (acceptable).
- httpx CONFIRMED leak: 2 lines of "HTTP Request: GET https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSyA9...<MASKED>" — proves FU-20260509220224 is real. Out of T006 scope (impacts core/logging.py).

## Logging (verbose=false)
- Cited from tester evidence: orchestrator-state/tasks/evidence/P00-S02-T006/logs-verbose-off.txt — only WARNING+ERROR shown; httpx silent at WARNING root.

## Verification Data Contract row used
- §6.5 row J103: admin user data/verification/users/admin_peopletech.json.email; provider/credential prod-like (gemini-direct with VERIFICATION_GEMINI_API_KEY); cleanup = "delete ai_provider test rows".
