/**
 * Hilo People — Audit feature domain types.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Pure domain types for the audit log feature.
 *   No external imports — domain layer is framework-agnostic.
 *   Types mirror the backend response shape from:
 *     - backend/app/admin/audit/schemas.py (AuditLogOut)
 *     - backend/app/admin/audit/router.py (response envelope)
 *
 * Backend canonical response shape (GET /api/v1/admin/audit):
 *   { data: AuditLog[], meta: { request_id, next_cursor, has_more, count }, errors: [] }
 *
 * Coupling note: AUDIT_MAX_WINDOW_DAYS mirrors backend service._MAX_WINDOW_DAYS = 90.
 *   If the backend cap changes, both must be updated together.
 *   See R6 in task pack P04-S03-T001.
 *
 * §D-T001-DOMAIN: Canonical write_set anchor for this file.
 * Source ref: §D-T001-DOMAIN, TECHNICAL_GUIDE §6.1#/admin/audit, §10.3 DB schema.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Maximum audit query window in days (mirrors backend _MAX_WINDOW_DAYS = 90).
 * Client enforces this to avoid avoidable 422 round-trips.
 * R6: must stay in sync with backend; document any change here.
 */
export const AUDIT_MAX_WINDOW_DAYS = 90;

/**
 * Default query window in days (last 7 days by default).
 * Matches the typical audit review workflow for a people auditor.
 */
export const AUDIT_DEFAULT_WINDOW_DAYS = 7;

/**
 * Known audit action strings observed in the backend codebase.
 * Used to populate the <datalist> for the action filter.
 * Server does exact-match; unknown actions pass through as free-text.
 * D-T001-ACTION-FILTER: free-text + datalist (never a fixed select).
 */
export const AUDIT_KNOWN_ACTIONS: readonly string[] = [
  "auth.sign_up",
  "auth.sign_in",
  "auth.mfa.verify",
  "auth.logout",
  "auth.refresh",
  "auth.password_reset.requested",
  "auth.password_reset.completed",
  "users.language.update",
  "admin.agent.tools.update",
  "admin.agent.run.start",
  "admin.agent.run.complete",
] as const;

// ---------------------------------------------------------------------------
// Query input types
// ---------------------------------------------------------------------------

/**
 * Input query parameters for the audit log endpoint.
 * Validated client-side before fetching (D-T001-RANGE-INVARIANT).
 * Backend alias: `from` → from_dt, `to` → to_dt.
 */
export interface AuditQuery {
  /** Window start (inclusive ISO datetime string). REQUIRED by backend. */
  from: Date;
  /** Window end (exclusive ISO datetime string). REQUIRED by backend. */
  to: Date;
  /** Optional actor UUID string filter (exact match on actor_user_id). */
  actor?: string;
  /** Optional action string filter (exact match). */
  action?: string;
  /** Opaque pagination cursor from previous page (keyset on created_at DESC, id DESC). */
  cursor?: string;
  /** Page size (default 50, max 200). */
  limit?: number;
}

// ---------------------------------------------------------------------------
// Response row type
// ---------------------------------------------------------------------------

/**
 * A single audit log row as returned by the backend (AuditLogOut schema).
 *
 * PII contract (D-T001-ACTOR-RENDER, D-T001-METADATA-RENDER):
 *   - actor_user_id is a UUID, NOT an email. Render as 8-char truncation.
 *   - metadata may contain IPs/user-agents. Render only request_id in v1.
 *
 * Refs: backend/app/admin/audit/schemas.py::AuditLogOut.
 */
export interface AuditLog {
  /** Row UUID. */
  id: string;
  /**
   * UUID of the actor (user who triggered the action).
   * Null when the user was deleted (GDPR Art. 17 ON DELETE SET NULL).
   */
  actor_user_id: string | null;
  /** Audit action string (e.g. "auth.sign_in", "admin.agent.run.start"). */
  action: string;
  /** Entity type label (e.g. "user", "conversation"). Null when not applicable. */
  entity_type: string | null;
  /** Entity UUID. Null when not applicable. */
  entity_id: string | null;
  /**
   * Raw JSONB metadata blob from the backend.
   * May contain ip, user_agent, request_id, action-specific context.
   * DO NOT render the full blob in v1 (D-T001-METADATA-RENDER).
   */
  metadata: Record<string, unknown>;
  /** ISO 8601 timestamp when the event was recorded. */
  created_at: string;
}

// ---------------------------------------------------------------------------
// Response page type
// ---------------------------------------------------------------------------

/**
 * Backend response envelope for GET /api/v1/admin/audit.
 * Wraps an array of audit rows with cursor-based pagination metadata.
 */
export interface AuditPage {
  /** Audit log rows for this page (may be empty). */
  rows: AuditLog[];
  /** Opaque cursor for the next page (null when no more pages). */
  next_cursor: string | null;
  /** True when more pages are available. */
  has_more: boolean;
  /** Total count of rows returned on this page. */
  count: number;
}
