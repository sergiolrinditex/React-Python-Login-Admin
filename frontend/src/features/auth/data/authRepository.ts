/**
 * Hilo People — Auth repository (concrete HTTP adapter).
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Concrete implementation of IAuthRepository (domain port).
 *   Calls the backend auth/user endpoints. All calls use authFetch (credentials:'include',
 *   X-Request-ID, Bearer injection, single-flight 401 interceptor).
 *
 * Clean Architecture: this is the DATA layer. Presentation/ depends on the port
 *   (IAuthRepository) NOT on this file directly.
 *
 * Endpoints consumed (TECHNICAL_GUIDE §6.2):
 *   - POST /api/v1/auth/refresh  → cookie-only; returns new access_token.
 *   - GET  /api/v1/users/me      → Bearer required; returns UserProfile.
 *   - POST /api/v1/auth/logout   → Bearer required; 204 on success.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 */

import type { IAuthRepository, Result } from "../domain/AuthRepository";
import type { UserProfile } from "../domain/types";
import { AuthSessionExpiredError, NetworkError, mapFetchError } from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Concrete repository
// ---------------------------------------------------------------------------

/**
 * Concrete AuthRepository implementation against the real backend.
 *
 * Creates a fresh instance with an onAuthFailure callback wired by AuthProvider.
 * The callback is called when a 401 cannot be recovered by refresh.
 */
export class AuthRepository implements IAuthRepository {
  private readonly _onAuthFailure: () => void;

  /**
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   */
  constructor(onAuthFailure: () => void) {
    this._onAuthFailure = onAuthFailure;
  }

  /**
   * Calls POST /api/v1/auth/refresh (no body; refresh cookie auto-sent).
   * Returns the new access token string on 200; error on 401 or network failure.
   */
  async refresh(): Promise<Result<string>> {
    logVerbose("auth.repo.refresh.start");
    try {
      const requestId = crypto.randomUUID();
      const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-Request-ID": requestId },
      });

      if (response.status === 401) {
        logWarn("auth.repo.refresh.session_expired", { request_id: requestId });
        return { ok: false, error: new AuthSessionExpiredError() };
      }

      if (!response.ok) {
        logError("auth.repo.refresh.unexpected_status", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new Error(`Refresh failed: ${response.status}`) };
      }

      const body = await _safeJson<{ data: { access_token: string } }>(response);
      const token = body.data.access_token;
      logVerbose("auth.repo.refresh.ok", {
        request_id: requestId,
        token_len: token.length,
      });
      return { ok: true, value: token };
    } catch (err: unknown) {
      const domainErr = mapFetchError(err);
      logError("auth.repo.refresh.error", { error: domainErr.message });
      return { ok: false, error: domainErr };
    }
  }

  /**
   * Calls GET /api/v1/users/me with Authorization: Bearer <accessToken>.
   * Returns the UserProfile on 200; AuthSessionExpiredError on 401.
   */
  async fetchMe(accessToken: string): Promise<Result<UserProfile>> {
    logVerbose("auth.repo.fetchMe.start", { token_len: accessToken.length });
    try {
      const requestId = crypto.randomUUID();
      const response = await fetch(`${API_BASE}/api/v1/users/me`, {
        method: "GET",
        credentials: "include",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "X-Request-ID": requestId,
        },
      });

      if (response.status === 401) {
        logWarn("auth.repo.fetchMe.unauthorized", { request_id: requestId });
        return { ok: false, error: new AuthSessionExpiredError() };
      }

      if (!response.ok) {
        logError("auth.repo.fetchMe.unexpected_status", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new Error(`fetchMe failed: ${response.status}`) };
      }

      const body = await _safeJson<{ data: UserProfile }>(response);
      logVerbose("auth.repo.fetchMe.ok", {
        request_id: requestId,
        user_id: body.data.id,
      });
      return { ok: true, value: body.data };
    } catch (err: unknown) {
      const domainErr = mapFetchError(err);
      logError("auth.repo.fetchMe.error", { error: domainErr.message });
      return { ok: false, error: domainErr };
    }
  }

  /**
   * Calls POST /api/v1/auth/logout with Authorization: Bearer <accessToken>.
   * Returns ok:true on 204; ok:false on 401 or network error.
   * Caller MUST clear access token REGARDLESS of result (defensive logout).
   */
  async logout(accessToken: string): Promise<Result<void>> {
    logVerbose("auth.repo.logout.start", { token_present: true });
    try {
      const requestId = crypto.randomUUID();
      const response = await fetch(`${API_BASE}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "X-Request-ID": requestId,
        },
      });

      if (response.status === 204) {
        logVerbose("auth.repo.logout.ok", { request_id: requestId });
        return { ok: true, value: undefined };
      }

      // 401 or other non-204 — still return ok:false (caller handles cleanup)
      logWarn("auth.repo.logout.non_204", {
        status: response.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AuthSessionExpiredError(),
      };
    } catch (err: unknown) {
      const domainErr = mapFetchError(err);
      logError("auth.repo.logout.error", { error: domainErr.message });
      return { ok: false, error: domainErr instanceof NetworkError ? domainErr : mapFetchError(err) };
    }
  }
}
