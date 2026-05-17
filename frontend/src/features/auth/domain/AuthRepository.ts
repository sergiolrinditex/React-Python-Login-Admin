/**
 * Hilo People — Auth domain repository port (interface).
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *   Extended in P03-S01-T001 — SignInPage: added signIn() + SignIn* types.
 *   Extended in P03-S01-T002 — SignUpPage: added signUp() + SignUp* types (§D-T002-AUTH-PORT).
 *   Extended in P03-S01-T003 — ForgotPasswordPage: added forgotPassword() + ForgotPassword* types.
 *   Extended in P03-S01-T005 — TwoFactorPage: added verifyMfa() + VerifyMfa* types (§D-T005-AUTH-PORT).
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
 *   SignUpOutcome is consumed by useSignUp (presentation/).
 *   ForgotPasswordOutcome is consumed by useForgotPassword (presentation/).
 *   VerifyMfaOutcome is consumed by useVerifyMfa (presentation/).
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
// Sign-up domain types (P03-S01-T002 — §D-T002-AUTH-PORT)
// ---------------------------------------------------------------------------

/**
 * Input to the sign-up operation.
 *
 * Policy:
 *   - email: RFC 5322 syntax (zod validates); server checks corporate domain allowlist.
 *   - password: min 12, max 256, ≥1 letter, ≥1 digit (mirrored client-side via zod for UX).
 *   - full_name: 1-200 chars; server strips whitespace.
 *   - legal_acceptance: must be literal true (service-layer enforced, not just Pydantic).
 *
 * Source: TECHNICAL_GUIDE §6.2 POST /api/v1/auth/sign-up + D-T002-EMAIL-CORP +
 *   D-T002-PASSWORD-PRE-VALIDATE + D-T002-LEGAL-LITERAL-TRUE.
 */
export interface SignUpRequest {
  email: string;
  password: string;
  full_name: string;
  legal_acceptance: true;
}

/**
 * Outcome of a successful sign-up operation.
 *
 * Note: sign-up does NOT return an access_token or set a refresh cookie.
 * User must sign in afterwards to bootstrap a session (D-T002-SUCCESS-REDIRECT).
 *
 * Source: TECHNICAL_GUIDE §6.2 — 201 response body.
 */
export interface SignUpOutcome {
  user_id: string;
  mfa_required: false;
}

// ---------------------------------------------------------------------------
// Forgot-password domain types (P03-S01-T003)
// ---------------------------------------------------------------------------

/**
 * Input to the forgot-password operation.
 * Only email is required — no password, no full_name.
 *
 * Source: TECHNICAL_GUIDE §6.2 POST /api/v1/auth/forgot-password.
 */
export interface ForgotPasswordRequest {
  email: string;
}

/**
 * Outcome of a successful forgot-password operation (200).
 * Anti-enumeration: server returns 200 regardless of whether the email exists.
 * UI shows identical success state for both known and unknown emails.
 *
 * Source: TECHNICAL_GUIDE §6.2 — 200 response (anti-enum design).
 */
export interface ForgotPasswordOutcome {
  /** Always true — indicates the request was accepted (not whether email exists). */
  sent: true;
}

// ---------------------------------------------------------------------------
// MFA verify domain types (P03-S01-T005 — §D-T005-AUTH-PORT)
// ---------------------------------------------------------------------------

/**
 * Input to the MFA verify operation.
 *
 * §D-T005-CHALLENGE-FIELD-NAME: the backend expects `challenge_id` in the body
 * but its VALUE is the full JWT mfa_challenge_token from the sign-in MFA branch.
 * This is named `challengeToken` in the domain to avoid confusion; the data
 * layer maps it to the wire field `challenge_id`.
 *
 * Source: TECHNICAL_GUIDE §6.2 MfaVerifyRequest (schemas.py:363-372).
 */
export interface VerifyMfaRequest {
  /** Full JWT string from SignInOutcome.mfa.challengeToken (wire field: challenge_id). */
  challengeToken: string;
  /** 6-digit numeric code from authenticator app. */
  code: string;
}

/**
 * Outcome of a successful MFA verify operation (200).
 * §D-T005-USERFETCH-AFTER-MFA: user is the FULL UserProfile (after fetchMe call).
 * The wire response returns a shorter MfaUserDto; the data layer calls fetchMe
 * before returning this outcome, so consumers always receive UserProfile.
 *
 * Source: TECHNICAL_GUIDE §6.2 — 200 response (T005 task pack §6.2).
 */
export interface VerifyMfaOutcome {
  accessToken: string;
  expiresIn: number;
  user: UserProfile;
}

// ---------------------------------------------------------------------------
// Auth repository port
// ---------------------------------------------------------------------------

/**
 * Port interface for all auth operations.
 * Implemented by data/authRepository.ts; consumed by presentation/AuthProvider.tsx,
 * presentation/useSignIn.ts, presentation/useSignUp.ts, presentation/useForgotPassword.ts
 * and presentation/useVerifyMfa.ts.
 *
 * Contract:
 *   - signIn(req): calls POST /api/v1/auth/sign-in; maps to SignInOutcome.
 *   - signUp(req): calls POST /api/v1/auth/sign-up; maps to SignUpOutcome.
 *   - forgotPassword(req): calls POST /api/v1/auth/forgot-password; anti-enum 200.
 *   - verifyMfa(req): calls POST /api/v1/auth/2fa/verify; maps to VerifyMfaOutcome.
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
   * Calls POST /api/v1/auth/sign-up with email, password, full_name, legal_acceptance.
   * Returns SignUpOutcome on 201 (user_id + mfa_required:false).
   * Does NOT create a session — user must sign in afterwards (D-T002-SUCCESS-REDIRECT).
   *
   * Typed errors: NonCorporateEmailError (400), LegalNotAcceptedError (400),
   *   EmailTakenError (409), PasswordPolicyError (422), SignupRateLimitedError (429),
   *   SignupValidationError (400/422 payload), SignupInternalError (5xx),
   *   NetworkError (fetch fail).
   *
   * @param req - { email, password, full_name, legal_acceptance: true }
   * @returns Result<SignUpOutcome, Error>
   */
  signUp(req: SignUpRequest): Promise<Result<SignUpOutcome>>;

  /**
   * Calls POST /api/v1/auth/forgot-password with email only.
   * Returns ForgotPasswordOutcome{sent:true} on 200 (anti-enum: same for known/unknown email).
   * Does NOT create a session. User receives a reset email (if registered).
   *
   * Anti-enum design: server returns 200 for ALL valid email syntax inputs.
   * Client MUST NOT distinguish between "email found" and "email not found".
   *
   * Typed errors: ForgotPasswordValidationError (400),
   *   ForgotPasswordRateLimitedError (429), ForgotPasswordInternalError (5xx),
   *   NetworkError (fetch fail).
   *
   * @param req - { email }
   * @returns Result<ForgotPasswordOutcome, Error>
   */
  forgotPassword(req: ForgotPasswordRequest): Promise<Result<ForgotPasswordOutcome>>;

  /**
   * Calls POST /api/v1/auth/2fa/verify with challenge_id (JWT) and code.
   * On success: calls fetchMe to get the full UserProfile, then returns VerifyMfaOutcome.
   * §D-T005-USERFETCH-AFTER-MFA: fetchMe is called inside the data layer so consumers
   * always receive UserProfile (not the wire MfaUserDto).
   *
   * §D-T005-CHALLENGE-FIELD-NAME: challengeToken (domain name) maps to challenge_id (wire field).
   * §D-T005-AGGREGATE-401: 401 AUTH_MFA_CODE_INVALID aggregates 4 internal failure modes.
   *
   * Typed errors: MfaPayloadInvalidError (400), MfaCodeInvalidError (401 aggregate),
   *   MfaChallengeExpiredError (410), MfaVerifyRateLimitedError (429),
   *   MfaVerifyInternalError (5xx), NetworkError (fetch fail).
   *
   * @param req - { challengeToken: JWT string, code: '123456' }
   * @returns Result<VerifyMfaOutcome, Error>
   */
  verifyMfa(req: VerifyMfaRequest): Promise<Result<VerifyMfaOutcome>>;

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
