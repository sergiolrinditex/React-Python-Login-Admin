/**
 * Hilo People — Application router.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider + route guards / Phase 1.
 *   Updated from P00-S01-T004 (original: /showcase only).
 *   Updated in P03-S01-T001 — replaced SignInStub with real SignInPage (§D-T001-ROUTER).
 *
 * Responsibility: single mount point for the application's route tree.
 *   Exports <AppRouter> which is consumed by main.tsx inside <Providers>.
 *   <AuthProvider> is mounted INSIDE the router tree (not in providers.tsx — P-7).
 *
 * Route inventory:
 *   /showcase          → ShowcasePage (public — design-system demo, dev-only)
 *   /auth/sign-in      → SignInPage (real form, P03-S01-T001)
 *   /admin             → STUB placeholder (wrapped in RequireRole — test surface)
 *   /                  → redirects to /auth/sign-in (P03 default — employees land on login)
 *   *                  → redirects to /auth/sign-in (catch-all; P03 adds 404)
 *
 * P03-S02-T001 adds: /chat, /chat/:conversationId under RequireAuth.
 * P04-S01-T001 adds: real /admin dashboard replacing stub.
 *
 * AuthProvider composition (task pack §I):
 *   INSIDE router.tsx: <AuthProvider> wraps <Routes>.
 *   NOT inside providers.tsx — providers stay route-unaware (P-7 pattern).
 *
 * React Router: package name is "react-router" (v7 — canonical import).
 *   Version: ^7.15.0. Pattern used: <BrowserRouter> + <Routes> (legacy router).
 *   Component-wrapper guard pattern: <RequireAuth><Outlet/></RequireAuth> inside Route element.
 *
 * Journey refs: upstream foundation for J100/J101/J102/J103/J104/J105.
 */

import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router";
import type { ReactNode } from "react";
import ShowcasePage from "../pages/showcase/ShowcasePage";
import SignInPage from "../pages/auth/SignInPage";
import { AuthProvider } from "../features/auth/presentation/AuthProvider";
import { RequireAuth } from "../features/auth/presentation/RequireAuth";
import { RequireRole } from "../features/auth/presentation/RequireRole";

// ---------------------------------------------------------------------------
// Route constants — shared with downstream tasks to avoid magic strings
// ---------------------------------------------------------------------------

/** Route path for the design-system showcase (dev-only, pre-journey). */
export const ROUTE_SHOWCASE = "/showcase";

/** Route path for sign-in page. Form implemented in P03-S01-T001. */
export const ROUTE_AUTH_SIGN_IN = "/auth/sign-in";

/** Route path for admin area. Dashboard implemented in P04-S01-T001. */
export const ROUTE_ADMIN = "/admin";

/** Route path for employee chat home. Implemented in P03-S02-T001. */
export const ROUTE_CHAT = "/chat";

// ---------------------------------------------------------------------------
// Stub page components (placeholders until P04 slices land)
// ---------------------------------------------------------------------------

/**
 * Admin area STUB. Real dashboard in P04-S01-T001.
 * Protected by RequireRole(['people_admin','super_admin']).
 */
function AdminStub(): ReactNode {
  return (
    <div
      style={{ padding: "2rem", fontFamily: "var(--font-sans)" }}
      data-testid="admin-stub"
    >
      <h1>Admin — stub</h1>
      <p>Real admin dashboard implemented in P04-S01-T001.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Application router — mounts BrowserRouter, AuthProvider, and the route tree.
 *
 * AuthProvider is mounted HERE (inside BrowserRouter, above Routes) so that
 * useNavigate() is available inside the provider when needed by logout handlers.
 *
 * @returns The router-wrapped application shell.
 */
export function AppRouter(): ReactNode {
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("AppRouter.render.start", {
      phase: "P03",
      slice: "P03-S01-T001",
      routes: [ROUTE_SHOWCASE, ROUTE_AUTH_SIGN_IN, ROUTE_ADMIN, ROUTE_CHAT],
    });
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes — no auth required */}
          <Route path={ROUTE_SHOWCASE} element={<ShowcasePage />} />
          {/* P03-S01-T001: real SignInPage replaces stub (§D-T001-ROUTER) */}
          <Route path={ROUTE_AUTH_SIGN_IN} element={<SignInPage />} />

          {/* Protected employee routes (P03-S02-T001 adds /chat, /history, /account) */}
          <Route element={<RequireAuth><Outlet /></RequireAuth>}>
            {/* /chat placeholder — real page in P03-S02-T001 */}
            <Route
              path={ROUTE_CHAT}
              element={
                <div data-testid="chat-placeholder" style={{ padding: "2rem" }}>
                  Chat home — implemented in P03-S02-T001
                </div>
              }
            />
          </Route>

          {/* Admin routes — people_admin or super_admin only */}
          <Route
            element={
              <RequireRole roles={["people_admin", "super_admin"]}>
                <Outlet />
              </RequireRole>
            }
          >
            <Route path={ROUTE_ADMIN} element={<AdminStub />} />
          </Route>

          {/* Default redirect — employees land on sign-in (P03-S01-T001, §D-T001-ROUTER) */}
          <Route path="/" element={<Navigate to={ROUTE_AUTH_SIGN_IN} replace />} />

          {/* Catch-all — redirects to sign-in; P04 adds proper 404 */}
          <Route path="*" element={<Navigate to={ROUTE_AUTH_SIGN_IN} replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
