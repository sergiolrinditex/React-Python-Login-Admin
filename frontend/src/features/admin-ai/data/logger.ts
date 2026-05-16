/**
 * Hilo People — Admin AI feature verbose logger.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-ADMINAI-FEATURE
 *
 * Responsibility: Centralised logging helper for the admin-ai feature.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.info fires for all levels.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * Security rules (non-negotiables §logging):
 *   - NEVER log token values, passwords, or secrets.
 *   - NEVER log user.email — log user.id (UUID) only.
 *   - NEVER log model_name in error paths (could leak sensitive config).
 *   - Log only: aggregate counts, window dates, error class names, request IDs.
 *
 * Mirrors features/auth/data/logger.ts pattern.
 */

// ---------------------------------------------------------------------------
// Verbose flag
// ---------------------------------------------------------------------------

/**
 * Returns true when verbose logging is enabled.
 * Evaluated at call time so tests can override env vars.
 */
function isVerbose(): boolean {
  return import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true";
}

// ---------------------------------------------------------------------------
// Public logging interface
// ---------------------------------------------------------------------------

/**
 * Log an info event — only visible when VITE_ENABLE_VERBOSE_LOGGING=true.
 *
 * @param event - Dot-namespaced event key (e.g. "admin-ai.repo.getUsage.start").
 * @param meta - Optional structured metadata (no PII, no tokens, no model keys).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[admin-ai] ${event}`, meta);
    } else {
      console.info(`[admin-ai] ${event}`);
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
    console.warn(`[admin-ai] ${event}`, meta);
  } else {
    console.warn(`[admin-ai] ${event}`);
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
    console.error(`[admin-ai] ${event}`, meta);
  } else {
    console.error(`[admin-ai] ${event}`);
  }
}
