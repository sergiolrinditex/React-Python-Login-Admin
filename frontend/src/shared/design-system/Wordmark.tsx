/**
 * Hilo People — Wordmark component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: renders the "Hilo" brand wordmark in display serif font.
 *   Used on: SignInPage (MobileFrame header), ChatHomePage (top nav),
 *   AdminShell (left-nav top). Journey refs: J100 (login), J101 (chat), J103 (admin).
 *
 * Token usage: --font-display, --color-ink.
 * Prohibitions: NO border-radius, NO box-shadow, NO hardcoded colors.
 *
 * Accessibility: renders as a semantic heading or presentational <span>
 *   depending on `as` prop. When used as site identity, wrap in <h1> at page level.
 *
 * Key deps: React 19, CSS custom properties from tokens.css.
 */

import type { CSSProperties, ElementType, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WordmarkProps {
  /** Additional CSS class. */
  className?: string;
  /** Inline style overrides (tokens only; no raw literals). */
  style?: CSSProperties;
  /** Render tag — defaults to "span" (page-level h1/h2 wraps from outside). */
  as?: ElementType;
  /** Font size override — defaults to 1.75rem. */
  size?: string;
  /** aria-label for screen readers when used standalone. */
  "aria-label"?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const STYLES: CSSProperties = {
  fontFamily: "var(--font-display)",
  color: "var(--color-ink)",
  letterSpacing: "-0.02em",
  lineHeight: 1,
  display: "inline-block",
};

/**
 * Hilo brand wordmark in display serif.
 *
 * @param props - {@link WordmarkProps}
 * @returns The wordmark element.
 */
export default function Wordmark({
  className,
  style,
  as: Tag = "span",
  size = "1.75rem",
  "aria-label": ariaLabel = "Hilo",
}: WordmarkProps): ReactNode {
  return (
    <Tag
      className={className}
      style={{ ...STYLES, fontSize: size, ...style }}
      aria-label={ariaLabel}
    >
      Hilo
    </Tag>
  );
}
