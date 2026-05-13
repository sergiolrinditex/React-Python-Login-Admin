/**
 * Hilo People — RequireAuth route guard component.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Route guard that enforces authentication for employee routes.
 *   - status='hydrating' → renders neither children nor redirect (blocks render race).
 *   - status='unauthenticated' → Navigate to /auth/sign-in?next=<safe_current_path>.
 *   - status='authenticated' → renders children.
 *
 * Usage in router.tsx:
 *   <Route element={<RequireAuth><Outlet /></RequireAuth>}>
 *     <Route path="/chat" element={<ChatHomePage />} />
 *   </Route>
 *
 * The `?next=` parameter is validated by getSafeRedirect() (T13) to prevent open-redirect.
 *
 * UX_CONTRACT D.3: while hydrating, render a neutral loading placeholder.
 *   Spinner shape is not mandated; tests assert absence of children/redirect.
 *
 * Non-negotiables §logging: BEFORE + AFTER log on status transitions.
 */

import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "./AuthProvider";
import { getSafeRedirect } from "./redirectAfterAuth";
import { logVerbose } from "../data/logger";

// Route constants (avoid magic strings)
export const ROUTE_AUTH_SIGN_IN = "/auth/sign-in";

/**
 * RequireAuth — Route guard component for authenticated routes.
 *
 * @param children - Content to render when authenticated.
 */
export function RequireAuth({ children }: { children: ReactNode }): React.ReactElement | null {
  const { status } = useAuth();
  const location = useLocation();

  logVerbose("auth.guard.RequireAuth.render", { status });

  if (status === "hydrating") {
    // Race-free: render nothing while AuthProvider resolves mount-time /refresh.
    // UX: no flash of sign-in page before hydration completes.
    return (
      <div aria-label="Loading authentication state" role="status" aria-live="polite">
        {/* Neutral loading placeholder — spinner UI belongs to P03 design slice */}
      </div>
    );
  }

  if (status === "unauthenticated") {
    // Build ?next= with the current location (path + search) for return-to-destination.
    const currentPath = location.pathname + location.search;
    const safeNext = getSafeRedirect(currentPath);
    const redirectTo = `${ROUTE_AUTH_SIGN_IN}?next=${encodeURIComponent(safeNext)}`;

    logVerbose("auth.guard.RequireAuth.redirecting", {
      from: currentPath,
      to: redirectTo,
    });

    return <Navigate to={redirectTo} replace />;
  }

  // status === 'authenticated' — render children
  return <>{children}</>;
}
