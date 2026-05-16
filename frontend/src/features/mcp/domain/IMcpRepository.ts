/**
 * Hilo People — MCP domain repository port (interface).
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Port (interface) for the MCP data layer.
 *   Defines what operations the domain needs; the data layer implements them.
 *   No imports of external libs, no React, no fetch calls here.
 *
 * §D-T003-DOMAIN-PORT (P04-S02-T003 task pack §5)
 *
 * Clean Architecture: presentation/ depends on this port, NOT on mcpRepository.ts
 *   directly. This decouples the UI from fetch implementation details.
 */

import type { Result, McpServer, McpSyncResult } from "./types";
import type { McpError } from "../data/errors";

/**
 * Repository port for MCP server operations.
 *
 * Both methods return Result<T, McpError> — never throw to the presentation layer.
 */
export interface IMcpRepository {
  /**
   * Fetch the list of MCP servers for the admin panel.
   *
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   * @returns Result with the server list or a typed McpError.
   */
  listServers(onAuthFailure: () => void): Promise<Result<McpServer[], McpError>>;

  /**
   * Trigger a sync for a specific MCP server.
   *
   * @param id - UUID of the MCP server to sync.
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   * @returns Result with sync details (tools_count, resources_count, prompts_count, status)
   *   or a typed McpError.
   */
  syncServer(id: string, onAuthFailure: () => void): Promise<Result<McpSyncResult, McpError>>;
}
