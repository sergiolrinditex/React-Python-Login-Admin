/**
 * Hilo People — Auth domain errors.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *   Extended in P03-S01-T001 — SignInPage: added sign-in-specific error classes.
 *
 * Responsibility: Typed error classes for auth operations.
 *   authRepository.ts throws these; presentation/ catches them via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error — use typed domain errors.
 *
 * Source: TECHNICAL_GUIDE §6.2 — error envelope {errors:[{code,message,field?,details?}]}.
 *   Sign-in error codes (§3.4 task pack): AUTH_INVALID_CREDENTIALS (401),
 *   AUTH_ACCOUNT_LOCKED (423), AUTH_SIGNIN_RATE_LIMITED (429),
 *   AUTH_SIGNIN_VALIDATION (400), AUTH_SIGNIN_INTERNAL_ERROR (500).
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
