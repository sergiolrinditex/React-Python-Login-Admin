/**
 * Hilo People — User feature public barrel.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Re-exports the public API surface of the user feature.
 *   Consumers import from "features/user" — not from internal subpaths.
 *
 * Exports:
 *   - Domain types: UserProfile, EmployeeProfile, LanguageCode, UserError (+ classes).
 *   - Repository: UserRepository class + userRepository singleton.
 *   - Hooks: useMe, useUpdateLanguage.
 *   - Query key: ME_QUERY_KEY (for manual invalidation by other features).
 */

// Domain types
export type { UserProfile, EmployeeProfile, LanguageCode, UserError } from "./domain/types";
export {
  UserValidationError,
  UserAuthExpiredError,
  UserForbiddenError,
  UserNetworkError,
  UserServerError,
} from "./domain/types";

// Repository
export type { IUserRepository } from "./domain/UserRepository";
export { UserRepository, userRepository } from "./data/userRepository";

// Hooks
export { useMe, ME_QUERY_KEY } from "./presentation/useMe";
export { useUpdateLanguage } from "./presentation/useUpdateLanguage";
