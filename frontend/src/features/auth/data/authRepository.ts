/**
 * Hilo People — Auth repository (concrete HTTP adapter).
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *   Extended in P03-S01-T001 — SignInPage: added signIn() method.
 *
 * Responsibility: Concrete implementation of IAuthRepository (domain port).
 *   Calls the backend auth/user endpoints. All calls use authFetch (credentials:'include',
 *   X-Request-ID, Bearer injection, single-flight 401 interceptor).
 *
 * Clean Architecture: this is the DATA layer. Presentation/ depends on the port
 *   (IAuthRepository) NOT on this file directly.
 *
 * Endpoints consumed (TECHNICAL_GUIDE §6.2):
 *   - POST /api/v1/auth/sign-in  → email+password; returns SignInOutcome (no-MFA or MFA).
 *   - POST /api/v1/auth/refresh  → cookie-only; returns new access_token.
 *   - GET  /api/v1/users/me      → Bearer required; returns UserProfile.
 *   - POST /api/v1/auth/logout   → Bearer required; 204 on success.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 * Security: NEVER log password. NEVER log full token. Log metadata only.
 */

import type { IAuthRepository, Result, SignInRequest, SignInOutcome } from "../domain/AuthRepository";
import type { UserProfile } from "../domain/types";
import {
  AuthSessionExpiredError,
  NetworkError,
  mapFetchError,
  InvalidCredentialsError,
  AccountLockedError,
  RateLimitedError,
  SigninValidationError,
  SigninInternalError,
} from "./errors";
import { setAccessToken } from "./accessTokenStore";
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

  // ---------------------------------------------------------------------------
  // signIn — P03-S01-T001
  // ---------------------------------------------------------------------------

  /**
   * Calls POST /api/v1/auth/sign-in with email+password.
   * Maps success shapes (no-MFA + MFA challenge) to SignInOutcome.
   *
   * Security: uses plain fetch (not authFetch) because sign-in is public endpoint —
   *   no Bearer header needed; credentials:'include' ensures cookies are sent.
   *   X-Request-ID injected for end-to-end correlation.
   *
   * D-T001-USERFETCH-ON-SUCCESS: on no-MFA success, calls fetchMe() inline to
   *   load the UserProfile before returning SignInOutcome{kind:'success'}.
   *
   * Logging contract (§7 of pack):
   *   BEFORE: email_domain only (never local part), password_len, request_id.
   *   AFTER ok_no_mfa: token_len, expires_in, request_id.
   *   AFTER mfa: challenge_token_len, expires_in, request_id.
   *   WARN on 401, 423, 429.
   *   ERROR on network + unexpected status.
   *   NEVER: password, full token, full email.
   */
  async signIn(req: SignInRequest): Promise<Result<SignInOutcome>> {
    const requestId = crypto.randomUUID();
    const emailDomain = req.email.includes("@") ? req.email.split("@")[1] : "unknown";

    logVerbose("auth.signin.submit.start", {
      email_domain: emailDomain,
      password_len: req.password.length,
      request_id: requestId,
    });

    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/sign-in`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": requestId,
        },
        body: JSON.stringify({ email: req.email, password: req.password }),
      });

      if (response.status === 401) {
        logWarn("auth.signin.submit.invalid_credentials", {
          status: 401,
          request_id: requestId,
        });
        return { ok: false, error: new InvalidCredentialsError() };
      }

      if (response.status === 423) {
        logWarn("auth.signin.submit.locked", {
          status: 423,
          request_id: requestId,
        });
        return { ok: false, error: new AccountLockedError() };
      }

      if (response.status === 429) {
        const retryAfterHeader = response.headers.get("Retry-After");
        const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : 0;
        logWarn("auth.signin.submit.rate_limited", {
          status: 429,
          retry_after: retryAfter,
          request_id: requestId,
        });
        return { ok: false, error: new RateLimitedError(isNaN(retryAfter) ? 0 : retryAfter) };
      }

      if (response.status === 400) {
        logWarn("auth.signin.submit.validation", {
          status: 400,
          request_id: requestId,
        });
        return { ok: false, error: new SigninValidationError() };
      }

      if (!response.ok) {
        logError("auth.signin.submit.unexpected", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new SigninInternalError(response.status) };
      }

      const body = await _safeJson<{
        data: {
          mfa_required: boolean;
          access_token?: string;
          token_type?: string;
          expires_in?: number;
          mfa_challenge_token?: string;
        };
      }>(response);

      if (body.data.mfa_required) {
        const challengeToken = body.data.mfa_challenge_token ?? "";
        const expiresIn = body.data.expires_in ?? 300;
        logVerbose("auth.signin.submit.mfa_required", {
          challenge_token_len: challengeToken.length,
          expires_in: expiresIn,
          request_id: requestId,
        });
        return {
          ok: true,
          value: { kind: "mfa", challengeToken, expiresIn },
        };
      }

      // No-MFA path: access_token present; call fetchMe before returning user
      const accessToken = body.data.access_token ?? "";
      const expiresIn = body.data.expires_in ?? 1800;

      logVerbose("auth.signin.submit.ok_no_mfa", {
        token_len: accessToken.length,
        expires_in: expiresIn,
        request_id: requestId,
      });

      // D-T001-USERFETCH-ON-SUCCESS: set token then fetchMe before signInAccepted
      setAccessToken(accessToken);
      const meResult = await this.fetchMe(accessToken);
      if (!meResult.ok) {
        logError("auth.signin.submit.fetchme_failed", {
          error: meResult.error.message,
          request_id: requestId,
        });
        return { ok: false, error: meResult.error };
      }

      return {
        ok: true,
        value: { kind: "success", accessToken, user: meResult.value },
      };
    } catch (err: unknown) {
      if (
        err instanceof InvalidCredentialsError ||
        err instanceof AccountLockedError ||
        err instanceof RateLimitedError ||
        err instanceof SigninValidationError ||
        err instanceof SigninInternalError
      ) {
        return { ok: false, error: err };
      }
      const domainErr = mapFetchError(err);
      logError("auth.signin.submit.network", { error: domainErr.message });
      return { ok: false, error: domainErr instanceof NetworkError ? domainErr : new NetworkError(domainErr.message) };
    }
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
