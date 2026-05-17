/**
 * Hilo People — Admin AI typed error classes.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-ADMINAI-FEATURE
 *
 * Responsibility: Typed error classes for admin-ai data layer operations.
 *   adminAiRepository returns these via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error — use typed domain errors.
 *
 * Source: TECHNICAL_GUIDE §6.2 error codes for GET /api/v1/admin/usage
 *   (401 AUTH_SESSION_EXPIRED, 403 forbidden, 422 ADMIN_USAGE_INVALID_PAYLOAD /
 *   ADMIN_USAGE_WINDOW_TOO_WIDE, 500 INTERNAL_ERROR).
 *
 * Mirrors the pattern from features/chat/data/errors.ts and features/auth/data/errors.ts.
 */

// ---------------------------------------------------------------------------
// Error classes
// ---------------------------------------------------------------------------

/**
 * Session expired — server returned 401 after refresh was exhausted.
 * Handled by authFetch single-flight; surfaces here when recovery is impossible.
 * On this error the page calls onAuthFailure() to bounce to sign-in.
 */
export class AdminAiAuthExpiredError extends Error {
  public readonly code = "ADMIN_AI_AUTH_EXPIRED";

  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "AdminAiAuthExpiredError";
  }
}

/**
 * Forbidden — server returned 403 (non-admin role).
 * Defensive only: RequireRole already guards the /admin route.
 */
export class AdminAiForbiddenError extends Error {
  public readonly code = "ADMIN_AI_FORBIDDEN";

  constructor(message = "You do not have permission to view this page.") {
    super(message);
    this.name = "AdminAiForbiddenError";
  }
}

/**
 * Per-field error detail from backend 422 response.
 * Shape mirrors backend {error, code, details} envelope where details may include
 * an errors[] array with field-level messages.
 * Slice: P04-S01-T003 — ModelWizardPage (additive extension).
 */
export interface ValidationFieldError {
  field: string;
  code: string;
  message: string;
}

/**
 * Validation error — server returned 422 (bad params or window too wide).
 * Should not occur in practice with the client's hard-coded 30d window + group_by=model,
 * but handled defensively — falls through to error_network UX state.
 * Source: TECHNICAL_GUIDE §6.2 — ADMIN_USAGE_INVALID_PAYLOAD, ADMIN_USAGE_WINDOW_TOO_WIDE.
 *
 * Extended in P04-S01-T003: added optional fieldErrors[] for wizard field-level
 * validation messages from POST /api/v1/admin/ai/providers 422 response body.
 */
export class AdminAiValidationError extends Error {
  public readonly code = "ADMIN_AI_VALIDATION_ERROR";
  public readonly serverCode: string;
  /** Optional array of field-level errors for form display (§D-T003-422-FIELD-ERRORS). */
  public readonly fieldErrors?: ValidationFieldError[];

  constructor(
    serverCode = "ADMIN_USAGE_INVALID_PAYLOAD",
    message = "Invalid usage request.",
    fieldErrors?: ValidationFieldError[],
  ) {
    super(message);
    this.name = "AdminAiValidationError";
    this.serverCode = serverCode;
    this.fieldErrors = fieldErrors;
  }
}

/**
 * Network / transient error — fetch rejected (offline, CORS, DNS failure) or 5xx.
 * Maps to the error_network UX state with a retry CTA.
 */
export class AdminAiNetworkError extends Error {
  public readonly code = "ADMIN_AI_NETWORK_ERROR";

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "AdminAiNetworkError";
  }
}

/**
 * Internal server error — server returned 5xx.
 * Treated as error_network at the UX level (same retry path).
 */
export class AdminAiInternalError extends Error {
  public readonly code = "ADMIN_AI_INTERNAL_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "AdminAiInternalError";
    this.status = status;
  }
}

/** Union of all typed admin-ai errors. */
export type AdminAiError =
  | AdminAiAuthExpiredError
  | AdminAiForbiddenError
  | AdminAiValidationError
  | AdminAiNetworkError
  | AdminAiInternalError;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch/domain error to a typed AdminAiError.
 * Unknown / TypeError falls through to AdminAiNetworkError.
 *
 * @param err - Raw caught value.
 * @returns A typed domain error.
 */
export function mapAdminAiError(err: unknown): AdminAiError {
  if (err instanceof AdminAiAuthExpiredError) return err;
  if (err instanceof AdminAiForbiddenError) return err;
  if (err instanceof AdminAiValidationError) return err;
  if (err instanceof AdminAiNetworkError) return err;
  if (err instanceof AdminAiInternalError) return err;
  if (err instanceof TypeError) return new AdminAiNetworkError(err.message, err);
  if (err instanceof Error) return new AdminAiNetworkError(err.message, err);
  return new AdminAiNetworkError("Unknown error");
}
