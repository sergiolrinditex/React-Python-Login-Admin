/**
 * Hilo People — User repository (concrete HTTP adapter).
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Implements IUserRepository via authFetch.
 *   getMe()         → GET  /api/v1/users/me  → Result<UserProfile, UserError>
 *   updateLanguage() → PATCH /api/v1/users/me/language → Result<UserProfile, UserError>
 *
 * Contract notes:
 *   - PATCH /users/me/language returns 200 + full UserProfile body (NOT 204).
 *     Pinned by DISCREPANCY-1 resolved in P01-S02-T007 + backend/app/users/schemas.py:127-140.
 *   - Uses relative URLs per ADR-002 (Vite proxy in dev, Nginx in prod).
 *   - Uses authFetch (Bearer injection, X-Request-ID, single-flight 401 refresh).
 *
 * Security:
 *   - NEVER log email, full_name, or token values.
 *   - Log only: user_id, language code (safe), status code, request_id.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 */

import type { IUserRepository, Result } from "../domain/UserRepository";
import type { UserProfile, LanguageCode, UserError } from "../domain/types";
import {
  UserValidationError,
  UserAuthExpiredError,
  UserForbiddenError,
  UserNetworkError,
  UserServerError,
} from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// URL constants (relative — ADR-002)
// ---------------------------------------------------------------------------

const ME_URL = "/api/v1/users/me";
const LANGUAGE_URL = "/api/v1/users/me/language";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Error mapper for unknown fetch errors
// ---------------------------------------------------------------------------

/**
 * Maps an unknown caught value to a typed UserError.
 *
 * @param err - Raw caught value.
 * @returns A typed UserError.
 */
function mapUserError(err: unknown): UserError {
  if (err instanceof UserValidationError) return err;
  if (err instanceof UserAuthExpiredError) return err;
  if (err instanceof UserForbiddenError) return err;
  if (err instanceof UserNetworkError) return err;
  if (err instanceof UserServerError) return err;
  if (err instanceof TypeError) return new UserNetworkError(err.message, err);
  if (err instanceof Error) return new UserNetworkError(err.message, err);
  return new UserNetworkError("Unknown error");
}

// ---------------------------------------------------------------------------
// Repository implementation
// ---------------------------------------------------------------------------

/**
 * Concrete HTTP adapter for user profile operations.
 * Implements IUserRepository using authFetch.
 *
 * Instantiated once per consumer; no singleton — callers create as needed.
 */
export class UserRepository implements IUserRepository {
  /**
   * Fetches the current user's profile.
   * GET /api/v1/users/me (Auth: Bearer)
   *
   * @param onAuthFailure - Called when session cannot be recovered (401 exhausted).
   * @returns Result<UserProfile, UserError>
   */
  async getMe(onAuthFailure?: () => void): Promise<Result<UserProfile, UserError>> {
    logVerbose("user.repo.getMe.start");

    try {
      const response = await authFetch(
        ME_URL,
        { method: "GET" },
        { onAuthFailure: onAuthFailure ?? (() => void 0) },
      );

      const requestId = response.headers.get("x-request-id") ?? "unknown";

      if (response.status === 401) {
        logWarn("user.repo.getMe.auth_expired", { status: 401, request_id: requestId });
        return { ok: false, error: new UserAuthExpiredError() };
      }

      if (response.status === 403) {
        logWarn("user.repo.getMe.forbidden", { status: 403, request_id: requestId });
        return { ok: false, error: new UserForbiddenError() };
      }

      if (!response.ok) {
        logError("user.repo.getMe.server_error", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new UserServerError(response.status) };
      }

      const body = await _safeJson<{ data: UserProfile }>(response);
      logVerbose("user.repo.getMe.ok", {
        user_id: body.data.id,
        preferred_language: body.data.preferred_language,
        request_id: requestId,
      });

      return { ok: true, value: body.data };
    } catch (err: unknown) {
      const domainErr = mapUserError(err);
      logError("user.repo.getMe.error", {
        error: domainErr.code,
        message: domainErr.message,
      });
      return { ok: false, error: domainErr };
    }
  }

  /**
   * Updates the current user's preferred language.
   * PATCH /api/v1/users/me/language (Auth: Bearer)
   * Backend returns 200 + full UserProfile body (not 204 — DISCREPANCY-1 resolved).
   *
   * @param language - Target language code: 'es', 'en', or 'fr'.
   * @param onAuthFailure - Called when session cannot be recovered.
   * @returns Result<UserProfile, UserError> where result.preferred_language === language.
   */
  async updateLanguage(
    language: LanguageCode,
    onAuthFailure?: () => void,
  ): Promise<Result<UserProfile, UserError>> {
    logVerbose("user.repo.updateLanguage.start", { language });

    try {
      const response = await authFetch(
        LANGUAGE_URL,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ language }),
        },
        { onAuthFailure: onAuthFailure ?? (() => void 0) },
      );

      const requestId = response.headers.get("x-request-id") ?? "unknown";

      if (response.status === 400 || response.status === 422) {
        logWarn("user.repo.updateLanguage.validation_error", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new UserValidationError() };
      }

      if (response.status === 401) {
        logWarn("user.repo.updateLanguage.auth_expired", { status: 401, request_id: requestId });
        return { ok: false, error: new UserAuthExpiredError() };
      }

      if (response.status === 403) {
        logWarn("user.repo.updateLanguage.forbidden", { status: 403, request_id: requestId });
        return { ok: false, error: new UserForbiddenError() };
      }

      if (!response.ok) {
        logError("user.repo.updateLanguage.server_error", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new UserServerError(response.status) };
      }

      const body = await _safeJson<{ data: UserProfile }>(response);
      logVerbose("user.repo.updateLanguage.ok", {
        user_id: body.data.id,
        preferred_language: body.data.preferred_language,
        request_id: requestId,
      });

      return { ok: true, value: body.data };
    } catch (err: unknown) {
      const domainErr = mapUserError(err);
      logError("user.repo.updateLanguage.error", {
        error: domainErr.code,
        message: domainErr.message,
      });
      return { ok: false, error: domainErr };
    }
  }
}

// ---------------------------------------------------------------------------
// Default singleton instance for DI in hooks
// ---------------------------------------------------------------------------

/** Default UserRepository instance — used by hooks unless overridden in tests. */
export const userRepository = new UserRepository();
