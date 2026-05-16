/**
 * Hilo People — useMcpServers hook.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: TanStack Query v5 useQuery wrapper around mcpRepository.listServers.
 *   Returns the list of MCP servers for the authenticated admin.
 *
 * §D-T003-PRES-USE-SERVERS (P04-S02-T003 task pack §5)
 *
 * Clean Architecture: presentation/ layer — depends on data/mcpRepository.
 *   McpServersPage depends on this hook; no direct repository imports in the page.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logVerbose/logWarn.
 * Logging: PII-clean — no server names, no endpoint URLs, only count.
 *
 * Key deps: @tanstack/react-query v5 (useQuery), mcpRepository.listServers.
 */

import { useQuery } from "@tanstack/react-query";
import type { McpServer } from "../domain/types";
import type { McpError } from "../data/errors";
import { listServers } from "../data/mcpRepository";
import { logVerbose, logWarn } from "../data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const MCP_SERVERS_QUERY_KEY = ["admin", "mcp", "servers"] as const;
const STALE_TIME = 30_000;       // 30 seconds
const GC_TIME = 5 * 60_000;     // 5 minutes

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/**
 * Fetches the list of MCP servers for the admin panel.
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns TanStack useQuery result with McpServer[] as data type.
 */
export function useMcpServers(onAuthFailure: () => void) {
  return useQuery<McpServer[], McpError>({
    queryKey: MCP_SERVERS_QUERY_KEY,
    queryFn: async () => {
      logVerbose("mcp.useMcpServers.fetch.start");

      const result = await listServers(onAuthFailure);

      if (!result.ok) {
        logWarn("mcp.useMcpServers.fetch.error", { code: result.error.code });
        throw result.error;
      }

      logVerbose("mcp.useMcpServers.fetch.success", {
        count: result.value.length,
      });

      return result.value;
    },
    staleTime: STALE_TIME,
    gcTime: GC_TIME,
  });
}
