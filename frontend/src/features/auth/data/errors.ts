/**
 * Hilo People — Auth domain errors.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *   Extended in P03-S01-T001 — SignInPage: added sign-in-specific error classes.
 *   Extended in P03-S01-T002 — SignUpPage: added sign-up-specific error classes (§D-T002-AUTH-ERRORS).
 *   Extended in P03-S01-T003 — ForgotPasswordPage: added forgot-password error classes (§D-T003-AUTH-ERRORS).
 *   Extended in P03-S01-T005 — TwoFactorPage: added MFA verify error classes (§D-T005-AUTH-ERRORS).
 *
 * Responsibility: Typed error classes for auth operations.
 *   authRepository.ts throws these; presentation/ catches them via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error — use typed domain errors.
 *
 * Source: TECHNICAL_GUIDE §6.2 — error envelope {errors:[{code,message,field?,details?}]}.
 *   Sign-in error codes (§3.4 task pack): AUTH_INVALID_CREDENTIALS (401),
 *   AUTH_ACCOUNT_LOCKED (423), AUTH_SIGNIN_RATE_LIMITED (429),
 *   AUTH_SIGNIN_VALIDATION (400), AUTH_SIGNIN_INTERNAL_ERROR (500).
 *   Sign-up error codes (§5 task pack): AUTH_SIGNUP_NON_CORPORATE_EMAIL (400),
 *   AUTH_SIGNUP_LEGAL_NOT_ACCEPTED (400), AUTH_SIGNUP_EMAIL_TAKEN (409),
 *   AUTH_SIGNUP_INVALID_PAYLOAD (422), AUTH_SIGNUP_RATE_LIMITED (429).
 *   Forgot-password error codes (P03-S01-T003): AUTH_FORGOT_VALIDATION (400),
 *   AUTH_FORGOT_RATE_LIMITED (429), AUTH_FORGOT_INTERNAL (5xx).
 *   MFA verify error codes (P03-S01-T005): AUTH_MFA_CODE_INVALID (401 aggregate),
 *   AUTH_MFA_CHALLENGE_EXPIRED (410), AUTH_MFA_VERIFY_RATE_LIMITED (429),
 *   AUTH_INVALID_PAYLOAD (400), AUTH_MFA_VERIFY_INTERNAL_ERROR (5xx).
 */

// ---------------------------------------------------------------------------
// Auth error classes
// ---------------------------------------------------------------------------

/**
 * Session expired or invalid — server returned 401 AUTH_SESSION_EXPIRED.
 * Anti-enumeration: the same error class is used for all 401 failure modes.
 */
export class AuthSessionExpiredError extends Error {
  public readonly code = "AUTH_SESSION_EXPIRED";

  constructor(message = "Session expired or invalid; please sign in again.") {
    super(message);
    this.name = "AuthSessionExpiredError";
  }
}

/**
 * Network error — fetch rejected (offline, CORS, DNS failure).
 * Does NOT indicate an auth failure — may be a transient connectivity issue.
 */
export class NetworkError extends Error {
  public readonly code = "NETWORK_ERROR";

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "NetworkError";
  }
}

/**
 * Unexpected server error — 5xx response.
 */
export class ServerError extends Error {
  public readonly code = "SERVER_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "ServerError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Sign-in specific errors (P03-S01-T001)
// ---------------------------------------------------------------------------

/**
 * Invalid credentials — server returned 401 AUTH_INVALID_CREDENTIALS.
 * Anti-enumeration design: same copy for unknown email AND wrong password (D-T001-AGGREGATE-401).
 * The backend returns BYTE-IDENTICAL bodies for both failure modes on purpose.
 */
export class InvalidCredentialsError extends Error {
  public readonly code = "AUTH_INVALID_CREDENTIALS";

  constructor(message = "Email o contraseña incorrectos.") {
    super(message);
    this.name = "InvalidCredentialsError";
  }
}

/**
 * Account locked — server returned 423 AUTH_ACCOUNT_LOCKED.
 * Triggered after 5 failed attempts in a 900-second sliding window (P01-S02-T002).
 */
export class AccountLockedError extends Error {
  public readonly code = "AUTH_ACCOUNT_LOCKED";

  constructor(message = "Cuenta bloqueada temporalmente.") {
    super(message);
    this.name = "AccountLockedError";
  }
}

/**
 * Rate limited — server returned 429 AUTH_SIGNIN_RATE_LIMITED.
 * Carries retryAfter seconds from the Retry-After response header.
 */
export class RateLimitedError extends Error {
  public readonly code = "AUTH_SIGNIN_RATE_LIMITED";
  /** Seconds to wait before retrying, from Retry-After header. 0 if header absent. */
  public readonly retryAfter: number;

  constructor(retryAfter = 0, message = "Demasiados intentos. Intenta de nuevo más tarde.") {
    super(message);
    this.name = "RateLimitedError";
    this.retryAfter = retryAfter;
  }
}

/**
 * Validation error from sign-in — server returned 400 AUTH_SIGNIN_VALIDATION.
 * Rare: client-side zod should catch first, but we handle it for defence in depth.
 */
export class SigninValidationError extends Error {
  public readonly code = "AUTH_SIGNIN_VALIDATION";
  /** Field-level errors from the backend envelope, if present. */
  public readonly fields?: Record<string, string>;

  constructor(message = "Datos de inicio de sesión no válidos.", fields?: Record<string, string>) {
    super(message);
    this.name = "SigninValidationError";
    this.fields = fields;
  }
}

/**
 * Internal server error from sign-in — server returned 500 or unexpected status.
 */
export class SigninInternalError extends Error {
  public readonly code = "AUTH_SIGNIN_INTERNAL_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Error interno del servidor.") {
    super(message);
    this.name = "SigninInternalError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Sign-up specific errors (P03-S01-T002 — §D-T002-AUTH-ERRORS)
// ---------------------------------------------------------------------------

/**
 * Non-corporate email domain — server returned 400 AUTH_SIGNUP_NON_CORPORATE_EMAIL.
 * Email domain is not in the CORPORATE_EMAIL_DOMAINS allowlist (env-var controlled).
 * UI state: permission_denied → field-level inline error on email.
 * Anti-enumeration note: field "email" IS returned for this code (unlike 409).
 */
export class NonCorporateEmailError extends Error {
  public readonly code = "AUTH_SIGNUP_NON_CORPORATE_EMAIL";

  constructor(message = "Este email no es un email corporativo válido.") {
    super(message);
    this.name = "NonCorporateEmailError";
  }
}

/**
 * Legal terms not accepted — server returned 400 AUTH_SIGNUP_LEGAL_NOT_ACCEPTED.
 * Triggered when legal_acceptance is false or missing in the request body.
 * UI state: error_validation → checkbox-adjacent inline error.
 */
export class LegalNotAcceptedError extends Error {
  public readonly code = "AUTH_SIGNUP_LEGAL_NOT_ACCEPTED";

  constructor(message = "Debes aceptar los términos y condiciones para continuar.") {
    super(message);
    this.name = "LegalNotAcceptedError";
  }
}

/**
 * Email taken / account creation failed — server returned 409 AUTH_SIGNUP_EMAIL_TAKEN.
 * Anti-enumeration: server returns NO field for 409 (does not reveal whether email exists).
 * UI state: error_validation → generic copy (no email field highlight).
 * D-T002-409-NO-FIELD: field intentionally absent, show generic message.
 */
export class EmailTakenError extends Error {
  public readonly code = "AUTH_SIGNUP_EMAIL_TAKEN";

  constructor(message = "No se pudo crear la cuenta con ese email.") {
    super(message);
    this.name = "EmailTakenError";
  }
}

/**
 * Password policy violation — server returned 422 AUTH_SIGNUP_INVALID_PAYLOAD (field: password).
 * Policy: min 12 chars, max 256, ≥1 letter, ≥1 digit.
 * The client-side zod schema mirrors this for UX, but server is authoritative.
 * D-T002-PASSWORD-PRE-VALIDATE: pre-validated client-side; server is still authoritative.
 */
export class PasswordPolicyError extends Error {
  public readonly code = "AUTH_SIGNUP_INVALID_PAYLOAD_PASSWORD";
  /** The field where the error occurred, if provided by the server. */
  public readonly field: string;

  constructor(field = "password", message = "La contraseña no cumple la política de seguridad.") {
    super(message);
    this.name = "PasswordPolicyError";
    this.field = field;
  }
}

/**
 * Rate limited — server returned 429 AUTH_SIGNUP_RATE_LIMITED.
 * Carries retryAfter seconds from the Retry-After response header.
 * UI state: permission_denied → disabled submit + countdown copy.
 */
export class SignupRateLimitedError extends Error {
  public readonly code = "AUTH_SIGNUP_RATE_LIMITED";
  /** Seconds to wait before retrying, from Retry-After header. 0 if header absent. */
  public readonly retryAfter: number;

  constructor(retryAfter = 0, message = "Demasiados intentos. Intenta de nuevo más tarde.") {
    super(message);
    this.name = "SignupRateLimitedError";
    this.retryAfter = retryAfter;
  }
}

/**
 * Generic payload validation error — server returned 400/422 for email, full_name, or other fields.
 * Carries optional field name and message from the backend envelope.
 */
export class SignupValidationError extends Error {
  public readonly code = "AUTH_SIGNUP_VALIDATION";
  /** Backend field name where the error occurred. */
  public readonly field?: string;

  constructor(field?: string, message = "Datos de registro no válidos.") {
    super(message);
    this.name = "SignupValidationError";
    this.field = field;
  }
}

/**
 * Internal server error from sign-up — server returned 500 or unexpected status.
 */
export class SignupInternalError extends Error {
  public readonly code = "AUTH_SIGNUP_INTERNAL_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Error interno del servidor.") {
    super(message);
    this.name = "SignupInternalError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Forgot-password specific errors (P03-S01-T003 — §D-T003-AUTH-ERRORS)
// ---------------------------------------------------------------------------

/**
 * Validation error from forgot-password — server returned 400.
 * Rare: client-side zod should catch first, but we handle for defence in depth.
 * UI state: error_validation → inline field error.
 */
export class ForgotPasswordValidationError extends Error {
  public readonly code = "AUTH_FORGOT_VALIDATION";
  /** Backend field name where the error occurred, if present. */
  public readonly field?: string;

  constructor(field?: string, message = "Datos de email no válidos.") {
    super(message);
    this.name = "ForgotPasswordValidationError";
    this.field = field;
  }
}

/**
 * Rate limited — server returned 429 for forgot-password.
 * Carries retryAfter seconds from the Retry-After response header.
 * UI state: permission_denied → disabled submit + countdown copy.
 */
export class ForgotPasswordRateLimitedError extends Error {
  public readonly code = "AUTH_FORGOT_RATE_LIMITED";
  /** Seconds to wait before retrying, from Retry-After header. 0 if header absent. */
  public readonly retryAfter: number;

  constructor(retryAfter = 0, message = "Demasiados intentos. Intenta de nuevo más tarde.") {
    super(message);
    this.name = "ForgotPasswordRateLimitedError";
    this.retryAfter = retryAfter;
  }
}

/**
 * Internal server error from forgot-password — server returned 500 or unexpected status.
 * UI state: error_network → generic server error copy.
 */
export class ForgotPasswordInternalError extends Error {
  public readonly code = "AUTH_FORGOT_INTERNAL_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Error interno del servidor.") {
    super(message);
    this.name = "ForgotPasswordInternalError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// MFA verify specific errors (P03-S01-T005 — §D-T005-AUTH-ERRORS)
// ---------------------------------------------------------------------------

/**
 * Payload validation error from MFA verify — server returned 400 AUTH_INVALID_PAYLOAD.
 * Triggered when code is not 6 digits or challenge_id < 30 chars.
 * UI state: error_validation → inline field error on code input.
 */
export class MfaPayloadInvalidError extends Error {
  public readonly code = "AUTH_INVALID_PAYLOAD";

  constructor(message = "Introduce un código de 6 dígitos.") {
    super(message);
    this.name = "MfaPayloadInvalidError";
  }
}

/**
 * Invalid code — server returned 401 AUTH_MFA_CODE_INVALID.
 * §D-T005-AGGREGATE-401: anti-enumeration design. Backend returns BYTE-IDENTICAL body
 * for wrong code, invalid challenge, missing secret, AND replay. UI MUST NOT differentiate.
 * One single copy: "Código incorrecto. Vuelve a intentarlo."
 * UI state: error_validation.
 */
export class MfaCodeInvalidError extends Error {
  public readonly code = "AUTH_MFA_CODE_INVALID";

  constructor(message = "Código incorrecto. Vuelve a intentarlo.") {
    super(message);
    this.name = "MfaCodeInvalidError";
  }
}

/**
 * Challenge expired — server returned 410 AUTH_MFA_CHALLENGE_EXPIRED.
 * Signature is valid but exp < now.
 * UI state: permission_denied → auto-redirect to /auth/sign-in after 1.5s flash.
 * §D-T005-EXPIRED-CHALLENGE.
 */
export class MfaChallengeExpiredError extends Error {
  public readonly code = "AUTH_MFA_CHALLENGE_EXPIRED";

  constructor(message = "Tu desafío ha expirado. Inicia sesión de nuevo.") {
    super(message);
    this.name = "MfaChallengeExpiredError";
  }
}

/**
 * Rate limited — server returned 429 AUTH_MFA_VERIFY_RATE_LIMITED.
 * > 20/min/IP (burst 5). Carries retryAfter seconds from Retry-After header.
 * UI state: permission_denied → disabled submit + countdown copy.
 */
export class MfaVerifyRateLimitedError extends Error {
  public readonly code = "AUTH_MFA_VERIFY_RATE_LIMITED";
  /** Seconds to wait before retrying, from Retry-After header. 0 if header absent. */
  public readonly retryAfter: number;

  constructor(retryAfter = 0, message = "Demasiados intentos. Espera unos segundos e inténtalo de nuevo.") {
    super(message);
    this.name = "MfaVerifyRateLimitedError";
    this.retryAfter = retryAfter;
  }
}

/**
 * Internal server error from MFA verify — server returned 500 or unexpected status.
 * UI state: error_network → generic server error copy.
 */
export class MfaVerifyInternalError extends Error {
  public readonly code = "AUTH_MFA_VERIFY_INTERNAL_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Error interno del servidor.") {
    super(message);
    this.name = "MfaVerifyInternalError";
    this.status = status;
  }
}

/** Union type for all MFA verify errors (§D-T005-AUTH-ERRORS). */
export type MfaVerifyError =
  | MfaPayloadInvalidError
  | MfaCodeInvalidError
  | MfaChallengeExpiredError
  | MfaVerifyRateLimitedError
  | MfaVerifyInternalError
  | NetworkError
  | Error;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch error to a typed domain error.
 * Used in authRepository to ensure Result<T, KnownError> signatures.
 *
 * @param err - Raw caught value from a try/catch block.
 * @returns A typed domain error (NetworkError, AuthSessionExpiredError, ServerError, or Error).
 */
export function mapFetchError(
  err: unknown,
): NetworkError | AuthSessionExpiredError | ServerError | Error {
  if (err instanceof AuthSessionExpiredError) return err;
  if (err instanceof NetworkError) return err;
  if (err instanceof ServerError) return err;
  if (err instanceof TypeError) {
    // fetch() rejects with TypeError on network failures
    return new NetworkError(err.message, err);
  }
  if (err instanceof Error) return err;
  return new Error("Unknown error");
}
