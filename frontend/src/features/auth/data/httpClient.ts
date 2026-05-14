/**
 * Hilo People — Auth-aware HTTP client with 401 single-flight refresh interceptor.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 * Fixed: P03-S01-T007 — API_BASE fallback set to "" per ADR-002 same-origin contract.
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
 * Single-flight pattern (task pack §K T15–T17):
 *   A single Promise<string> (_inflight) serializes concurrent 401 retries.
 *   All requesters that hit 401 while refresh is in-flight await the same promise.
 *
 * Non-negotiables §logging: BEFORE+AFTER+ERROR on every public operation.
 */

import { AuthSessionExpiredError, NetworkError, mapFetchError } from "./errors";
import { getAccessToken, setAccessToken, clearAccessToken } from "./accessTokenStore";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const REFRESH_URL = `${API_BASE}/api/v1/auth/refresh`;

/** Endpoints that must NOT receive an Authorization Bearer header. */
const NO_AUTH_PREFIXES = ["/api/v1/auth/refresh", "/api/v1/auth/logout"];

// ---------------------------------------------------------------------------
// Internal: single-flight refresh promise
// ---------------------------------------------------------------------------

let _inflight: Promise<string> | null = null;

/**
 * Fires ONE refresh request. Concurrent callers receive the same Promise.
 * Resolves with the new access token string; rejects with AuthSessionExpiredError.
 *
 * @param onAuthFailure - Called when refresh fails (clears store, triggers logout UI).
 * @returns Promise resolving to the new access token.
 */
async function _doRefresh(onAuthFailure: () => void): Promise<string> {
  if (_inflight !== null) {
    logVerbose("auth.http.refresh_inflight");
    return _inflight;
  }

  logVerbose("auth.http.refresh.start");
  _inflight = (async (): Promise<string> => {
    try {
      const requestId = crypto.randomUUID();
      const response = await fetch(REFRESH_URL, {
        method: "POST",
        credentials: "include",
        headers: { "X-Request-ID": requestId },
      });

      if (!response.ok) {
        logWarn("auth.http.refresh.failed", { status: response.status, request_id: requestId });
        clearAccessToken();
        onAuthFailure();
        throw new AuthSessionExpiredError();
      }

      const body = (await response.json()) as {
        data: { access_token: string };
      };
      const newToken = body.data.access_token;
      setAccessToken(newToken);
      logVerbose("auth.http.refresh.ok", {
        request_id: requestId,
        token_len: newToken.length,
      });
      return newToken;
    } finally {
      _inflight = null;
    }
  })();

  return _inflight;
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

/** Resets the in-flight refresh state. Test utility only. */
export function _resetInflight(): void {
  _inflight = null;
}
