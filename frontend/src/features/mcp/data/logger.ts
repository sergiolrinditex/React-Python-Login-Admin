/**
 * Hilo People — MCP feature verbose logger.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Centralised logging helper for the MCP feature.
 *   Mirrors features/chat/data/logger.ts and features/auth/data/logger.ts exactly.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.debug/info/warn/error all fire.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * §D-T003-DATA-LOGGER (P04-S02-T003 task pack §5)
 *
 * Security rules:
 *   - NEVER log server endpoint URLs with credentials.
 *   - NEVER log access tokens or auth_type secrets.
 *   - NEVER log user.email or full_name.
 *   - Log server_id (UUID) and request_id only — not server names or endpoints.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public operation.
 */

// ---------------------------------------------------------------------------
// Verbose flag
// ---------------------------------------------------------------------------

/**
 * Returns true when verbose logging is enabled.
 * Evaluated at call time (not cached) so tests can override env vars.
 */
function isVerbose(): boolean {
  return import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true";
}

// ---------------------------------------------------------------------------
// Public logging interface
// ---------------------------------------------------------------------------

/**
 * Log a debug/info event — only visible when VITE_ENABLE_VERBOSE_LOGGING=true.
 *
 * @param event - Dot-namespaced event key (e.g. "mcp.repo.listServers.start").
 * @param meta - Optional structured metadata (no tokens, no PII, no endpoint URLs).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[mcp] ${event}`, meta);
    } else {
      console.info(`[mcp] ${event}`);
    }
  }
}

/**
 * Log a warning event — always visible regardless of verbose flag.
 *
 * @param event - Dot-namespaced event key.
 * @param meta - Optional structured metadata (no tokens, no PII).
 */
export function logWarn(event: string, meta?: Record<string, unknown>): void {
  if (meta !== undefined) {
    console.warn(`[mcp] ${event}`, meta);
  } else {
    console.warn(`[mcp] ${event}`);
  }
}

/**
 * Log an error event — always visible regardless of verbose flag.
 *
 * @param event - Dot-namespaced event key.
 * @param meta - Optional structured metadata (no tokens, no PII).
 */
export function logError(event: string, meta?: Record<string, unknown>): void {
  if (meta !== undefined) {
    console.error(`[mcp] ${event}`, meta);
  } else {
    console.error(`[mcp] ${event}`);
  }
}
