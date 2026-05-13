/**
 * Hilo People — Auth domain types (entities and value objects).
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Pure TypeScript types for the auth domain.
 *   No React, no external libraries, no fetch, no side effects.
 *   Downstream layers (data/, presentation/) depend on these types.
 *
 * Source: TECHNICAL_GUIDE §6.2 (UserProfile shape), §10.2 (token policy),
 *         instrucciones.md §3.3 (roles).
 *
 * Security contract (TECHNICAL_GUIDE §10.2):
 *   - Access token is OPAQUE string — never decoded by frontend.
 *   - Frontend NEVER reads the refresh cookie — it is HttpOnly.
 */

// ---------------------------------------------------------------------------
// Roles (instrucciones.md §3.3)
// ---------------------------------------------------------------------------

/** Valid user roles in the system. */
export type Role =
  | "employee"
  | "people_admin"
  | "people_auditor"
  | "super_admin";

// ---------------------------------------------------------------------------
// UserProfile (TECHNICAL_GUIDE §6.2, T007 backend contract)
// ---------------------------------------------------------------------------

/** Employee profile sub-object returned from GET /api/v1/users/me. null for admins. */
export interface EmployeeProfile {
  employee_id: string;
  brand: string;
  society: string;
  center: string;
  country: string;
  department: string;
}

/**
 * User profile shape as returned by GET /api/v1/users/me.
 * Source: backend/app/users/schemas.py (T007).
 * Note: roles defaults to ['employee'] when no DB rows exist for the user.
 */
export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  status: "active" | "inactive" | "pending" | "locked";
  preferred_language: "es" | "en" | "fr";
  roles: string[];
  employee_profile: EmployeeProfile | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Auth status (UX_CONTRACT §3)
// ---------------------------------------------------------------------------

/**
 * Auth provider hydration status.
 *
 * - hydrating: mount-time /refresh call in progress; guards block render.
 * - authenticated: valid session, user populated.
 * - unauthenticated: no valid refresh cookie or refresh failed.
 */
export type AuthStatus = "hydrating" | "authenticated" | "unauthenticated";

// ---------------------------------------------------------------------------
// Auth session (immutable state snapshot)
// ---------------------------------------------------------------------------

/**
 * Immutable auth session state snapshot.
 * The access token is stored only here (module-level, not in AuthSession objects).
 * AuthSession is the value exposed by useAuth().
 */
export interface AuthSession {
  status: AuthStatus;
  user: UserProfile | null;
}
