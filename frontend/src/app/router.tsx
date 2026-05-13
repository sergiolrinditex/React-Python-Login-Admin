/**
 * Hilo People — Application router.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider + route guards / Phase 1.
 *   Updated from P00-S01-T004 (original: /showcase only).
 *
 * Responsibility: single mount point for the application's route tree.
 *   Exports <AppRouter> which is consumed by main.tsx inside <Providers>.
 *   <AuthProvider> is mounted INSIDE the router tree (not in providers.tsx — P-7).
 *
 * Route inventory (this slice):
 *   /showcase          → ShowcasePage (public — design-system demo, dev-only)
 *   /auth/sign-in      → STUB placeholder (form lives in P03-S01-T001)
 *   /admin             → STUB placeholder (wrapped in RequireRole — test surface)
 *   /                  → redirects to /showcase (temp; P03 replaces with /auth/sign-in)
 *   *                  → redirects to /showcase (catch-all; P03 adds 404)
 *
 * P03-S01-T001 adds: real SignInPage form replacing the /auth/sign-in stub.
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
 *   Loader-based redirect requires createBrowserRouter (data-router API), deferred to P03.
 *
 * Journey refs: upstream foundation for J100/J101/J102/J103/J104/J105.
 */

import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router";
import type { ReactNode } from "react";
import ShowcasePage from "../pages/showcase/ShowcasePage";
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
// Stub page components (placeholders until P03/P04 slices land)
// ---------------------------------------------------------------------------

/**
 * Sign-in page STUB. The real form (email + password inputs, layout, copy) lives in P03-S01-T001.
 * This stub exists solely to make RequireAuth redirects browser-verifiable.
 * Removable (non-breaking) when P03-S01-T001 replaces it via the same route path.
 */
function SignInStub(): ReactNode {
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("[auth] route.sign-in-stub.render", {
      note: "Real form in P03-S01-T001",
    });
  }
  return (
    <div
      style={{ padding: "2rem", fontFamily: "var(--font-sans)" }}
      data-testid="sign-in-stub"
    >
      <h1>Sign in — stub</h1>
      <p>Real sign-in form implemented in P03-S01-T001.</p>
      <small>
        Check <code>?next=</code> in URL for return-to-destination:{" "}
        <code>{new URLSearchParams(window.location.search).get("next") ?? "(none)"}</code>
      </small>
    </div>
  );
}

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
      phase: "P01",
      slice: "P01-S03-T001",
      routes: [ROUTE_SHOWCASE, ROUTE_AUTH_SIGN_IN, ROUTE_ADMIN],
    });
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes — no auth required */}
          <Route path={ROUTE_SHOWCASE} element={<ShowcasePage />} />
          <Route path={ROUTE_AUTH_SIGN_IN} element={<SignInStub />} />

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

          {/* Default redirect — P03 replaces with /auth/sign-in redirect */}
          <Route path="/" element={<Navigate to={ROUTE_SHOWCASE} replace />} />

          {/* Catch-all — P03 adds a proper 404 page */}
          <Route path="*" element={<Navigate to={ROUTE_SHOWCASE} replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
