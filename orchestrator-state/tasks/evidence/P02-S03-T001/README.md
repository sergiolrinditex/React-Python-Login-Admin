# Evidence: P02-S03-T001 — Chat Conversation CRUD Endpoints

## Tester run: 2026-05-13

## Files

| File | What it proves |
|------|----------------|
| `pytest_chat_conversations.txt` | 14/14 integration tests PASS (T01-T14 chat CRUD) |
| `pytest_regression.txt` | 45/47 (2 skipped pre-existing seeded-data tests) auth_signin + users_me pass — no regression from +2 lines in app/main.py |
| `curl_signin.json` | POST /api/v1/auth/sign-in → access_token obtained for admin.peopletech |
| `curl_create_with_msg.json` | POST /api/v1/chat/conversations with initial_message → 201 + conversation_id |
| `curl_create_empty.json` | POST /api/v1/chat/conversations without initial_message → 201 + conversation_id |
| `curl_list.json` | GET /api/v1/chat/conversations?limit=20 → 200 + data array + pagination meta |
| `curl_get_detail.json` | GET /api/v1/chat/conversations/{id} → 200 + messages + citations |
| `curl_unauth_401.txt` | GET /api/v1/chat/conversations without Bearer → 401 AUTH_SESSION_EXPIRED |
| `curl_invalid_cursor_400.txt` | GET with ?cursor=not-valid-base64 → 400 CHAT_CURSOR_INVALID |
| `curl_404.txt` | GET /api/v1/chat/conversations/00000000-... → 404 CHAT_CONVERSATION_NOT_FOUND |
| `curl_403.txt` | User B GET User A's conversation → 403 CHAT_CONVERSATION_FORBIDDEN |
| `curl_pagination_roundtrip.json` | 25 conversations: page1=10 has_more=True, page2=10 has_more=True, page3=5 has_more=False cursor=null — all 7 contract checks PASS |
| `db_snapshots.txt` | DB state: conversations + messages tables (title, language, role, content_length) |
| `back_logs_verbose.txt` | ENABLE_VERBOSE_LOGGING=true: BEFORE/AFTER per router/service/repo, uid_hash present, no PII |
| `back_logs_quiet.txt` | ENABLE_VERBOSE_LOGGING=false: root logger WARNING level confirmed via subprocess test |
| `data-contract-used.txt` | Verification Data Contract rows and data used |

## Test outcome

- backend tests: 14/14 PASS (in isolation)
- regression tests: 45/47 (2 skipped pre-existing)
- curl smoke: all 8 endpoints/scenarios PASS
- logging verbose on: PASS (no PII, BEFORE/AFTER present)
- logging verbose off: PASS (WARNING level, no INFO/DEBUG)
- DB state: PASS (conversations + messages persisted correctly, no PII in logs)
- pagination: PASS (all 7 contract checks)
