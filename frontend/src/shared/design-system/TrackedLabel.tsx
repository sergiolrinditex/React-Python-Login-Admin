/**
 * TrackedLabel — Uppercase label with high tracking.
 *
 * What: Renders a small uppercase label using the `--tracking-label` (.18em)
 * and `--font-sans` tokens. Used for field labels, section dividers, status
 * indicators, and metadata tags throughout the editorial UI.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: instrucciones.md §7, TECHNICAL_GUIDE §7, UX_CONTRACT §1
 * ("uppercase labels with high tracking")
 *
 * Logging:
 *   No runtime actions. BEFORE/AFTER logging applies when the label gains
 *   interactive behaviour (click, sort toggle, filter) in a downstream slice.
 *
 * Accessibility:
 *   - Does not convey information by colour alone (UX_CONTRACT §6).
 *   - If used as a form field label, pass `htmlFor` to associate with the input.
 */

import type { CSSProperties, ReactNode } from 'react';

interface TrackedLabelProps {
  /** The label text (will be uppercased via CSS). */
  children: ReactNode;
  /** Associates label with an input by ID (renders as <label>). */
  htmlFor?: string;
  /** Extra class for layout. Do NOT override colour/font tokens here. */
  className?: string;
  /** Controls text size. Default: 'xs'. */
  size?: 'xs' | 'sm';
  /** Optional inline style overrides (use sparingly — prefer className for layout). */
  style?: CSSProperties;
}

const sizeMap: Record<NonNullable<TrackedLabelProps['size']>, string> = {
  xs: 'var(--text-xs)',
  sm: 'var(--text-sm)',
};

/**
 * Uppercase tracked label using the Hilo editorial identity.
 *
 * @param children - Label text.
 * @param htmlFor - If provided, renders as `<label>` for accessibility.
 * @param className - Layout overrides.
 * @param size - Text size token. Default 'xs'.
 */
export function TrackedLabel({ children, htmlFor, className, size = 'xs', style: extraStyle }: TrackedLabelProps) {
  const baseStyle: CSSProperties = {
    fontFamily:    'var(--font-sans)',
    fontSize:      sizeMap[size],
    fontWeight:    'var(--weight-semibold)' as string,
    letterSpacing: 'var(--tracking-label)',  /* 0.18em — canonical Hilo identity */
    lineHeight:    'var(--leading-normal)',
    color:         'var(--color-text-secondary)',
    textTransform: 'uppercase',
    display:       'block',
    borderRadius:  'var(--radius)',          /* = 0 */
    ...extraStyle,
  };

  if (htmlFor !== undefined) {
    return (
      <label htmlFor={htmlFor} className={className} style={baseStyle}>
        {children}
      </label>
    );
  }

  return (
    <span className={className} style={baseStyle}>
      {children}
    </span>
  );
}
