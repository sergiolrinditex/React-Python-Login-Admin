/**
 * Hilo People — User domain types.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Re-exports the canonical UserProfile and EmployeeProfile from
 *   auth/domain/types (DRY — §D-T004-USER-DOMAIN-REUSE). Both GET /users/me and
 *   PATCH /users/me/language return the same UserProfile shape; no duplication here.
 *   Declares the Language literal union (the 3 supported locales).
 *
 * Source: TECHNICAL_GUIDE §6.1 (language whitelist es/en/fr), §6.2 (UserProfile).
 * Decision: §D-T004-USER-DOMAIN-REUSE — re-export, never re-declare.
 *
 * Non-negotiables §architecture: Domain imports nothing external (no React, no fetch).
 */

// Re-export the canonical profile types from auth domain.
// NEVER re-declare these — both endpoints share the same shape.
export type { UserProfile, EmployeeProfile } from "../../auth/domain/types";

// ---------------------------------------------------------------------------
// Language union (TECHNICAL_GUIDE §6.1 — strict backend whitelist)
// ---------------------------------------------------------------------------

/**
 * Supported language codes. Backend rejects anything outside this set.
 * Source: PATCH /api/v1/users/me/language strict whitelist (backend/app/users/schemas.py).
 */
export type LanguageCode = "es" | "en" | "fr";

// ---------------------------------------------------------------------------
// Typed user errors (mirror pattern from features/chat/data/errors.ts)
// ---------------------------------------------------------------------------

/**
 * Validation error — server returned 400 or 422 (both mapped here).
 * Typical case: invalid language code sent (defensive — selector constrains options).
 */
export class UserValidationError extends Error {
  public readonly code = "USER_VALIDATION_ERROR";

  constructor(message = "Invalid request payload.") {
    super(message);
    this.name = "UserValidationError";
  }
}

/**
 * Auth expired — server returned 401 after authFetch refresh exhausted.
 * AuthProvider + RequireAuth handle the redirect; this surfaces it for hook callers.
 */
export class UserAuthExpiredError extends Error {
  public readonly code = "USER_AUTH_EXPIRED";

  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "UserAuthExpiredError";
  }
}

/**
 * Forbidden — server returned 403 (insufficient role or missing employee_profile).
 */
export class UserForbiddenError extends Error {
  public readonly code = "USER_FORBIDDEN";

  constructor(message = "You do not have permission to perform this action.") {
    super(message);
    this.name = "UserForbiddenError";
  }
}

/**
 * Network error — fetch rejected (offline, CORS, DNS failure).
 */
export class UserNetworkError extends Error {
  public readonly code = "USER_NETWORK_ERROR";

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "UserNetworkError";
  }
}

/**
 * Server error — 5xx response from backend.
 */
export class UserServerError extends Error {
  public readonly code = "USER_SERVER_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "UserServerError";
    this.status = status;
  }
}

/** Union of all typed user errors. */
export type UserError =
  | UserValidationError
  | UserAuthExpiredError
  | UserForbiddenError
  | UserNetworkError
  | UserServerError;
