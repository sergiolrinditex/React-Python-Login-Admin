/**
 * Hilo People — In-memory access token store.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Single source of truth for the current access token in memory.
 *   Implements the token-in-memory contract from TECHNICAL_GUIDE §10.2:
 *   "El access token vive solo en memoria del cliente (variable de runtime del cliente,
 *   nunca persistido). NUNCA access ni refresh en localStorage ni sessionStorage."
 *
 * Security guardrails (task pack §P):
 *   1. NEVER write to localStorage, sessionStorage, or IndexedDB.
 *   2. NEVER log the token value — log len=<n> or present=true only.
 *   3. Token is lost on page reload — intentional. AuthProvider calls /refresh on mount.
 *
 * Pattern: module-level variable behind closure (not a class).
 *   Exported functions are the only interface — no direct access to _token.
 *
 * Test note: T01 verifies that localStorage is NEVER touched.
 */

import { logVerbose } from "./logger";

// ---------------------------------------------------------------------------
// Module-level in-memory store (closure pattern)
// ---------------------------------------------------------------------------

let _token: string | null = null;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Returns the current access token, or null if no token is stored.
 * NEVER expose in logs — callers must log presence only.
 *
 * @returns The current access token string, or null.
 */
export function getAccessToken(): string | null {
  return _token;
}

/**
 * Stores a new access token in memory.
 * Logs BEFORE (with presence flag only) and AFTER (len only, never value).
 *
 * @param token - The new access token string.
 */
export function setAccessToken(token: string): void {
  logVerbose("auth.store.set.start", {
    was_present: _token !== null,
    new_len: token.length,
  });
  _token = token;
  logVerbose("auth.store.set.ok", { len: token.length });
}

/**
 * Clears the in-memory access token (logout / session expiry).
 * Logs BEFORE and AFTER the clear operation.
 * Safe to call when token is already null.
 */
export function clearAccessToken(): void {
  logVerbose("auth.store.clear.start", { was_present: _token !== null });
  _token = null;
  logVerbose("auth.store.clear.ok");
}

/**
 * Returns true when an access token is currently stored.
 * Use this for logging presence checks — never log the token itself.
 */
export function hasAccessToken(): boolean {
  return _token !== null;
}
