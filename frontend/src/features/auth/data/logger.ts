/**
 * Hilo People — Auth feature verbose logger.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Centralised logging helper for the auth feature.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.debug/info/warn/error all fire.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * Security rules (P §3, §4 security guardrails):
 *   - NEVER log token values (access or refresh). Log len=<n> or present=true only.
 *   - NEVER log passwords, cookies, secrets, or PII (full email).
 *   - NEVER log user.email — log user.id (UUID) only.
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
 * @param event - Dot-namespaced event key (e.g. "auth.provider.hydrate.start").
 * @param meta - Optional structured metadata (no tokens, no PII).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[auth] ${event}`, meta);
    } else {
      console.info(`[auth] ${event}`);
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
    console.warn(`[auth] ${event}`, meta);
  } else {
    console.warn(`[auth] ${event}`);
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
    console.error(`[auth] ${event}`, meta);
  } else {
    console.error(`[auth] ${event}`);
  }
}
