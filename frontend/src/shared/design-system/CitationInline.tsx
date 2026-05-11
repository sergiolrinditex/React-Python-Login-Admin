/**
 * Hilo People — CitationInline component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: inline citation link in "[Fuente N]" style for chat messages.
 *   Rendered inline within chat text alongside assistant serif copy. Used on:
 *   ChatHomePage (message citations, RAG source attribution).
 *   Journey refs: J101 (AI chat — RAG citations).
 *
 * Token usage: --font-sans, --color-ink (underlined).
 * Prohibitions: NO border-radius, NO box-shadow, NO colored backgrounds on hover.
 *
 * Accessibility:
 *   - Renders as <a> with href or <button> if onClick only.
 *   - Descriptive aria-label including source name.
 *   - Keyboard activation via native element.
 *
 * Key deps: React 19, CSS custom properties from tokens.css.
 */

import type { CSSProperties, MouseEventHandler, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CitationInlineProps {
  /** Citation label — e.g. "Fuente 1" or "Source 1". */
  label: string;
  /** URL for the source (renders as anchor). If absent, renders as button. */
  href?: string;
  /** Click handler (complements href). */
  onClick?: MouseEventHandler<HTMLAnchorElement | HTMLButtonElement>;
  /** Opens link in new tab when true (adds rel="noopener noreferrer"). */
  external?: boolean;
  className?: string;
  style?: CSSProperties;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const BASE_STYLE: CSSProperties = {
  display: "inline",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  textDecoration: "underline",
  letterSpacing: "0.02em",
  cursor: "pointer",
  background: "transparent",
  border: "none",
  borderRadius: 0,
  padding: "0 0.15em",
  lineHeight: "inherit",
  verticalAlign: "super",
  fontWeight: 500,
  opacity: 0.75,
};

const HOVER_STYLE: CSSProperties = {
  opacity: 1,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Inline citation link for chat message attribution.
 *
 * @param props - {@link CitationInlineProps}
 * @returns The citation element (anchor or button).
 */
export default function CitationInline({
  label,
  href,
  onClick,
  external = false,
  className,
  style,
}: CitationInlineProps): ReactNode {
  /* BEFORE render log */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("CitationInline.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      label,
      hasHref: Boolean(href),
    });
  }

  const ariaLabel = `Citation: ${label}`;
  const displayText = `[${label}]`;

  /* Hover opacity managed via CSS onMouseEnter/Leave — no JS state */
  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    (e.currentTarget as HTMLElement).style.opacity = String(HOVER_STYLE.opacity);
  };
  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>) => {
    (e.currentTarget as HTMLElement).style.opacity = String(BASE_STYLE.opacity);
  };

  const commonProps = {
    className,
    style: { ...BASE_STYLE, ...style },
    "aria-label": ariaLabel,
    onMouseEnter: handleMouseEnter,
    onMouseLeave: handleMouseLeave,
  };

  if (href) {
    return (
      <a
        href={href}
        target={external ? "_blank" : undefined}
        rel={external ? "noopener noreferrer" : undefined}
        onClick={onClick as MouseEventHandler<HTMLAnchorElement>}
        {...commonProps}
      >
        {displayText}
      </a>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick as MouseEventHandler<HTMLButtonElement>}
      {...commonProps}
    >
      {displayText}
    </button>
  );
}
