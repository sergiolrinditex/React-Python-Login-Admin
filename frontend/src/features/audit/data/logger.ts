/**
 * Hilo People — Audit feature verbose logger.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Centralised logging helper for the audit feature.
 *   Mirrors the exact pattern from features/admin/data/logger.ts.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.info fires for all events.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * Security rules (non-negotiables §logging):
 *   - NEVER log token values (access or refresh).
 *   - NEVER log user email, full_name, or any PII.
 *   - NEVER log full audit rows (they may contain IPs, user-agents, metadata blobs).
 *   - NEVER log actor UUIDs in full; use short hashes when needed.
 *   - Safe to log: has_from, has_to, action_present, actor_present, count, request_id.
 *
 * §D-T001-DATA: Canonical write_set anchor for this file.
 * Source ref: §D-T001-DATA, non-negotiables §logging.
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
 * @param event - Dot-namespaced event key (e.g. "audit.repo.fetch.before").
 * @param meta - Optional structured metadata (no PII, no tokens, no full rows).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[audit] ${event}`, meta);
    } else {
      console.info(`[audit] ${event}`);
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
    console.warn(`[audit] ${event}`, meta);
  } else {
    console.warn(`[audit] ${event}`);
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
    console.error(`[audit] ${event}`, meta);
  } else {
    console.error(`[audit] ${event}`);
  }
}
