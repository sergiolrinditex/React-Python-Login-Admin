/**
 * Hilo People — RequireRole route guard component.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Role-based route guard that wraps RequireAuth.
 *   Allows access only when the authenticated user has at least one of the required roles.
 *   On role mismatch: redirects to /chat (safe fallback for employees).
 *
 * Usage in router.tsx:
 *   <Route element={<RequireRole roles={['people_admin','super_admin']}><Outlet/></RequireRole>}>
 *     <Route path="/admin" element={<AdminDashboard />} />
 *   </Route>
 *
 * Behaviour:
 *   - status='hydrating' → delegates to RequireAuth (renders neutral placeholder).
 *   - status='unauthenticated' → delegates to RequireAuth (redirects to /auth/sign-in?next=).
 *   - status='authenticated' + role mismatch → redirects to /chat (KISS — no toast).
 *   - status='authenticated' + role match → renders children.
 *
 * Source: instrucciones.md §3.3 — RequireRole is polymorphic;
 *   no named RequireAdmin/RequireAuditor aliases (YAGNI per task pack §D.1).
 *
 * Non-negotiables §logging: BEFORE + AFTER on role check.
 */

import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { useAuth } from "./AuthProvider";
import { RequireAuth } from "./RequireAuth";
import { logVerbose } from "../data/logger";

/** Safe fallback when role check fails (employee home). */
const ROLE_DENIED_REDIRECT = "/chat";

/**
 * RequireRole — Role-based route guard.
 *
 * @param roles - List of roles that are allowed access (any-of semantics: OR).
 * @param children - Content to render when role is satisfied.
 */
export function RequireRole({
  roles,
  children,
}: {
  roles: string[];
  children: ReactNode;
}): React.ReactElement | null {
  const { status, user } = useAuth();

  logVerbose("auth.guard.RequireRole.render", { status, required_roles: roles });

  // Delegate hydrating + unauthenticated to RequireAuth
  if (status !== "authenticated") {
    return <RequireAuth>{children}</RequireAuth>;
  }

  // Check role intersection (any-of semantics)
  const userRoles = user?.roles ?? [];
  const hasRole = roles.some((r) => userRoles.includes(r));

  if (!hasRole) {
    logVerbose("auth.guard.RequireRole.denied", {
      user_id: user?.id,
      user_roles: userRoles,
      required_roles: roles,
    });
    return <Navigate to={ROLE_DENIED_REDIRECT} replace />;
  }

  logVerbose("auth.guard.RequireRole.allowed", { user_id: user?.id });
  return <>{children}</>;
}
