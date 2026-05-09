/**
 * MobileFrame — Mobile-width layout shell (375 px).
 *
 * What: Constrains content to a mobile-width column (max 402 px per
 * UX_CONTRACT §6), centred on the background colour. Used as the outer shell
 * for mobile-first screens (login, chat, onboarding).
 *
 * Naming note: instrucciones.md §7 calls this "MobileShell"; TECHNICAL_GUIDE §7
 * names it "MobileFrame". We follow the TECHNICAL_GUIDE — it is the architectural
 * source. Downstream consumers that import MobileShell will need to be updated;
 * a comment in the component body records this decision for audit trail.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: TECHNICAL_GUIDE §7 (MobileFrame), instrucciones.md §7 (MobileShell),
 *         UX_CONTRACT §6 (mobile target 402 px)
 *
 * Logging:
 *   No runtime actions. BEFORE/AFTER logging applies if MobileFrame gains
 *   scroll-position tracking or orientation listeners.
 *
 * Accessibility:
 *   - Main content area is a <main> element for landmark navigation.
 */

import type { CSSProperties, ReactNode } from 'react';

interface MobileFrameProps {
  /** The page content rendered inside the shell. */
  children: ReactNode;
  /** Additional class for the outer full-bleed wrapper. */
  className?: string;
}

const outerStyle: CSSProperties = {
  // Full-bleed background in crudo linen — matches body background from reset.css.
  minHeight:        '100dvh',
  backgroundColor:  'var(--color-bg)',
  display:          'flex',
  flexDirection:    'column',
  alignItems:       'center',
};

const innerStyle: CSSProperties = {
  // Mobile column: UX_CONTRACT §6 sets mobile target at 402 px.
  width:         '100%',
  maxWidth:      '402px',
  minHeight:     '100dvh',
  display:       'flex',
  flexDirection: 'column',
  backgroundColor: 'var(--color-bg)',
  // Editorial: zero rounded corners (global reset.css handles * selector,
  // but explicit here for documentation).
  borderRadius:  'var(--radius)',  /* = 0 */
};

/**
 * Mobile-first layout shell constraining content to 402 px max-width.
 *
 * @param children - Screen content.
 * @param className - Class for outer full-bleed wrapper.
 */
export function MobileFrame({ children, className }: MobileFrameProps) {
  // instrucciones.md §7 names this component "MobileShell" but TECHNICAL_GUIDE §7
  // (architectural source) names it "MobileFrame". Using MobileFrame. See handoff.

  return (
    <div className={className} style={outerStyle}>
      <main style={innerStyle}>
        {children}
      </main>
    </div>
  );
}
