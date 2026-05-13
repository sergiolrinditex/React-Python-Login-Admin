# /verify-slice — Evidence Summary — P02-S07-T001 (MCP server and tool endpoints)

- TIMESTAMP: 2026-05-13T13:45:00+02:00
- MODE: pre-closer
- VERIFY_OUTCOME: verified

## Environment

Hard reset performed **scoped** because the parallel worktree `P02-S04-T001`
has its own uvicorn on `:8000` against the shared Rancher/Postgres. A full
DB drop would have invalidated their verification. Coordinated with the user
who chose the isolated-verify option (single-question selector).

| Item | Value |
|---|---|
| Backend | uvicorn `app.main:app` on `127.0.0.1:8001` (own PID) |
| DB | `hilo_dev_p02s07` (fresh, scoped, same Rancher postgres) — alembic head=0002 |
| Redis | shared `127.0.0.1:6379/2` |
| MCP mock | `127.0.0.1:8080` JSON-RPC 2.0 server (this dir / `mcp_mock_server.py`) |
| ENABLE_VERBOSE_LOGGING | `true` for V01–V22; switched to `false` for V23 (gate check) |
| MCP_ALLOWLIST_DOMAINS | `localhost,docs.langchain.com` |
| MCP_DISCOVERY_TIMEOUT_SECONDS | `15` |

Verification data loaded via `app.verification_data.bootstrap`:
- `--only auth` → 2 rows (incl. `employee.verification@inditex-sandbox.com`)
- `--only admin_ai` → 1 admin row (`admin.peopletech@inditex-sandbox.com`) + 1 provider
- `--only mcp_agents` → 1 server row (deleted after load to start MCP tables empty)

Roles seeded manually (the verification-data loader does **not** seed
`roles`/`user_roles` rows per design D9). `admin.peopletech@…` → `people_admin`;
`employee.verification@…` → `employee`.

## Verification Data Contract rows used (TECHNICAL_GUIDE §6.5)

- **J105 mcp-agents** row → admin user `admin.peopletech@inditex-sandbox.com`
  (real verification credential), `sandbox_readonly` server fixture, plus a
  second real-internet endpoint `https://docs.langchain.com/mcp` registered
  during V07 (allowlisted explicitly for this verify run).
- Real persisted data observed (final state, see `verify-db-final.log`):

  | Table | Final count |
  |---|---|
  | `mcp_servers` | 3 (sandbox_local_mock active; langchain_docs draft; sandbox_with_key draft) |
  | `mcp_credentials` | 1 (Fernet ciphertext, 120 bytes, plaintext_match = `f`) |
  | `mcp_tools` | 1 (`echo`, server_id=sandbox_local_mock) |
  | `mcp_resources` | 1 |
  | `mcp_prompts` | 1 |
  | `audit_logs` (admin.ai.mcp.*) | 13 (create×3, sync×3, sync.failed×3, tool.update×4) |

## Curl flow — V01 to V23

| # | URL | Probe | Expected | Observed | Pass |
|---|---|---|---|---|---|
| V01 | `GET /api/v1/admin/ai/mcp/servers` no token | reject anon | 401 `AUTH_SESSION_EXPIRED` | 401 | ✅ |
| V02 | `GET /api/v1/admin/ai/mcp/servers` with employee bearer | RBAC | 403 `AUTH_PERMISSION_DENIED` | 403 | ✅ |
| V03 | `GET /api/v1/admin/ai/mcp/servers` with admin bearer | happy empty | 200 + `data:[]` | 200 + `data:[]` | ✅ |
| V04 | `POST /api/v1/admin/ai/mcp/servers` transport=`stdio` | reject stdio | 422 Pydantic Literal | 422 (`Input should be 'http' or 'sse'`) | ✅ |
| V05 | `POST` endpoint=`https://evil.example.com/mcp` | allowlist | 400 `MCP_ENDPOINT_NOT_ALLOWED` | 400 (`Allowed: ['docs.langchain.com','localhost']`) | ✅ |
| V06 | `POST` sandbox_local_mock (http, auth=none) | core create | 201 + draft + envelope | 201 + status=draft | ✅ |
| V07 | `POST` langchain_docs (https, auth=none) | real domain | 201 + draft | 201 + draft (host `docs.langchain.com` in allowlist) | ✅ |
| V08 | `GET` admin → 2 servers | no leak | no `encrypted_secret` in body | 0 occurrences of `encrypted_secret` | ✅ |
| V09 | `POST` missing `name` | Pydantic | 422 | 422 | ✅ |
| V10 | `POST {LOCAL_ID}/sync` REAL handshake vs mock | core sync | 200 + `tools_count=1 resources_count=1 prompts_count=1 status=active`; DB tool with `enabled=false requires_approval=true risk_level=medium` | exactly that — see logs and DB | ✅ |
| V11 | `GET` after sync | status flip | `sandbox_local_mock.status=active`, `last_sync_at` set | 2026-05-13T11:42:40.929860Z | ✅ |
| V12 | `POST /servers/{UUID-null}/sync` | not found | 404 `MCP_SERVER_NOT_FOUND` | 404 | ✅ |
| V13 | `POST {LC_ID}/sync` REAL `docs.langchain.com` | unreachable transport mismatch | 502 `MCP_SERVER_UNREACHABLE`; 2nd call within minute → 429 `RATE_LIMITED` | 502 in 77ms, 429 with `Retry-After: 59` | ✅ |
| V14 | `PATCH {TOOL_ID}` `{enabled:true, risk_level:low}` | core patch + audit | 200 + persisted | 200; DB enabled=t risk_level=low | ✅ |
| V15 | `PATCH {TOOL_ID}` `risk_level=invalid` | enum guard | 422 | 422 | ✅ |
| V16 | `PATCH /tools/{UUID-null}` | not found | 404 `MCP_TOOL_NOT_FOUND` | 404 | ✅ |
| V17 | `PATCH {TOOL_ID}` `{}` empty body | KISS guard | 400 `MCP_TOOL_PAYLOAD_INVALID` | 400 | ✅ |
| V18 | `PATCH {TOOL_ID}` `risk_level=critical` | enum coverage | 200 | 200 | ✅ |
| V19 | Re-sync `{LOCAL_ID}` after V14 | D-SYNC1 idempotence | tools_count=1; preserve `enabled=true risk_level=critical` (curated admin fields) | preserved (DB row unchanged on curated columns; description/schemas refreshed from server) | ✅ |
| V20 | `POST` sandbox_with_key, `auth.type=api_key secret=sk-verify-only-secret-12345` | Fernet roundtrip | DB `encrypted_secret` ≠ plaintext, length≈120 | length=120, plaintext_match=`f` | ✅ |
| V21 | Audit invariant scan over `admin.ai.mcp.%` rows | no PII | 0 rows match `sk-verify-only-secret\|VerifyPass\|AdminVerify2024\|encrypted_secret` | 0 | ✅ |
| V22 | Re-sync `{LC_ID}` after RL window | real internet | 502 `MCP_SERVER_UNREACHABLE` (docs.langchain.com does not speak http-JSON-RPC) | 502 in 80ms | ✅ |
| V23 | Backend restart with `ENABLE_VERBOSE_LOGGING=false`, hit `GET /servers` + `PATCH /tools/{id}` | log gating | 0 `app.mcp.*DEBUG` lines | 0 lines (`grep -c 'app.mcp.*DEBUG' verify-back-quiet.log` = 0) | ✅ |

Notes:
- The 422 envelope for Pydantic `body` errors (V04, V09, V15) returns FastAPI's
  default `{detail: [...]}` — this is **by design** for admin/ai routes per
  P02-S05-T001 precedent (the `/api/v1/admin/ai/*` family is **not** in
  `_AUTH_INVALID_PAYLOAD_PATHS`). Documented in handoff §"422 vs 400 mapping".
- V13's 502 against `docs.langchain.com/mcp` is the expected/spec behaviour
  of our hand-rolled HTTP JSON-RPC client when the target speaks SSE or a
  different shape. The slice's contract is "happy path returns 200; transport
  error returns 502 + audit failure" — both branches verified live.
- V22 plus V19 together exercise the CRITICAL-2 fix (initialize handshake)
  end-to-end against a real local mock and confirm the per-server status
  transition `draft → active`.

## Live log observations

`orchestrator-state/tasks/evidence/P02-S07-T001/verify-back.log` (verbose=true):

- **Handshake sequence captured** (CRITICAL-2 fix):
  ```
  mcp.client.discover.start auth_type=none timeout=15s
  mcp.client.initialize.start protocol_version=2025-06-18
  mcp.client.initialize.ok    protocol_version=2025-06-18
  mcp.client.json_rpc.start   method=tools/list
  mcp.client.json_rpc.ok      method=tools/list
  mcp.client.json_rpc.start   method=resources/list
  mcp.client.json_rpc.ok      method=resources/list
  mcp.client.json_rpc.start   method=prompts/list
  mcp.client.json_rpc.ok      method=prompts/list
  mcp.client.discover.ok      tools=1 resources=1 prompts=1
  ```
- BEFORE/AFTER pattern present on every router/service/repository function.
- `request_id` propagated to every log line (verified for 6 sample
  request_ids across V03/V06/V10/V14/V20/V22).
- 0 lines contain `sk-verify-only-secret`, `VerifyPass2024`, `AdminVerify2024`
  or `encrypted_secret`.

`mcp-mock` log mirror confirms the wire order from the server side:
`initialize → notifications/initialized (202) → tools/list → resources/list → prompts/list`.

## Bookkeeping artefacts found / not found

- The official-docs note `orchestrator-state/memory/official-doc-notes/P02-S07-T001-mcp-sdk-2026-05-13.md`
  carries a complete `## RESOLVED` block at the bottom (cycle-1 debugger fix).
  Re-checked in this verify: header line 2 = `Status: RESOLVED 2026-05-13`.
  Hook `hook_docs_discrepancy_check.py` is no longer flagging this note.
- The follow-up YAML `FU-20260513112253-replace-technical-guide-md-line-60-sdk-mcp-pytho.yaml`
  declared by the debugger as a NEW deliverable is **not on disk** (validator
  re-review confirmed this — minor non-blocking finding). I am leaving this
  alone and surfacing it for the closer / main-orchestrator to register
  cleanly with `register-followup-task.sh propose` (severity=low,
  scope_classification=missing_coverage). See validator re-review §"Minor
  finding" for the exact CLI invocation. **This is not blocking closer**.

## Screen/Journey review applicability

- TASK kind: `api`
- `Pantalla/Ruta`: `— (api-only)` per Coverage Registry
- `Journey refs`: `J105` (slice participates but does not close — see below)
- No `VISUAL_CONTRACT_CHECK` anywhere in acceptance/handoff/evidence
- Human verification reproduced only curl flows + log inspection + DB asserts;
  no screen / navigation / UX state to review

⇒ `screen_journey_review: not_applicable` — the visual experience tied to
J105 (McpServersPage, McpWizardPage, AgentsPage) is the responsibility of
P04-S02-T003/T004/T005, which will trigger `screen-journey-reviewer` when
they close.

## Journey closure detection

`python3 -B -S .claude/bin/list_journey_closures.py P02-S07-T001 --json`:

- `closing_journeys: []`
- J105 needs `P02-S08-T001, P04-S02-T003/T004/T005, P05-S01-T006` to close.
- Closer must **not** emit `JOURNEY_PENDING_VERIFY: J105` (the journey is
  still in progress, not awaiting verification).
- §5.bis (journey-closing inline gate) is **N/A** for this slice.

## Decision

**VERIFY_OUTCOME: verified**. All 11 acceptance criteria from the task pack
are met on a real running backend against real (mock + internet) MCP
endpoints, with real Fernet encryption against a real Postgres, with real
audit rows, real request_id propagation, and real verbose-mode gating.
No findings that require `debugger` cycle 2. Ready for `closer`.
