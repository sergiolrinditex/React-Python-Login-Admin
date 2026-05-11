/**
 * Hilo People — MobileFrame component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: mobile shell wrapper (402 px wide per UX_CONTRACT §7).
 *   Provides the outer crude-background container and inner paper surface
 *   without any rounded corners. Used on: SignInPage, SignUpPage,
 *   ForgotPasswordPage, ChatHomePage.
 *   Journey refs: J100 (login), J101 (chat), J102 (document upload mobile).
 *
 * Token usage: --color-bg (outer), --color-paper (inner), --hairline.
 * Prohibitions: NO border-radius, NO box-shadow, NO decorative shadows.
 *
 * Accessibility:
 *   - role="main" optional via prop (page-level semantics).
 *   - Inner children handle their own a11y.
 *
 * Key deps: React 19, CSS custom properties from tokens.css.
 */

import type { CSSProperties, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MobileFrameProps {
  children: ReactNode;
  /** Target width — defaults to 402 px per UX_CONTRACT §7. */
  width?: number | string;
  /** Full-page mode: stretches frame to full viewport height. */
  fullHeight?: boolean;
  /** Apply role="main" to inner content area. */
  asMain?: boolean;
  className?: string;
  style?: CSSProperties;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const OUTER_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "center",
  alignItems: "flex-start",
  minHeight: "100vh",
  backgroundColor: "var(--color-bg)",
  padding: "2rem 1rem",
};

const INNER_BASE: CSSProperties = {
  backgroundColor: "var(--color-paper)",
  width: "100%",
  maxWidth: "402px",
  borderLeft: "var(--hairline)",
  borderRight: "var(--hairline)",
  borderTop: "var(--hairline)",
  borderBottom: "var(--hairline)",
  borderRadius: 0, /* Hard rule */
  padding: "2rem",
  minHeight: "480px",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Mobile shell: crude-bg outer + paper inner, 402 px max-width, square corners.
 *
 * @param props - {@link MobileFrameProps}
 * @returns The mobile frame element.
 */
export default function MobileFrame({
  children,
  width,
  fullHeight = false,
  asMain = false,
  className,
  style,
}: MobileFrameProps): ReactNode {
  /* BEFORE render log */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("MobileFrame.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      fullHeight,
    });
  }

  const innerStyle: CSSProperties = {
    ...INNER_BASE,
    maxWidth: width ?? "402px",
    minHeight: fullHeight ? "100vh" : INNER_BASE.minHeight,
    ...style,
  };

  const Tag = asMain ? "main" : "div";

  return (
    <div style={OUTER_STYLE}>
      <Tag className={className} style={innerStyle}>
        {children}
      </Tag>
    </div>
  );
}
