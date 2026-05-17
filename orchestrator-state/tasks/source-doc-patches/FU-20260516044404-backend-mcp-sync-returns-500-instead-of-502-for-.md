# Source-of-truth amendment — FU-20260516044404-backend-mcp-sync-returns-500-instead-of-502-for-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S02-T006 | bug | Backend MCP sync returns 500 instead of 502 for unreachable MCP server | Runtime follow-up P04-S02-T003 | current | planned | medium | human | P04-S02-T003 | front:mcp | backend/app/api/admin/ai/mcp/**, backend/tests/api/admin/ai/mcp/** | J105 | /admin/ai/mcp | POST /api/v1/admin/ai/mcp/servers/{id}/sync | mcp_servers | runtime-followup#FU-20260516044404-backend-mcp-sync-returns-500-instead-of-502-for- | runtime-followup#FU-20260516044404-backend-mcp-sync-returns-500-instead-of-502-for- | POST /api/v1/admin/ai/mcp/servers/{id}/sync against an unreachable MCP endpoint returns HTTP 502 with envelope {data:null, meta:{request_id}, errors:[{code:MCP_SERVER_UNREACHABLE, message:..., field:null, details:null}]}, existing 200 success path unaffected, existing 401/403/404 mappings unaffected. | /verify-slice P04-S02-T003 sandbox row → click Sync → observe HTTP 502 + code=MCP_SERVER_UNREACHABLE in network panel, frontend renders errors:MCP_SERVER_UNREACHABLE inline (already wired since this slice). Backend integration test covers 502 path with a stub MCP server that closes the connection. |
```
