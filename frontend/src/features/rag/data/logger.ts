/**
 * Hilo People — RAG feature verbose logger.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Centralised logging helper for the RAG feature.
 *   Mirrors the exact pattern from features/chat/data/logger.ts.
 *   Logs are gated by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   When verbose=true: console.info/warn/error all fire.
 *   When verbose=false: only console.warn/console.error fire.
 *
 * Security rules (non-negotiables §Security):
 *   - NEVER log filename, file content, or title content.
 *   - NEVER log access tokens or bearer values.
 *   - NEVER log user.email or user PII.
 *   - Safe to log: mime_type, size_bytes_bucketed, sha256_prefix (first 8 chars),
 *     document.id (UUID), request_id, language code, status, collection_id.
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
 * @param event - Dot-namespaced event key (e.g. "rag.repo.listDocuments.start").
 * @param meta - Optional structured metadata (no PII, no file content, no tokens).
 */
export function logVerbose(event: string, meta?: Record<string, unknown>): void {
  if (isVerbose()) {
    if (meta !== undefined) {
      console.info(`[rag] ${event}`, meta);
    } else {
      console.info(`[rag] ${event}`);
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
    console.warn(`[rag] ${event}`, meta);
  } else {
    console.warn(`[rag] ${event}`);
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
    console.error(`[rag] ${event}`, meta);
  } else {
    console.error(`[rag] ${event}`);
  }
}
