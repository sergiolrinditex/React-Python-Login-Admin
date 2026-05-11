/**
 * Hilo People — Application entry point.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *   Write set extension §B (human-approved in planner pack): mounts React app,
 *   imports global CSS, composes Providers + AppRouter.
 *
 * Responsibility: exactly one React root mount. Wraps <Providers> (T002)
 *   inside <StrictMode> and passes <AppRouter> (T004) as children.
 *
 * Import order: tokens.css BEFORE global.css (global.css uses var() from tokens).
 *
 * Key deps:
 *   - react ^19.2.6 (createRoot API, StrictMode).
 *   - ./app/providers (T002 composition root — i18n + QueryClient).
 *   - ./app/router (T004 router — BrowserRouter + Routes).
 *   - ./shared/styles/tokens.css + ./shared/styles/global.css.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Providers } from "./app/providers";
import { AppRouter } from "./app/router";
import "./shared/styles/tokens.css";
import "./shared/styles/global.css";

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------

const rootElement = document.getElementById("root");

if (!rootElement) {
  // This branch is never reached in production (index.html always has #root).
  // Fail loudly in development to catch template regressions early.
  throw new Error(
    "[main.tsx] #root element not found. Ensure index.html contains <div id='root'>.",
  );
}

if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
  console.info("main.mount.start", {
    phase: "P00",
    slice: "P00-S01-T004",
    rootId: "root",
  });
}

createRoot(rootElement).render(
  <StrictMode>
    <Providers>
      <AppRouter />
    </Providers>
  </StrictMode>,
);

if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
  console.info("main.mount.ok", {
    phase: "P00",
    slice: "P00-S01-T004",
  });
}
