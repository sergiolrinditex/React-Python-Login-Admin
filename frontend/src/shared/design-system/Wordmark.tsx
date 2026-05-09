/**
 * Wordmark — Hilo People brand logotype.
 *
 * What: Renders the "HILO" wordmark in display (serif) type. The wordmark is
 * the editorial identity anchor of the application — it appears in the empty
 * state of the chat, the login screen header, and admin shell header.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: TECHNICAL_GUIDE §7 (component list), instrucciones.md §7 (editorial identity)
 *
 * Naming note: instrucciones §7 says `MobileShell` as a descriptive component.
 * TECHNICAL_GUIDE §7 explicitly names `Wordmark`. We follow the TECHNICAL_GUIDE.
 *
 * Logging:
 *   No runtime actions. BEFORE/AFTER logging applies once the Wordmark gains
 *   a click handler (e.g. navigate-to-home) in a downstream slice.
 *
 * Accessibility:
 *   - The outer element has role="img" and aria-label with the brand name.
 *   - No alt-text needed on the span (decorative typography, not an img).
 */

import type { CSSProperties } from 'react';

interface WordmarkProps {
  /** Size variant. Controls font-size via token scale. Default: '2xl'. */
  size?: 'lg' | '2xl' | '3xl' | '4xl';
  /** Additional className for layout overrides. Do NOT pass colour/font tokens here. */
  className?: string;
  /** Accessible label. Defaults to 'Hilo People'. */
  label?: string;
}

const sizeMap: Record<NonNullable<WordmarkProps['size']>, string> = {
  lg:  'var(--text-lg)',
  '2xl': 'var(--text-2xl)',
  '3xl': 'var(--text-3xl)',
  '4xl': 'var(--text-4xl)',
};

/**
 * Renders the "HILO" wordmark using the display (serif) type stack.
 *
 * @param size - Font size variant. Default: '2xl'.
 * @param className - Additional layout class.
 * @param label - Accessible name. Default: 'Hilo People'.
 */
export function Wordmark({ size = '2xl', className, label = 'Hilo People' }: WordmarkProps) {
  const style: CSSProperties = {
    fontFamily:    'var(--font-display)',
    fontSize:      sizeMap[size],
    fontWeight:    'var(--weight-bold)' as string,
    letterSpacing: 'var(--tracking-tight)',
    lineHeight:    'var(--leading-tight)',
    color:         'var(--color-ink)',
    // Editorial identity: zero rounded corners enforced globally via reset.css
    borderRadius:  'var(--radius)',  /* = 0 */
    userSelect:    'none',
  };

  return (
    <span
      role="img"
      aria-label={label}
      className={className}
      style={style}
    >
      HILO
    </span>
  );
}
