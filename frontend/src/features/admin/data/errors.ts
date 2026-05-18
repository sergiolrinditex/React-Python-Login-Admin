/**
 * Hilo People — Admin usage domain errors.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Typed error classes for admin usage operations.
 *   usageRepository.ts returns these via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error.
 *
 * Mirrors the pattern from features/chat/data/errors.ts.
 * Error mapping: D-T002-ERROR-MAPPING in task pack §11.
 *
 * D-T002-DATA-ERRORS: Canonical write_set anchor for this file.
 * Source ref: §D-T002-DATA-ERRORS, task pack §7 Front→Back→DB contract.
 */

// ---------------------------------------------------------------------------
// Usage error classes
// ---------------------------------------------------------------------------

/**
 * Validation error — 422 from server OR client-side range invariant failed.
 * Used when from >= to, or span > 90 days (D-T002-RANGE-INVARIANT).
 */
export class UsageValidationError extends Error {
  public readonly code = "USAGE_VALIDATION_ERROR" as const;

  constructor(message = "Invalid usage query parameters.") {
    super(message);
    this.name = "UsageValidationError";
  }
}

/**
 * Forbidden error — server returned 403 (non-admin role).
 * Renders the permission_denied UX state in UsagePage.
 */
export class UsageForbiddenError extends Error {
  public readonly code = "USAGE_FORBIDDEN" as const;

  constructor(message = "You do not have permission to view usage data.") {
    super(message);
    this.name = "UsageForbiddenError";
  }
}

/**
 * Auth expired — server returned 401 after refresh exhausted.
 * authFetch single-flight handles this; surfaces here when recovery fails.
 * In practice, RequireAuth redirects the user before this is shown.
 */
export class UsageAuthExpiredError extends Error {
  public readonly code = "USAGE_AUTH_EXPIRED" as const;

  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "UsageAuthExpiredError";
  }
}

/**
 * Network error — fetch rejected (offline, CORS, DNS failure, abort).
 * Does NOT indicate an auth failure — may be a transient connectivity issue.
 */
export class UsageNetworkError extends Error {
  public readonly code = "USAGE_NETWORK_ERROR" as const;

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "UsageNetworkError";
  }
}

/**
 * Server error — 5xx response.
 * Renders the error_network UX state with retry CTA.
 */
export class UsageServerError extends Error {
  public readonly code = "USAGE_SERVER_ERROR" as const;
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "UsageServerError";
    this.status = status;
  }
}

/** Union of all typed usage errors. */
export type UsageError =
  | UsageValidationError
  | UsageForbiddenError
  | UsageAuthExpiredError
  | UsageNetworkError
  | UsageServerError;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch/domain error to a typed UsageError.
 *
 * @param err - Raw caught value from a try/catch block.
 * @returns A typed domain error.
 */
export function mapUsageError(err: unknown): UsageError {
  if (err instanceof UsageValidationError) return err;
  if (err instanceof UsageForbiddenError) return err;
  if (err instanceof UsageAuthExpiredError) return err;
  if (err instanceof UsageNetworkError) return err;
  if (err instanceof UsageServerError) return err;
  if (err instanceof TypeError) {
    return new UsageNetworkError(err.message, err);
  }
  if (err instanceof Error) return new UsageNetworkError(err.message, err);
  return new UsageNetworkError("Unknown error");
}
