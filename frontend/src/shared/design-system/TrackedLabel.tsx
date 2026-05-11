/**
 * Hilo People — TrackedLabel component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: uppercase tracked label for form labels, section headers,
 *   and status text across journey screens. Always rendered in small caps with
 *   letter-spacing = --tracking-label (.18em). Does NOT convey information
 *   through color alone (WCAG 1.4.1).
 *
 * Screens: EditorialInput label, HairlineTable column headers, StatusDot companion.
 * Journey refs: all journeys (ubiquitous UI primitive).
 *
 * Token usage: --font-sans, --tracking-label, --color-ink.
 * Prohibitions: NO border-radius, NO box-shadow, NO colored variants.
 *
 * Key deps: React 19, CSS custom properties from tokens.css.
 */

import type { CSSProperties, ElementType, HTMLAttributes, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Visual state for the label. */
export type TrackedLabelVariant = "default" | "active" | "muted";

export interface TrackedLabelProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  /** Visual variant — changes opacity, NOT color. Never color-only. */
  variant?: TrackedLabelVariant;
  /** Render tag — defaults to "span". */
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
  /** HTML id — for associating with inputs via htmlFor. */
  id?: string;
  /** Accessible title when label text alone is insufficient. */
  title?: string;
  /** htmlFor — used when rendering as <label> element. */
  htmlFor?: string;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const OPACITY_BY_VARIANT: Record<TrackedLabelVariant, number> = {
  default: 0.7,
  active: 1,
  muted: 0.4,
};

const BASE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem", /* 11px at 16px base */
  fontWeight: 500,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  display: "inline-block",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Uppercase tracked label for form fields, section headers, and status text.
 *
 * @param props - {@link TrackedLabelProps}
 * @returns The label element.
 */
export default function TrackedLabel({
  children,
  variant = "default",
  as: Tag = "span",
  className,
  style,
  id,
  title,
  htmlFor,
  ...rest
}: TrackedLabelProps): ReactNode {
  const opacity = OPACITY_BY_VARIANT[variant];

  return (
    <Tag
      id={id}
      className={className}
      title={title}
      htmlFor={htmlFor}
      style={{ ...BASE_STYLE, opacity, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
