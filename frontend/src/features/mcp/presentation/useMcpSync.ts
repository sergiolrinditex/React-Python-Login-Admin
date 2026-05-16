/**
 * Hilo People — useMcpSync hook.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: TanStack Query v5 useMutation wrapper for POST /servers/{id}/sync.
 *   Invalidates the servers list on success to refresh last_sync_at and status.
 *   Returns the shared mutation instance used for all per-row sync actions.
 *
 * §D-T003-PRES-USE-SYNC (P04-S02-T003 task pack §5)
 * §D-T003-PER-ROW-SYNCING: shared mutation + per-row pending state via mutationKey filtering.
 * §D-T003-INVALIDATE-ON-SUCCESS: invalidates ['admin','mcp','servers'] on success.
 *
 * Clean Architecture: presentation/ layer — depends on data/mcpRepository.
 *   McpServersPage depends on this hook; no direct repository imports in the page.
 *
 * R-7 mitigation: use shared useMutation instance rather than one per row.
 *   Per-row pending state is derived from useMutationState with mutationKey filter.
 *   The page calls mutate({ id: server.id }) with the correct mutationKey per call.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logVerbose/logWarn.
 *
 * Key deps: @tanstack/react-query v5 (useMutation, useQueryClient), mcpRepository.syncServer.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { McpSyncResult } from "../domain/types";
import type { McpError } from "../data/errors";
import { syncServer } from "../data/mcpRepository";
import { logVerbose, logWarn } from "../data/logger";
import { MCP_SERVERS_QUERY_KEY } from "./useMcpServers";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SyncMutationVariables {
  /** UUID of the server to sync. */
  id: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Base mutation key prefix for MCP sync operations. */
export const MCP_SYNC_MUTATION_KEY = ["mcp", "sync"] as const;

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/**
 * Shared mutation hook for syncing MCP servers.
 *
 * Usage in the page:
 *   const { mutate, isPending } = useMcpSync(onAuthFailure);
 *   // Per-row: mutate({ id: server.id }, { mutationKey: [...MCP_SYNC_MUTATION_KEY, server.id] })
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns TanStack useMutation result.
 */
export function useMcpSync(onAuthFailure: () => void) {
  const queryClient = useQueryClient();

  return useMutation<McpSyncResult, McpError, SyncMutationVariables>({
    mutationKey: MCP_SYNC_MUTATION_KEY,
    mutationFn: async ({ id }: SyncMutationVariables) => {
      logVerbose("mcp.useMcpSync.mutate.start", { server_id: id });

      const result = await syncServer(id, onAuthFailure);

      if (!result.ok) {
        logWarn("mcp.useMcpSync.mutate.error", {
          server_id: id,
          code: result.error.code,
        });
        throw result.error;
      }

      logVerbose("mcp.useMcpSync.mutate.success", {
        server_id: id,
        tools_count: result.value.tools_count,
        status: result.value.status,
      });

      return result.value;
    },
    onSuccess: () => {
      // §D-T003-INVALIDATE-ON-SUCCESS: refresh server list so last_sync_at updates
      void queryClient.invalidateQueries({ queryKey: MCP_SERVERS_QUERY_KEY });
    },
  });
}
