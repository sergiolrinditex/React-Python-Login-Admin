/**
 * Hilo People — Single-flight refresh token module.
 *
 * Slice/Phase: P05-S01-T007 — auth store: deduplicate concurrent refresh token calls
 *   on reload to prevent race-condition logout / Phase 5.
 *
 * Responsibility: Owns the single shared in-flight Promise<string> for POST
 *   /api/v1/auth/refresh. Both httpClient._doRefresh() and AuthRepository.refresh()
 *   delegate here so that only ONE network request is made regardless of how many
 *   concurrent callers arrive (e.g. AuthProvider.hydrate() + httpClient 401 interceptor
 *   on a page reload/F5 with a valid HttpOnly refresh cookie).
 *
 * Single-flight contract:
 *   1. First caller → creates the Promise, stores it in _inflight, logs `.start`.
 *   2. Subsequent callers while _inflight !== null → join the same Promise, log `.joined`.
 *   3. On Promise settle (success or failure) → _inflight = null (cleared in `finally`).
 *   4. Next caller after settle → creates a NEW Promise (step 1 again).
 *
 * Logging contract (TECHNICAL_GUIDE §6 + non-negotiables §logging):
 *   - auth.refresh.singleflight.start   → verbose; payload: { request_id, reason }
 *   - auth.refresh.singleflight.joined  → verbose; payload: { reason }
 *   - auth.refresh.singleflight.ok      → verbose; payload: { request_id, token_len, reason }
 *   - auth.refresh.singleflight.failed  → warn;    payload: { status, request_id, reason }
 *   - auth.refresh.singleflight.network → error;   payload: { error: message, reason }
 *   NEVER log: token value, cookie value, email, password, TOTP secret.
 *
 * Security: X-Request-ID (UUIDv4) is generated per fresh refresh call for
 *   end-to-end traceability (non-negotiables §request-correlation).
 *
 * Dependencies: accessTokenStore.ts (setAccessToken, clearAccessToken),
 *   errors.ts (AuthSessionExpiredError, NetworkError, mapFetchError), logger.ts.
 *
 * @module refreshSingleFlight
 */

import { setAccessToken, clearAccessToken } from "./accessTokenStore";
import { AuthSessionExpiredError, NetworkError, mapFetchError } from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

/** Absolute or relative URL for the refresh endpoint. */
export const REFRESH_URL = `${API_BASE}/api/v1/auth/refresh`;

// ---------------------------------------------------------------------------
// Module-private in-flight state (single-flight pattern)
// ---------------------------------------------------------------------------

/**
 * The single shared in-flight Promise while a refresh is pending.
 * Null when no refresh is in progress.
 * Module-private: NOT exported. Only _resetSingleFlight exposes it for tests.
 */
let _inflight: Promise<string> | null = null;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Executes POST /api/v1/auth/refresh exactly once for concurrent callers.
 *
 * If a refresh request is already in-flight (e.g. both AuthProvider.hydrate()
 * and httpClient._doRefresh() called this at the same time on F5), the joining
 * caller awaits the existing Promise — no second network request is made.
 *
 * On success: stores the new access token via setAccessToken() and resolves
 *   with the raw token string. The caller may use this value.
 * On HTTP error (non-200): clears the token via clearAccessToken(), calls
 *   onAuthFailure() (typically triggers logout UI), and throws
 *   AuthSessionExpiredError.
 * On network error: throws NetworkError (does NOT call onAuthFailure — the
 *   session may still be valid; the caller decides whether to retry).
 *
 * @param opts.onAuthFailure - Called exactly once when refresh itself returns
 *   a non-200 response. Typically wired to AuthProvider.onAuthFailure.
 * @param opts.reason - Caller tag for log correlation ("interceptor" | "hydrate"
 *   | "manual"). Appears in log events, never in network requests.
 * @returns Promise resolving to the new access token string.
 * @throws AuthSessionExpiredError when the refresh response is not 2xx.
 * @throws NetworkError when the fetch itself rejects (offline, CORS, DNS).
 */
export function refreshAccessToken(opts: {
  onAuthFailure?: () => void;
  reason: "interceptor" | "hydrate" | "manual";
}): Promise<string> {
  const { onAuthFailure = () => void 0, reason } = opts;

  // Join the existing in-flight Promise if one exists.
  if (_inflight !== null) {
    logVerbose("auth.refresh.singleflight.joined", { reason });
    return _inflight;
  }

  // Create a new in-flight Promise. This is the critical section:
  // we assign synchronously BEFORE the first await so any concurrent
  // caller that enters this function while we are suspended will see
  // _inflight !== null and join, not create a second request.
  const requestId = crypto.randomUUID();
  logVerbose("auth.refresh.singleflight.start", { request_id: requestId, reason });

  _inflight = (async (): Promise<string> => {
    try {
      const response = await fetch(REFRESH_URL, {
        method: "POST",
        credentials: "include",
        headers: { "X-Request-ID": requestId },
      });

      if (!response.ok) {
        logWarn("auth.refresh.singleflight.failed", {
          status: response.status,
          request_id: requestId,
          reason,
        });
        clearAccessToken();
        onAuthFailure();
        throw new AuthSessionExpiredError();
      }

      const body = (await response.json()) as { data: { access_token: string } };
      const newToken = body.data.access_token;
      setAccessToken(newToken);
      logVerbose("auth.refresh.singleflight.ok", {
        request_id: requestId,
        token_len: newToken.length,
        reason,
      });
      return newToken;
    } catch (err: unknown) {
      // Re-throw typed domain errors without wrapping.
      if (err instanceof AuthSessionExpiredError) throw err;
      // Map network errors.
      const domainErr = mapFetchError(err);
      if (domainErr instanceof NetworkError) {
        logError("auth.refresh.singleflight.network", {
          error: domainErr.message,
          reason,
        });
        throw domainErr;
      }
      // Any other unexpected error: wrap as NetworkError for the caller.
      const wrapped = new NetworkError(
        err instanceof Error ? err.message : "Unknown refresh error",
        err,
      );
      logError("auth.refresh.singleflight.network", {
        error: wrapped.message,
        reason,
      });
      throw wrapped;
    } finally {
      // Always reset so the next caller creates a fresh Promise.
      _inflight = null;
    }
  })();

  return _inflight;
}

/**
 * Resets the in-flight state to null.
 *
 * @internal Testing only — DO NOT call from production code.
 *   Use this in beforeEach/afterEach to isolate test cases that
 *   test concurrent refresh behaviour.
 */
export function _resetSingleFlight(): void {
  _inflight = null;
}
