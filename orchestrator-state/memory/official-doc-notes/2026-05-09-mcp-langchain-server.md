# LangChain MCP Server Status — Verification Note (P00-S02-T005)

**Date**: 2026-05-09
**Task**: P00-S02-T005
**Severity**: LOW (server is UP and functional as MCP endpoint)
**Sources**:
- WebFetch `https://docs.langchain.com/mcp` — responded with MCP server configuration JSON
- Context7 /websites/langchain_oss_python_deepagents — deepagents docs referencing LangChain MCP

---

## Finding

### `https://docs.langchain.com/mcp` STATUS: ACTIVE MCP SERVER

**Task pack says**: MCP server `docs-langchain` with URL `https://docs.langchain.com/mcp` —
active, for LangChain documentation queries.

**Verification result**: The URL `https://docs.langchain.com/mcp` responded with a valid MCP
server configuration document (not a 404, not an HTML page). The response describes:

- **Server name**: "Docs by LangChain"
- **Tools exposed**:
  1. `search_docs_by_lang_chain` — searches the LangChain documentation knowledge base
  2. `query_docs_filesystem_docs_by_lang_chain` — runs read-only filesystem queries
     (`cat`, `head`, `rg`, `tree`) against a virtualized in-memory LangChain docs filesystem

- **Architecture**: The MCP server exposes LangChain documentation via a sandboxed virtual
  filesystem. It is a public, read-only documentation server — no auth token required for
  basic queries.

**Verdict**: The server IS LIVE and IS a valid MCP endpoint. The task pack's `docs-langchain`
entry with `https://docs.langchain.com/mcp` is CORRECT.

---

## Implication for T005 JSON

- `data/verification/mcp_agents/servers.json` entry for `docs-langchain` with
  `access_token: null` (public server) is CORRECT.
- The `access_token_env` field can be `null` for this server — it requires no authentication.
- McpServerSeed validator logic: "productive → one of the two required (None permitted if
  server is public)" — confirmed: `docs-langchain` qualifies as "public server, no auth".

---

## No fallback needed

The server is live. No alternative MCP server needs to be proposed.

RESOLVED: n/a — no discrepancy. Server confirmed active.
