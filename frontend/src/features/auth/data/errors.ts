/**
 * Hilo People — Auth domain errors.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Typed error classes for auth operations.
 *   authRepository.ts throws these; presentation/ catches them via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error — use typed domain errors.
 *
 * Source: TECHNICAL_GUIDE §6.2 — error envelope {errors:[{code,message,field?,details?}]}.
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
