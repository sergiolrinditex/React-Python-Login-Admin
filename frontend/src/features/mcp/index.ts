/**
 * Hilo People — MCP feature barrel.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *   Updated: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: Public surface for the mcp feature module.
 *   Mirrors features/auth/index.ts pattern (P-29 #barrel).
 *
 * §D-T003-FEAT-BARREL (P04-S02-T003 task pack §5)
 * §D-T004-FEAT-BARREL (P04-S02-T004 task pack §6) — added wizard types/errors/hook exports.
 *
 * Import from this barrel to keep page imports clean.
 * Do NOT import internal sub-paths from outside the feature.
 */

export type {
  McpServer,
  McpSyncResult,
  McpServerStatus,
  McpTransport,
  McpAuthType,
  McpCreateAuth,
  CreateServerRequest,
} from "./domain/types";
export type { McpError } from "./data/errors";
export {
  McpAuthExpiredError,
  McpForbiddenError,
  McpServerNotFoundError,
  McpServerUnreachableError,
  McpRateLimitedError,
  McpServerError,
  McpNetworkError,
  McpValidationError,
  McpEndpointNotAllowedError,
} from "./data/errors";
export { useMcpServers, MCP_SERVERS_QUERY_KEY } from "./presentation/useMcpServers";
export { useMcpSync, MCP_SYNC_MUTATION_KEY } from "./presentation/useMcpSync";
export { useCreateMcpServer, MCP_CREATE_MUTATION_KEY } from "./presentation/useCreateMcpServer";
