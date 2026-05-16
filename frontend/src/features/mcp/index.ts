/**
 * Hilo People — MCP feature barrel.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Public surface for the mcp feature module.
 *   Mirrors features/auth/index.ts pattern (P-29 #barrel).
 *
 * §D-T003-FEAT-BARREL (P04-S02-T003 task pack §5)
 *
 * Import from this barrel to keep page imports clean.
 * Do NOT import internal sub-paths from outside the feature.
 */

export type { McpServer, McpSyncResult, McpServerStatus } from "./domain/types";
export type { McpError } from "./data/errors";
export {
  McpAuthExpiredError,
  McpForbiddenError,
  McpServerNotFoundError,
  McpServerUnreachableError,
  McpRateLimitedError,
  McpServerError,
  McpNetworkError,
} from "./data/errors";
export { useMcpServers, MCP_SERVERS_QUERY_KEY } from "./presentation/useMcpServers";
export { useMcpSync, MCP_SYNC_MUTATION_KEY } from "./presentation/useMcpSync";
