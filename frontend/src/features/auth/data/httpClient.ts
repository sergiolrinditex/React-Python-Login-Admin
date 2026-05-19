/**
 * Hilo People — Auth-aware HTTP client with 401 single-flight refresh interceptor.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 * Fixed: P03-S01-T007 — API_BASE fallback set to "" per ADR-002 same-origin contract.
 * Fixed: P05-S01-T007 — Single-flight state moved to refreshSingleFlight.ts so that
 *   AuthRepository.refresh() and httpClient._doRefresh() share the same in-flight gate,
 *   preventing the F5 reload race where two concurrent requests carry the same HttpOnly
 *   refresh cookie and the backend revokes the first before the second arrives.
 *
 * Responsibility: fetch wrapper that:
 *   1. Injects credentials:'include' on every request (for HttpOnly refresh cookie).
 *   2. Injects X-Request-ID (UUIDv4) on every request (§security request correlation).
 *   3. Injects Authorization: Bearer <token> on protected requests (not on /auth/*).
 *   4. Intercepts 401 responses: fires ONE /auth/refresh (single-flight), then retries.
 *   5. If refresh itself returns 401: clears token + notifies caller via onAuthFailure callback.
 *
 * ADR-002 (same-origin reverse proxy): API_BASE defaults to "" so ALL fetch calls use
 * relative paths (e.g. "/api/v1/users/me"). In dev, Vite proxies /api → :8000; in prod,
 * Nginx proxies /api → backend container. VITE_API_BASE_URL="" in .env.example is the
 * contract pin — do NOT set it to "http://localhost:8000" (re-introduces CORS preflight).
 *
 * Security guardrails (task pack §P):
 *   - credentials:'include' on ALL fetches (defense in depth).
 *   - X-Request-ID injected at this layer for end-to-end traceability.
 *   - Access token injected ONLY for non-auth endpoints.
 *   - __authNoRetry flag prevents infinite refresh loop.
 *
 * Single-flight pattern (task pack §K T15–T17, P05-S01-T007):
 *   The single-flight gate now lives in refreshSingleFlight.ts. _doRefresh() is a
 *   thin wrapper that passes the onAuthFailure callback and the caller reason.
 *   All concurrent 401 interceptors (and AuthProvider.hydrate()) share ONE Promise.
 *
 * Non-negotiables §logging: BEFORE+AFTER+ERROR on every public operation.
 */

import { AuthSessionExpiredError, NetworkError, mapFetchError } from "./errors";
import { getAccessToken, clearAccessToken } from "./accessTokenStore";
import { logVerbose, logWarn, logError } from "./logger";
import { refreshAccessToken, _resetSingleFlight } from "./refreshSingleFlight";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

/** Endpoints that must NOT receive an Authorization Bearer header. */
const NO_AUTH_PREFIXES = ["/api/v1/auth/refresh", "/api/v1/auth/logout"];

// ---------------------------------------------------------------------------
// Internal: single-flight refresh (delegates to shared module)
// ---------------------------------------------------------------------------

/**
 * Fires ONE refresh request via the shared single-flight module.
 * Concurrent callers (including AuthRepository.refresh on hydrate) receive
 * the same Promise — only ONE POST /api/v1/auth/refresh is made per burst.
 * Resolves with the new access token string; throws AuthSessionExpiredError on failure.
 *
 * @param onAuthFailure - Called when refresh fails (clears store, triggers logout UI).
 * @returns Promise resolving to the new access token.
 */
function _doRefresh(onAuthFailure: () => void): Promise<string> {
  logVerbose("auth.http.refresh.delegated");
  return refreshAccessToken({ onAuthFailure, reason: "interceptor" });
}

// ---------------------------------------------------------------------------
// Internal: should inject Bearer header?
// ---------------------------------------------------------------------------

function _shouldInjectBearer(url: string): boolean {
  const path = url.startsWith("http") ? new URL(url).pathname : url;
  return !NO_AUTH_PREFIXES.some((prefix) => path.startsWith(prefix));
}

// ---------------------------------------------------------------------------
// Public: authFetch
// ---------------------------------------------------------------------------

/**
 * Auth-aware fetch wrapper.
 *
 * Behaviour:
 *   - Injects credentials:'include' and X-Request-ID always.
 *   - Injects Authorization: Bearer on non-auth endpoints.
 *   - On 401: fires single-flight refresh and retries once.
 *   - On second 401 after refresh: calls onAuthFailure and throws AuthSessionExpiredError.
 *   - __authNoRetry option prevents retry (used for /auth/refresh and /auth/logout calls).
 *
 * @param url - Full URL or path relative to API_BASE.
 * @param init - Standard RequestInit options.
 * @param opts - Auth options.
 * @param opts.onAuthFailure - Callback when session is fully expired (token cleared).
 * @returns The fetch Response.
 * @throws AuthSessionExpiredError when session cannot be recovered.
 * @throws NetworkError on network-level failures.
 */
export async function authFetch(
  url: string,
  init: RequestInit = {},
  opts: {
    onAuthFailure?: () => void;
    __authNoRetry?: boolean;
  } = {},
): Promise<Response> {
  const { onAuthFailure = () => void 0, __authNoRetry = false } = opts;

  const requestId = crypto.randomUUID();
  const fullUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;

  const headers = new Headers(init.headers ?? {});
  headers.set("X-Request-ID", requestId);

  if (_shouldInjectBearer(fullUrl)) {
    const token = getAccessToken();
    if (token !== null) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  logVerbose("auth.http.request.start", {
    url: fullUrl,
    method: init.method ?? "GET",
    request_id: requestId,
    has_bearer: headers.has("Authorization"),
  });

  let response: Response;
  try {
    response = await fetch(fullUrl, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch (err: unknown) {
    const domainErr = mapFetchError(err);
    logError("auth.http.request.network_error", {
      url: fullUrl,
      request_id: requestId,
      error: domainErr.message,
    });
    throw new NetworkError(domainErr.message, err);
  }

  logVerbose("auth.http.request.ok", {
    url: fullUrl,
    status: response.status,
    request_id: requestId,
  });

  if (response.status === 401 && !__authNoRetry) {
    logVerbose("auth.http.401_intercepted", {
      url: fullUrl,
      request_id: requestId,
    });

    try {
      const newToken = await _doRefresh(onAuthFailure);

      // Retry with new token
      const retryHeaders = new Headers(init.headers ?? {});
      retryHeaders.set("X-Request-ID", crypto.randomUUID());
      if (_shouldInjectBearer(fullUrl)) {
        retryHeaders.set("Authorization", `Bearer ${newToken}`);
      }

      logVerbose("auth.http.retry_after_refresh", { url: fullUrl });
      const retryResponse = await fetch(fullUrl, {
        ...init,
        headers: retryHeaders,
        credentials: "include",
      });

      if (retryResponse.status === 401) {
        logWarn("auth.http.retry_still_401", { url: fullUrl });
        clearAccessToken();
        onAuthFailure();
        throw new AuthSessionExpiredError();
      }

      return retryResponse;
    } catch (err: unknown) {
      if (err instanceof AuthSessionExpiredError) throw err;
      throw new AuthSessionExpiredError();
    }
  }

  return response;
}

/**
 * Resets the in-flight refresh state in the shared single-flight module.
 *
 * @internal Testing only — back-compat alias for _resetSingleFlight().
 *   Existing test files (auth.test.tsx, httpClient.test.ts) import this
 *   symbol; they do not need to change. The underlying state is now owned
 *   by refreshSingleFlight.ts.
 */
export function _resetInflight(): void {
  _resetSingleFlight();
}
