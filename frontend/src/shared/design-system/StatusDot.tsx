/**
 * StatusDot — Monochrome inline status indicator.
 *
 * What: Renders a small filled circle to indicate active/inactive/pending
 * status. Follows the Hilo editorial rule: "never convey information by colour
 * alone" (UX_CONTRACT §6, instrucciones §7 zero decorative shadows).
 * The dot MUST always be accompanied by accessible text (either via label prop
 * or adjacent visible text); it is never the sole status signal.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: TECHNICAL_GUIDE §7 (StatusDot component), instrucciones.md §7
 *
 * Logging:
 *   No runtime actions. BEFORE/AFTER logging applies when StatusDot is used
 *   inside an action-bearing container.
 *
 * Accessibility:
 *   - The outer element has aria-label derived from the `status` prop.
 *   - `aria-hidden="true"` on the inner circle (decorative shape).
 *   - Optional `label` prop renders visible text beside the dot.
 */

import type { CSSProperties } from 'react';

type StatusVariant = 'active' | 'inactive' | 'pending';

interface StatusDotProps {
  /** The status variant. Determines fill and accessible name. */
  status: StatusVariant;
  /** Optional visible label rendered beside the dot. Encouraged for a11y. */
  label?: string;
  /** Extra class for layout. */
  className?: string;
}

/** Maps status variant to opacity of the ink fill — monochrome only. */
const opacityMap: Record<StatusVariant, number> = {
  active:   1,
  inactive: 0.28,
  pending:  0.56,
};

const statusLabels: Record<StatusVariant, string> = {
  active:   'active',
  inactive: 'inactive',
  pending:  'pending',
};

/**
 * Monochrome status dot — active / inactive / pending.
 *
 * @param status - Status variant.
 * @param label - Optional visible text beside the dot.
 * @param className - Layout overrides.
 */
export function StatusDot({ status, label, className }: StatusDotProps) {
  const dotStyle: CSSProperties = {
    display:      'inline-block',
    width:        8,
    height:       8,
    borderRadius: 'var(--radius)',       /* = 0 — editorial: square dot, not circle */
    backgroundColor: `var(--color-ink)`,
    opacity:      opacityMap[status],
    flexShrink:   0,
  };

  const containerStyle: CSSProperties = {
    display:    'inline-flex',
    alignItems: 'center',
    gap:        'var(--space-2)',
  };

  return (
    <span
      className={className}
      style={containerStyle}
      role="status"
      aria-label={label ?? statusLabels[status]}
    >
      <span style={dotStyle} aria-hidden="true" />
      {label !== undefined && (
        <span
          style={{
            fontFamily:    'var(--font-sans)',
            fontSize:      'var(--text-xs)',
            letterSpacing: 'var(--tracking-label)',
            textTransform: 'uppercase',
            color:         'var(--color-text-secondary)',
          }}
        >
          {label}
        </span>
      )}
    </span>
  );
}
