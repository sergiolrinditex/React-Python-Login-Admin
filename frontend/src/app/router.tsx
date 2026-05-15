/**
 * Hilo People — Application router.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider + route guards / Phase 1.
 *   Updated from P00-S01-T004 (original: /showcase only).
 *   Updated in P03-S01-T001 — replaced SignInStub with real SignInPage (§D-T001-ROUTER).
 *   WRITE_SET_DRIFT §D-T001-ROUTE (P03-S02-T001): wired /chat to ChatHomePage;
 *     updated / and * redirects so authenticated users land on /chat.
 *   Updated in P03-S01-T002 — added /auth/sign-up route wired to SignUpPage (§D-T002-ROUTER).
 *   Updated in P03-S02-T003 — added /history route wired to HistoryPage (§D-T003-ROUTER).
 *
 * Responsibility: single mount point for the application's route tree.
 *   Exports <AppRouter> which is consumed by main.tsx inside <Providers>.
 *   <AuthProvider> is mounted INSIDE the router tree (not in providers.tsx — P-7).
 *
 * Route inventory:
 *   /showcase          → ShowcasePage (public — design-system demo, dev-only)
 *   /auth/sign-in      → SignInPage (real form, P03-S01-T001)
 *   /auth/sign-up      → SignUpPage (real form, P03-S01-T002)
 *   /chat              → ChatHomePage (employee, RequireAuth) — P03-S02-T001
 *   /chat/:conversationId → placeholder (P03-S02-T002 adds real ConversationPage)
 *   /history              → HistoryPage (employee history, RequireAuth) — P03-S02-T003
 *   /admin             → STUB placeholder (wrapped in RequireRole — test surface)
 *   /                  → RootRedirect: authenticated→/chat, unauthenticated→/auth/sign-in
 *   *                  → redirects to / (catch-all; uses RootRedirect logic)
 *
 * P03-S01-T001 adds: real SignInPage form replacing the /auth/sign-in stub.
 * P03-S01-T002 adds: real SignUpPage form at /auth/sign-up.
 * P03-S02-T001 adds: /chat real page; updates / and * redirects for authed users.
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
import SignUpPage from "../pages/auth/SignUpPage";
import ChatHomePage from "../pages/chat/ChatHomePage";
import HistoryPage from "../pages/chat/HistoryPage";
import { AuthProvider } from "../features/auth/presentation/AuthProvider";
import { useAuth } from "../features/auth/presentation/AuthProvider";
import { RequireAuth } from "../features/auth/presentation/RequireAuth";
import { RequireRole } from "../features/auth/presentation/RequireRole";

// ---------------------------------------------------------------------------
// Route constants — shared with downstream tasks to avoid magic strings
// ---------------------------------------------------------------------------

/** Route path for the design-system showcase (dev-only, pre-journey). */
export const ROUTE_SHOWCASE = "/showcase";

/** Route path for sign-in page. Form implemented in P03-S01-T001. */
export const ROUTE_AUTH_SIGN_IN = "/auth/sign-in";

/** Route path for sign-up page. Form implemented in P03-S01-T002. */
export const ROUTE_AUTH_SIGN_UP = "/auth/sign-up";

/** Route path for admin area. Dashboard implemented in P04-S01-T001. */
export const ROUTE_ADMIN = "/admin";

/** Route path for employee chat home. Implemented in P03-S02-T001. */
export const ROUTE_CHAT = "/chat";

/** Route path for employee conversation history. Implemented in P03-S02-T003. §D-T003-ROUTER */
export const ROUTE_HISTORY = "/history";

// ---------------------------------------------------------------------------
// RootRedirect — auth-aware redirect for "/" and "*" catch-all
// D-T001-ROUTE: authenticated → /chat; unauthenticated → /auth/sign-in;
//   hydrating → null (RequireAuth handles the loading state for guarded routes).
// D-T001-DEEPLINK-AUTHED-DEFAULT: direct navigation to "/" always lands on /chat.
// ---------------------------------------------------------------------------

/**
 * Root redirect component. Checks auth status and redirects accordingly.
 * status='hydrating' → renders nothing (avoids flash to sign-in).
 * status='authenticated' → /chat (employee home per D-T001-ROUTE).
 * status='unauthenticated' → /auth/sign-in.
 */
function RootRedirect(): ReactNode {
  const { status } = useAuth();

  if (status === "hydrating") {
    return null;
  }

  if (status === "authenticated") {
    return <Navigate to={ROUTE_CHAT} replace />;
  }

  return <Navigate to={ROUTE_AUTH_SIGN_IN} replace />;
}

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
      slice: "P03-S02-T003",
      routes: [ROUTE_SHOWCASE, ROUTE_AUTH_SIGN_IN, ROUTE_AUTH_SIGN_UP, ROUTE_CHAT, ROUTE_HISTORY, ROUTE_ADMIN],
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
          {/* P03-S01-T002: real SignUpPage (§D-T002-ROUTER) */}
          <Route path={ROUTE_AUTH_SIGN_UP} element={<SignUpPage />} />

          {/* Protected employee routes */}
          <Route element={<RequireAuth><Outlet /></RequireAuth>}>
            {/* /chat — real ChatHomePage (P03-S02-T001) */}
            <Route path={ROUTE_CHAT} element={<ChatHomePage />} />
            {/* /history — real HistoryPage (P03-S02-T003 §D-T003-ROUTER) */}
            <Route path={ROUTE_HISTORY} element={<HistoryPage />} />
            {/*
             * /chat/:conversationId — placeholder for P03-S02-T002 (ConversationPage).
             * D-T001-OUTAGE-OF-CHAT-T002: navigate succeeds; unknown path bounces to /chat.
             * This route must exist to prevent the catch-all intercepting /chat/:id navigations.
             */}
            <Route
              path={`${ROUTE_CHAT}/:conversationId`}
              element={<Navigate to={ROUTE_CHAT} replace />}
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

          {/*
           * Root redirect — D-T001-ROUTE + D-T001-DEEPLINK-AUTHED-DEFAULT.
           * authenticated → /chat; unauthenticated → /auth/sign-in; hydrating → null.
           */}
          <Route path="/" element={<RootRedirect />} />

          {/* Catch-all — redirect to root which applies RootRedirect logic. */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
