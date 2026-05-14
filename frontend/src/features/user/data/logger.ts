/**
 * Hilo People — User feature verbose logger.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Centralised logging helper for the user feature.
 *   Mirrors the exact pattern from features/chat/data/logger.ts and
 *   features/auth/data/logger.ts.
 *   Logs gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *
 * Security rules:
 *   - NEVER log email, full_name, or any PII.
 *   - NEVER log access tokens or bearer values.
 *   - Log user.id (UUID) only when needed for traceability.
 *   - Language code IS safe to log (not PII).
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
 * Log a debug/info event — visible only when VITE_ENABLE_VERBOSE_LOGGING=true.
 *
 * @param event - Dot-namespaced event key (e.g. "user.repo.getMe.start").
 * @param meta - Optional structured metadata (no PII, no tokens).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[user] ${event}`, meta);
    } else {
      console.info(`[user] ${event}`);
    }
  }
}

/**
 * Log a warning event — always visible regardless of verbose flag.
 *
 * @param event - Dot-namespaced event key.
 * @param meta - Optional structured metadata (no PII).
 */
export function logWarn(event: string, meta?: Record<string, unknown>): void {
  if (meta !== undefined) {
    console.warn(`[user] ${event}`, meta);
  } else {
    console.warn(`[user] ${event}`);
  }
}

/**
 * Log an error event — always visible regardless of verbose flag.
 *
 * @param event - Dot-namespaced event key.
 * @param meta - Optional structured metadata (no PII).
 */
export function logError(event: string, meta?: Record<string, unknown>): void {
  if (meta !== undefined) {
    console.error(`[user] ${event}`, meta);
  } else {
    console.error(`[user] ${event}`);
  }
}
