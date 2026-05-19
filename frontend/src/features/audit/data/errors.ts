/**
 * Hilo People — Audit feature data layer errors.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Typed error classes for audit log operations.
 *   auditRepository.ts returns these via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error.
 *
 * Mirrors the pattern from features/admin/data/errors.ts (UsagePage sibling).
 * Error mapping: D-T001-ERROR-MAPPING in task pack §7.
 *
 * §D-T001-DATA: Canonical write_set anchor for this file.
 * Source ref: §D-T001-DATA, task pack §7 Front→Back→DB contract.
 */

// ---------------------------------------------------------------------------
// Audit error classes
// ---------------------------------------------------------------------------

/**
 * Validation error — 422 from server OR client-side filter validation failed.
 * Covers: AUDIT_WINDOW_INVALID (from >= to), AUDIT_WINDOW_TOO_WIDE (>90 days),
 * invalid actor UUID format.
 */
export class AuditValidationError extends Error {
  public readonly code = "AUDIT_VALIDATION_ERROR" as const;
  /** Optional localization subkey for specific validation messages. */
  public readonly subCode?: "range" | "window" | "actor";

  constructor(message = "Invalid audit query parameters.", subCode?: "range" | "window" | "actor") {
    super(message);
    this.name = "AuditValidationError";
    this.subCode = subCode;
  }
}

/**
 * Forbidden error — server returned 403 (non-auditor role).
 * Renders the permission_denied UX state in AuditLogPage.
 * Note: with RequireRole guard in router.tsx this is typically unreachable
 * from the page itself; handled defensively for mid-session role loss.
 */
export class AuditForbiddenError extends Error {
  public readonly code = "AUDIT_FORBIDDEN" as const;

  constructor(message = "You do not have permission to view audit logs.") {
    super(message);
    this.name = "AuditForbiddenError";
  }
}

/**
 * Auth expired — server returned 401 after refresh exhausted.
 * authFetch single-flight handles this; surfaces here when recovery fails.
 * In practice, RequireAuth redirects the user before this is shown.
 */
export class AuditAuthExpiredError extends Error {
  public readonly code = "AUDIT_AUTH_EXPIRED" as const;

  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "AuditAuthExpiredError";
  }
}

/**
 * Network error — fetch rejected (offline, CORS, DNS failure, abort).
 * Does NOT indicate an auth failure — may be a transient connectivity issue.
 */
export class AuditNetworkError extends Error {
  public readonly code = "AUDIT_NETWORK_ERROR" as const;

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "AuditNetworkError";
  }
}

/**
 * Server error — 5xx response.
 * Renders the error_network UX state with retry CTA.
 */
export class AuditServerError extends Error {
  public readonly code = "AUDIT_SERVER_ERROR" as const;
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "AuditServerError";
    this.status = status;
  }
}

/** Union of all typed audit errors. */
export type AuditError =
  | AuditValidationError
  | AuditForbiddenError
  | AuditAuthExpiredError
  | AuditNetworkError
  | AuditServerError;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch/domain error to a typed AuditError.
 *
 * @param err - Raw caught value from a try/catch block.
 * @returns A typed domain error.
 */
export function mapAuditError(err: unknown): AuditError {
  if (err instanceof AuditValidationError) return err;
  if (err instanceof AuditForbiddenError) return err;
  if (err instanceof AuditAuthExpiredError) return err;
  if (err instanceof AuditNetworkError) return err;
  if (err instanceof AuditServerError) return err;
  if (err instanceof TypeError) {
    return new AuditNetworkError(err.message, err);
  }
  if (err instanceof Error) return new AuditNetworkError(err.message, err);
  return new AuditNetworkError("Unknown error");
}
