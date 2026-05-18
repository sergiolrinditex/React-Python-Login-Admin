/**
 * Hilo People — Agents feature verbose logger.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Centralised logging helper for the agents feature.
 *   Mirrors features/mcp/data/logger.ts exactly.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.debug/info/warn/error all fire.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * §D-T005-LOGGER (P04-S02-T005 task pack §8.1)
 *
 * Security rules (§D-T005-LOGS-PII-CLEAN):
 *   - NEVER log tool_id values (only counts).
 *   - NEVER log agent.name or agent.description.
 *   - NEVER log run input text.
 *   - NEVER log access tokens or auth secrets.
 *   - Log agent_id (UUID), tool_count, request_id, status only.
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
 * @param event - Dot-namespaced event key (e.g. "agents.repo.listAgents.start").
 * @param meta - Optional structured metadata (no tokens, no PII, no tool_id values).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[agents] ${event}`, meta);
    } else {
      console.info(`[agents] ${event}`);
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
    console.warn(`[agents] ${event}`, meta);
  } else {
    console.warn(`[agents] ${event}`);
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
    console.error(`[agents] ${event}`, meta);
  } else {
    console.error(`[agents] ${event}`);
  }
}
