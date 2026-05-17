/**
 * Hilo People — useCreateMcpServer hook.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: TanStack Query v5 useMutation wrapper for
 *   POST /api/v1/admin/ai/mcp/servers (createServer).
 *   On 201 success: invalidates ['admin','mcp','servers'] query and navigates
 *   to /admin/ai/mcp so the new row appears without manual refresh.
 *
 * §D-T004-PRES-USE-CREATE (P04-S02-T004 task pack §6)
 * §D-T004-INVALIDATE-AND-NAVIGATE (R-8 mitigation):
 *   invalidateQueries + navigate after 201.
 *
 * Clean Architecture: presentation/ layer — depends on data/mcpRepository.createServer.
 *   McpWizardPage depends on this hook; no direct repository imports in the page.
 *
 * Security:
 *   NEVER log secret or refresh_token — only transport and auth_type are logged.
 *   NEVER persist form values in localStorage or sessionStorage.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logVerbose/logWarn/logError.
 *
 * Key deps: @tanstack/react-query v5 (useMutation, useQueryClient), react-router
 *   useNavigate, mcpRepository.createServer.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import type { McpServer, CreateServerRequest } from "../domain/types";
import type { McpError } from "../data/errors";
import { createServer } from "../data/mcpRepository";
import { logVerbose, logWarn, logError } from "../data/logger";
import { MCP_SERVERS_QUERY_KEY } from "./useMcpServers";
import { ROUTE_ADMIN_AI_MCP } from "../../../app/router";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Mutation key prefix for MCP server creation. */
export const MCP_CREATE_MUTATION_KEY = ["mcp", "create"] as const;

/** Delay (ms) before navigating away on success — lets the success state render. */
const SUCCESS_NAVIGATE_DELAY_MS = 600;

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/**
 * Mutation hook for registering a new MCP server.
 *
 * On success (201):
 *   1. Invalidates the ['admin','mcp','servers'] query so McpServersPage refreshes.
 *   2. Navigates to /admin/ai/mcp after SUCCESS_NAVIGATE_DELAY_MS ms.
 *
 * Error handling:
 *   McpValidationError.fieldErrors → page calls form.setError per field.
 *   McpEndpointNotAllowedError → page shows inline error on endpoint field.
 *   McpForbiddenError → page renders permission_denied state.
 *   McpRateLimitedError / McpServerError / McpNetworkError → page renders error_network.
 *
 * §D-T004-PRES-USE-CREATE
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns TanStack useMutation result typed to CreateServerRequest → McpServer.
 */
export function useCreateMcpServer(onAuthFailure: () => void) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation<McpServer, McpError, CreateServerRequest>({
    mutationKey: MCP_CREATE_MUTATION_KEY,
    mutationFn: async (req: CreateServerRequest) => {
      // BEFORE log — transport and auth_type only; secret NEVER logged
      logVerbose("mcp.useCreateMcpServer.mutate.start", {
        transport: req.transport,
        auth_type: req.auth.type,
      });

      const result = await createServer(req, onAuthFailure);

      if (!result.ok) {
        logWarn("mcp.useCreateMcpServer.mutate.error", {
          code: result.error.code,
        });
        throw result.error;
      }

      // AFTER log — id and status only; has_credential is safe to log
      logVerbose("mcp.useCreateMcpServer.mutate.success", {
        server_id: result.value.id,
        status: result.value.status,
        has_credential: result.value.has_credential,
      });

      return result.value;
    },
    onSuccess: (server: McpServer) => {
      // §D-T004-INVALIDATE-AND-NAVIGATE: invalidate list then navigate
      logVerbose("mcp.useCreateMcpServer.onSuccess", {
        server_id: server.id,
      });

      void queryClient.invalidateQueries({ queryKey: MCP_SERVERS_QUERY_KEY });

      // Brief delay so the page can render the success state before navigating
      setTimeout(() => {
        void navigate(ROUTE_ADMIN_AI_MCP);
      }, SUCCESS_NAVIGATE_DELAY_MS);
    },
    onError: (err: McpError) => {
      logError("mcp.useCreateMcpServer.onError", {
        code: err.code,
      });
    },
  });
}
