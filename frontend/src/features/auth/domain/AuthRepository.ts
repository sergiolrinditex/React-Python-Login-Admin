/**
 * Hilo People — Auth domain repository port (interface).
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *   Extended in P03-S01-T001 — SignInPage: added signIn() + SignIn* types.
 *
 * Responsibility: Port (interface) for the auth data layer.
 *   Defines what operations the domain needs; the data layer implements them.
 *   No imports of external libs, no React, no fetch calls here.
 *
 * Clean Architecture: presentation/ depends on this port, NOT on authRepository.ts
 *   directly. This decouples the UI from fetch implementation details.
 *
 * Non-obvious deps: SignInOutcome is a discriminated union consumed by
 *   useSignIn (presentation/) and by tests without touching fetch internals.
 */

import type { UserProfile } from "./types";

// ---------------------------------------------------------------------------
// Result types for typed error handling (no throw upward)
// ---------------------------------------------------------------------------

/** Result type for operations that may succeed or fail. */
export type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

// ---------------------------------------------------------------------------
// Sign-in domain types (P03-S01-T001)
// ---------------------------------------------------------------------------

/**
 * Input to the sign-in operation.
 * Password is min(1) on sign-in (not the full creation policy — D-T001-PASSWORD-MIN).
 */
export interface SignInRequest {
  email: string;
  password: string;
}

/**
 * Discriminated union for sign-in outcomes.
 *
 * success: no-MFA path — contains access token and user profile (fetchMe already called).
 * mfa: MFA challenge path — contains challengeToken + expiresIn (router state transport).
 *
 * Source: §3.4 response shapes + D-T001-USERFETCH-ON-SUCCESS + D-T001-CHALLENGE-TRANSPORT.
 */
export type SignInOutcome =
  | { kind: "success"; accessToken: string; user: UserProfile }
  | { kind: "mfa"; challengeToken: string; expiresIn: number };

// ---------------------------------------------------------------------------
// Auth repository port
// ---------------------------------------------------------------------------

/**
 * Port interface for all auth operations.
 * Implemented by data/authRepository.ts; consumed by presentation/AuthProvider.tsx
 * and presentation/useSignIn.ts.
 *
 * Contract:
 *   - signIn(req): calls POST /api/v1/auth/sign-in; maps to SignInOutcome.
 *   - refresh(): calls POST /api/v1/auth/refresh (cookie-only). Returns access token on success.
 *   - fetchMe(accessToken): calls GET /api/v1/users/me with Bearer header.
 *   - logout(accessToken): calls POST /api/v1/auth/logout with Bearer + cookie.
 */
export interface IAuthRepository {
  /**
   * Calls POST /api/v1/auth/sign-in with email+password.
   * Maps both success shapes (no-MFA + MFA) to SignInOutcome.
   * On no-MFA success: also calls fetchMe and returns {kind:'success', user}.
   * On MFA: returns {kind:'mfa', challengeToken, expiresIn}. No fetchMe needed.
   *
   * Typed errors: InvalidCredentialsError (401), AccountLockedError (423),
   *   RateLimitedError (429), SigninValidationError (400), SigninInternalError (5xx),
   *   NetworkError (fetch fail).
   *
   * @param req - { email, password }
   * @returns Result<SignInOutcome, Error>
   */
  signIn(req: SignInRequest): Promise<Result<SignInOutcome>>;

  /**
   * Calls POST /api/v1/auth/refresh. Browser auto-sends HttpOnly refresh cookie.
   * Returns the new opaque access token string, or an error.
   * The response also sets a new rotated refresh cookie — browser handles automatically.
   *
   * @returns Result<string> where string is the new access_token.
   */
  refresh(): Promise<Result<string>>;

  /**
   * Calls GET /api/v1/users/me with the Bearer access token.
   * Returns the UserProfile on success; error on 401 or network failure.
   *
   * @param accessToken - Opaque JWT string from AuthProvider's in-memory store.
   */
  fetchMe(accessToken: string): Promise<Result<UserProfile>>;

  /**
   * Calls POST /api/v1/auth/logout. Requires Bearer access token.
   * The backend clears the refresh cookie on ALL response paths (204 or 401).
   * This method returns ok:true on 204 and ok:false on 401/network error.
   * The caller MUST clear the access token store REGARDLESS of the result.
   *
   * @param accessToken - Current in-memory access token.
   */
  logout(accessToken: string): Promise<Result<void>>;
}
