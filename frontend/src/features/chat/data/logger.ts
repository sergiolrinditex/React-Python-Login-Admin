/**
 * Hilo People — Chat feature verbose logger.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *
 * Responsibility: Centralised logging helper for the chat feature.
 *   Mirrors the exact pattern from features/auth/data/logger.ts.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.debug/info/warn/error all fire.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * Security rules:
 *   - NEVER log prompt text content or message body.
 *   - NEVER log access tokens or any bearer value.
 *   - NEVER log user.email or full_name. Log user.id (UUID) only.
 *   - Log prompt length (safe) — NOT prompt content.
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
 * @param event - Dot-namespaced event key (e.g. "chat.home.create_conversation.start").
 * @param meta - Optional structured metadata (no tokens, no PII, no prompt content).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[chat] ${event}`, meta);
    } else {
      console.info(`[chat] ${event}`);
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
    console.warn(`[chat] ${event}`, meta);
  } else {
    console.warn(`[chat] ${event}`);
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
    console.error(`[chat] ${event}`, meta);
  } else {
    console.error(`[chat] ${event}`);
  }
}
