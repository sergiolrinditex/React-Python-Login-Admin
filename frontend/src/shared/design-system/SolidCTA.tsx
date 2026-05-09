/**
 * SolidCTA — Solid black call-to-action button.
 *
 * What: Primary CTA button following the Hilo editorial identity — solid black
 * background (`--color-ink`), white text (`--color-paper`), uppercase with
 * high tracking, zero rounded corners. The only CTA variant used for primary
 * actions (submit, continue, confirm).
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: instrucciones.md §7 ("CTA sólidos negros"), TECHNICAL_GUIDE §7,
 *         UX_CONTRACT §6 (WCAG AA contrast, visible focus)
 *
 * Logging:
 *   This component forwards onClick to the parent consumer. The parent feature
 *   use-case is responsible for BEFORE/AFTER logging of the triggered action.
 *   No logging at the primitive component level.
 *
 * Accessibility:
 *   - `type="button"` by default to prevent accidental form submission.
 *   - :focus-visible ring is applied globally via reset.css.
 *   - Disabled state uses reduced opacity (never conveys info by colour alone).
 *   - aria-busy when `loading` is true.
 */

import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from 'react';

interface SolidCTAProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className'> {
  /** Button label text or child content. */
  children: ReactNode;
  /** Shows a loading indicator and disables interaction. */
  loading?: boolean;
  /** Additional class for layout overrides. */
  className?: string;
  /** Size variant. Default: 'md'. */
  size?: 'sm' | 'md' | 'lg';
}

const sizeStyles: Record<NonNullable<SolidCTAProps['size']>, CSSProperties> = {
  sm: { padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--text-xs)' },
  md: { padding: 'var(--space-3) var(--space-8)', fontSize: 'var(--text-sm)' },
  lg: { padding: 'var(--space-4) var(--space-10)', fontSize: 'var(--text-base)' },
};

/**
 * Solid black CTA button with uppercase tracked label.
 *
 * @param children - Button content.
 * @param loading - Shows busy indicator; disables interaction.
 * @param className - Layout class.
 * @param size - Size variant. Default: 'md'.
 * @param rest - Passed to native <button>.
 */
export function SolidCTA({ children, loading = false, className, size = 'md', ...rest }: SolidCTAProps) {
  const baseStyle: CSSProperties = {
    display:       'inline-flex',
    alignItems:    'center',
    justifyContent: 'center',
    gap:           'var(--space-2)',
    fontFamily:    'var(--font-sans)',
    fontWeight:    'var(--weight-semibold)' as string,
    letterSpacing: 'var(--tracking-label)',
    textTransform: 'uppercase',
    color:         'var(--color-paper)',           /* white text */
    backgroundColor: 'var(--color-ink)',           /* solid black — no hex literal */
    border:        'none',
    borderRadius:  'var(--radius)',                /* = 0 */
    cursor:        loading || rest.disabled ? 'not-allowed' : 'pointer',
    opacity:       loading || rest.disabled ? 0.38 : 1,
    transition:    `opacity var(--duration-fast) var(--ease-standard)`,
    whiteSpace:    'nowrap',
    ...sizeStyles[size],
  };

  return (
    <button
      type="button"
      className={className}
      style={baseStyle}
      aria-busy={loading}
      aria-disabled={loading || rest.disabled}
      {...rest}
      disabled={loading || rest.disabled}
    >
      {children}
    </button>
  );
}
