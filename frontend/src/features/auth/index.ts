/**
 * Hilo People — Auth feature public barrel export.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *   Extended in P03-S01-T001 — SignInPage: added useSignIn, sign-in errors, route constants.
 *   Extended in P03-S01-T002 — SignUpPage: added useSignUp, sign-up errors, SignUp* types (§D-T002-AUTH-INDEX).
 *   Extended in P03-S01-T003 — ForgotPasswordPage: added useForgotPassword, forgot-password errors.
 *   Extended in P03-S01-T005 — TwoFactorPage: added useVerifyMfa, MFA errors, VerifyMfa* types (§D-T005-AUTH-INDEX).
 *
 * Responsibility: Single import surface for downstream slices.
 *   Only export what downstream consumers genuinely need.
 *   Internal data-layer details (httpClient, logger internals) stay unexported.
 *
 * YAGNI: only export what is consumed by router.tsx and upcoming page slices.
 */

// Domain types
export type { UserProfile, AuthSession, AuthStatus, Role, EmployeeProfile } from "./domain/types";
export type {
  IAuthRepository,
  Result,
  SignInRequest,
  SignInOutcome,
  SignUpRequest,
  SignUpOutcome,
  ForgotPasswordRequest,
  ForgotPasswordOutcome,
  VerifyMfaRequest,
  VerifyMfaOutcome,
} from "./domain/AuthRepository";

// Data layer — only what pages need to call authFetch directly
export { authFetch } from "./data/httpClient";
export { getAccessToken, setAccessToken, clearAccessToken, hasAccessToken } from "./data/accessTokenStore";
export {
  AuthSessionExpiredError,
  NetworkError,
  InvalidCredentialsError,
  AccountLockedError,
  RateLimitedError,
  SigninValidationError,
  SigninInternalError,
  // P03-S01-T002: sign-up errors (§D-T002-AUTH-INDEX)
  NonCorporateEmailError,
  LegalNotAcceptedError,
  EmailTakenError,
  PasswordPolicyError,
  SignupRateLimitedError,
  SignupValidationError,
  SignupInternalError,
  // P03-S01-T003: forgot-password errors
  ForgotPasswordValidationError,
  ForgotPasswordRateLimitedError,
  ForgotPasswordInternalError,
  // P03-S01-T005: MFA verify errors (§D-T005-AUTH-INDEX)
  MfaPayloadInvalidError,
  MfaCodeInvalidError,
  MfaChallengeExpiredError,
  MfaVerifyRateLimitedError,
  MfaVerifyInternalError,
} from "./data/errors";
export type { MfaVerifyError } from "./data/errors";

// Presentation layer — public components and hooks
export { AuthProvider, useAuth } from "./presentation/AuthProvider";
export type { AuthContextValue } from "./presentation/AuthProvider";
export { RequireAuth, ROUTE_AUTH_SIGN_IN } from "./presentation/RequireAuth";
export { RequireRole } from "./presentation/RequireRole";
export { getSafeRedirect, DEFAULT_SAFE_REDIRECT } from "./presentation/redirectAfterAuth";
// P03-S01-T001: sign-in hook (§D-T001-AUTH-INDEX)
export { useSignIn } from "./presentation/useSignIn";
export type { UseSignInReturn, SignInError } from "./presentation/useSignIn";
// P03-S01-T002: sign-up hook (§D-T002-AUTH-INDEX)
export { useSignUp } from "./presentation/useSignUp";
export type { UseSignUpReturn, SignUpError } from "./presentation/useSignUp";
// P03-S01-T003: forgot-password hook
export { useForgotPassword } from "./presentation/useForgotPassword";
export type { UseForgotPasswordReturn, ForgotPasswordError } from "./presentation/useForgotPassword";
// P03-S01-T005: MFA verify hook (§D-T005-AUTH-INDEX)
export { useVerifyMfa } from "./presentation/useVerifyMfa";
export type { UseVerifyMfaReturn, VerifyMfaError } from "./presentation/useVerifyMfa";
