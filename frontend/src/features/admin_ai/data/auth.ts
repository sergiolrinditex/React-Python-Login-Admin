/**
 * Admin auth header helper — P00 stub.
 *
 * What: Returns the Authorization header for admin-only API calls.
 *       In Phase 0 the backend stub accepts any `Bearer dev-admin-<suffix>`.
 *       This helper isolates the hardcoded literal to one location so the
 *       real-auth phase grep-finds it immediately.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   none — pure utility, no imports.
 *
 * Source-of-truth refs:
 *   - instrucciones.md §7 (P00 stub auth)
 *   - TECHNICAL_GUIDE §6.1 (admin route auth = "Sí admin")
 *   - task-pack P00-S02-T007.md §3.4
 *
 * Security note:
 *   The literal 'dev-admin-localhost' is intentional for the P00 stub.
 *   It matches the backend require_admin guard (prefix dev-admin-*).
 *   It is NOT a production secret. Replace entirely in P01-S03-T001.
 */

/**
 * Returns the Authorization header for admin API requests.
 *
 * P00 stub — accepts any Bearer dev-admin-* prefix.
 * Replaced in P01-S03-T001 with the real auth-store accessor.
 *
 * @returns Object with Authorization header value.
 *
 * TODO(P01-S03-T001): replace with auth-store accessor.
 *   grep: getAdminAuthHeader
 */
export function getAdminAuthHeader(): { Authorization: string } {
  // P00 stub. Replaced in P01-S03-T001 with a real auth-store accessor.
  return { Authorization: 'Bearer dev-admin-localhost' };
}
