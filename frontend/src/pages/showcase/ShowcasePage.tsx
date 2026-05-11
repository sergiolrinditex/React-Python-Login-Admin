/**
 * Hilo People — Design System Showcase Page (orchestrator).
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *   Updated in P00-S01-T005: added I18nDemoSection import (WRITE_SET_DRIFT controlled).
 *
 * Responsibility: route entry for /showcase. Renders all 9 base component sections
 *   defined in ShowcaseSections.tsx plus the T005 i18n demo section.
 *   Statically loaded — no async, no auth guard.
 *
 * i18n_checked: yes (T005) — i18n demo section added; rest of page is English
 *   copy for the design-system showcase (not user-facing text).
 *
 * Page-level states (all N/A per §E):
 *   - loading: synchronous static load — N/A.
 *   - success: no submission — N/A.
 *   - permission_denied: dev-only, not auth-guarded — N/A.
 *   Component-level states ARE demonstrated in ShowcaseSections.
 *
 * WRITE_SET_DRIFT (T005): I18nDemoSection added here to satisfy verify_mode=human.
 *   The i18n section is append-only; the original 9 sections are unchanged.
 *   Justified by: showcase is the only canonical dev surface in P0 (T004).
 *   Precedent: T001/T002 write_set extensions approved by validator.
 *
 * Key deps: React 19, ShowcaseSections.tsx, I18nDemoSection.tsx, tokens.css (via main.tsx).
 */

import type { ReactNode } from "react";
import { ShowcaseSections } from "./ShowcaseSections";
import { I18nDemoSection } from "./I18nDemoSection";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Design-system showcase — /showcase route entry point.
 *
 * @returns The showcase page.
 */
export default function ShowcasePage(): ReactNode {
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("ShowcasePage.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      route: "/showcase",
    });
  }

  return (
    <div
      style={{
        backgroundColor: "var(--color-bg)",
        minHeight: "100vh",
        padding: "3rem 2rem",
        maxWidth: "900px",
        margin: "0 auto",
      }}
    >
      {/* Page header */}
      <header style={{ marginBottom: "4rem" }}>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "2.5rem",
            color: "var(--color-ink)",
            letterSpacing: "-0.02em",
            marginBottom: "0.5rem",
          }}
        >
          Design System
        </h1>
        <p
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.875rem",
            color: "var(--color-ink)",
            opacity: 0.55,
          }}
        >
          Hilo People — P00-S01-T004 — All 9 base components, all applicable states
        </p>
      </header>

      <ShowcaseSections />

      {/* Section 10: i18n demo (T005 addition — WRITE_SET_DRIFT controlled) */}
      <I18nDemoSection />

      {/* Showcase footer */}
      <footer
        style={{
          borderTop: "var(--hairline)",
          paddingTop: "1.5rem",
          fontFamily: "var(--font-sans)",
          fontSize: "0.6875rem",
          letterSpacing: "var(--tracking-label)",
          textTransform: "uppercase",
          color: "var(--color-ink)",
          opacity: 0.3,
        }}
      >
        Hilo People · Design System · P00-S01-T004 + T005
      </footer>
    </div>
  );
}
