/**
 * Hilo People — Auth feature public barrel export.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Single import surface for downstream slices (P03-S01-T001, etc.).
 *   Only export what downstream consumers genuinely need.
 *   Internal data-layer details (httpClient, logger internals) stay unexported.
 *
 * YAGNI: only export what is consumed by router.tsx and upcoming page slices.
 */

// Domain types
export type { UserProfile, AuthSession, AuthStatus, Role, EmployeeProfile } from "./domain/types";
export type { IAuthRepository, Result } from "./domain/AuthRepository";

// Data layer — only what pages need to call authFetch directly
export { authFetch } from "./data/httpClient";
export { getAccessToken, setAccessToken, clearAccessToken, hasAccessToken } from "./data/accessTokenStore";
export { AuthSessionExpiredError, NetworkError } from "./data/errors";

// Presentation layer — public components and hooks
export { AuthProvider, useAuth } from "./presentation/AuthProvider";
export type { AuthContextValue } from "./presentation/AuthProvider";
export { RequireAuth, ROUTE_AUTH_SIGN_IN } from "./presentation/RequireAuth";
export { RequireRole } from "./presentation/RequireRole";
export { getSafeRedirect, DEFAULT_SAFE_REDIRECT } from "./presentation/redirectAfterAuth";
