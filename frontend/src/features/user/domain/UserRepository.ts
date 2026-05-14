/**
 * Hilo People — User domain repository port (interface).
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Port (interface) for user operations.
 *   Defines what operations the domain needs; data/userRepository.ts implements them.
 *   No imports of React, no fetch, no external libs — pure domain boundary.
 *
 * Clean Architecture: presentation/ depends on this port, not on userRepository.ts directly.
 *
 * Operations:
 *   - getMe(): GET /api/v1/users/me — read profile + employee_profile.
 *   - updateLanguage(lang): PATCH /api/v1/users/me/language — returns 200 + full UserProfile.
 *
 * Source: TECHNICAL_GUIDE §6.1 (endpoint contracts), instrucciones.md §3.2.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type { UserProfile, LanguageCode, UserError } from "./types";

// Re-export Result for convenience in the data and presentation layers.
export type { Result };

// ---------------------------------------------------------------------------
// Repository port
// ---------------------------------------------------------------------------

/**
 * Port interface for user profile operations.
 * Implemented by data/userRepository.ts.
 * Consumed by presentation/useMe.ts and presentation/useUpdateLanguage.ts.
 */
export interface IUserRepository {
  /**
   * Calls GET /api/v1/users/me.
   * Returns UserProfile including employee_profile (null for admin users).
   *
   * Errors:
   *   - UserAuthExpiredError (401 — after authFetch refresh exhausted)
   *   - UserNetworkError (fetch-level failure)
   *   - UserServerError (5xx)
   *
   * @returns Result<UserProfile, UserError>
   */
  getMe(): Promise<Result<UserProfile, UserError>>;

  /**
   * Calls PATCH /api/v1/users/me/language with {language: LanguageCode}.
   * Backend returns 200 with FULL UserProfile body (not 204).
   * See DISCREPANCY-1 resolved in P01-S02-T007 handoff.
   *
   * Errors:
   *   - UserValidationError (400 or 422 — invalid language code)
   *   - UserAuthExpiredError (401 — after authFetch refresh exhausted)
   *   - UserForbiddenError (403 — insufficient role)
   *   - UserNetworkError (fetch-level failure)
   *   - UserServerError (5xx)
   *
   * @param language - Must be 'es', 'en', or 'fr'. Backend strict whitelist.
   * @returns Result<UserProfile, UserError> where UserProfile.preferred_language === language.
   */
  updateLanguage(language: LanguageCode): Promise<Result<UserProfile, UserError>>;
}
