/**
 * Hilo People — Admin feature verbose logger.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Centralised logging helper for the admin feature.
 *   Mirrors the exact pattern from features/chat/data/logger.ts.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.info fires for all events.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * Security rules (non-negotiables §logging):
 *   - NEVER log token values (access or refresh).
 *   - NEVER log user.email, full_name, or any PII.
 *   - NEVER log estimated_cost of individual rows (aggregate totals only).
 *   - Safe to log: from, to, group_by, row_count, request_id.
 *
 * D-T002-DATA-LOGGER: Canonical write_set anchor for this file.
 * Source ref: §D-T002-DATA-LOGGER, non-negotiables §logging.
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
 * @param event - Dot-namespaced event key (e.g. "usage.repo.fetch.before").
 * @param meta - Optional structured metadata (no PII, no tokens, no cost details).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[admin] ${event}`, meta);
    } else {
      console.info(`[admin] ${event}`);
    }
  }
}

/**
 * Log a warning event — always visible regardless of verbose flag.
 *
 * @param event - Dot-namespaced event key.
 * @param meta - Optional structured metadata (no PII, no tokens).
 */
export function logWarn(event: string, meta?: Record<string, unknown>): void {
  if (meta !== undefined) {
    console.warn(`[admin] ${event}`, meta);
  } else {
    console.warn(`[admin] ${event}`);
  }
}

/**
 * Log an error event — always visible regardless of verbose flag.
 *
 * @param event - Dot-namespaced event key.
 * @param meta - Optional structured metadata (no PII, no tokens).
 */
export function logError(event: string, meta?: Record<string, unknown>): void {
  if (meta !== undefined) {
    console.error(`[admin] ${event}`, meta);
  } else {
    console.error(`[admin] ${event}`);
  }
}
