/**
 * Hilo People — Application router.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: single mount point for the application's route tree.
 *   Exports <AppRouter> which is consumed by main.tsx inside <Providers>.
 *   This slice registers /showcase. Real journey routes (/auth/*, /chat, /admin/**)
 *   are added in P03-S01 and P04-S01 respectively.
 *
 * Composition rule (planner MEMORY P-7):
 *   <BrowserRouter> is mounted HERE (not in providers.tsx). Providers.tsx
 *   remains route-unaware and easier to unit-test.
 *
 * React Router: package name is "react-router" (v7 — canonical import; NOT
 *   "react-router-dom" which is the legacy v6 name). Confirmed by T002 install.
 *   Version: ^7.15.0 (declared in frontend/package.json).
 *
 * Journey refs: upstream foundation for J100/J101/J102/J103/J104/J105.
 *   No journey is closed by this slice.
 *
 * Key deps: react-router ^7.15.0, React 19.
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import ShowcasePage from "../pages/showcase/ShowcasePage";
import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Route constants — shared with downstream tasks to avoid magic strings
// ---------------------------------------------------------------------------

/** Route path for the design-system showcase (dev-only, pre-journey). */
export const ROUTE_SHOWCASE = "/showcase";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Application router — mounts BrowserRouter and declares the route tree.
 *
 * Routes registered in this slice:
 *   /showcase         → ShowcasePage (design-system demo, all 9 base components)
 *   /                 → redirects to /showcase (temporary; P03 replaces with /auth/sign-in)
 *
 * P03-S01-T001 adds: /auth/sign-in, /auth/sign-up, /auth/forgot-password
 * P03-S02-T001 adds: /chat, /chat/:conversationId
 * P04-S01-T001 adds: /admin, /admin/dashboard
 * P04-S02-T001 adds: /admin/documents
 * ...
 *
 * @returns The router-wrapped application shell.
 */
export function AppRouter(): ReactNode {
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("AppRouter.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      routes: [ROUTE_SHOWCASE],
    });
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Design-system showcase — visible at /showcase (dev-only surface) */}
        <Route path={ROUTE_SHOWCASE} element={<ShowcasePage />} />

        {/* Default redirect — P03 replaces with protected /auth/sign-in redirect */}
        <Route path="/" element={<Navigate to={ROUTE_SHOWCASE} replace />} />

        {/* Catch-all — P03 adds a proper 404 page */}
        <Route path="*" element={<Navigate to={ROUTE_SHOWCASE} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
