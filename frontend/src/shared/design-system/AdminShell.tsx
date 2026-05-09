/**
 * AdminShell — Admin panel layout shell (1440 px).
 *
 * What: Two-column editorial shell for the admin panel. Left column: 240 px
 * navigation sidebar with hairline right border. Right column: main content
 * area. Background: `--color-bg` (linen). Admin target width: 1440 px
 * per UX_CONTRACT §6.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: TECHNICAL_GUIDE §7 (AdminShell), instrucciones.md §7, UX_CONTRACT §6
 *
 * Logging:
 *   No runtime actions. BEFORE/AFTER logging applies when AdminShell gains
 *   sidebar-collapse or permission-gated rendering in a downstream slice.
 *
 * Accessibility:
 *   - Sidebar rendered as <nav> with aria-label.
 *   - Main content area as <main>.
 */

import type { CSSProperties, ReactNode } from 'react';

interface AdminShellProps {
  /** Navigation content rendered in the sidebar. */
  sidebar: ReactNode;
  /** Page content rendered in the main area. */
  children: ReactNode;
  /** Additional class on the outer wrapper. */
  className?: string;
}

const shellStyle: CSSProperties = {
  display:         'flex',
  minHeight:       '100dvh',
  backgroundColor: 'var(--color-bg)',
  borderRadius:    'var(--radius)',  /* = 0 */
};

const sidebarStyle: CSSProperties = {
  width:           '240px',
  flexShrink:      0,
  borderRight:     'var(--hairline)',
  backgroundColor: 'var(--color-bg)',
  padding:         'var(--space-8) var(--space-6)',
  display:         'flex',
  flexDirection:   'column',
  gap:             'var(--space-4)',
  borderRadius:    'var(--radius)',
};

const mainStyle: CSSProperties = {
  flex:            1,
  padding:         'var(--space-8)',
  overflow:        'auto',
  maxWidth:        '1200px',
  borderRadius:    'var(--radius)',
};

/**
 * Two-column admin shell: 240 px sidebar + flexible main content area.
 *
 * @param sidebar - Navigation content.
 * @param children - Main page content.
 * @param className - Outer wrapper class.
 */
export function AdminShell({ sidebar, children, className }: AdminShellProps) {
  return (
    <div className={className} style={shellStyle}>
      <nav aria-label="Admin navigation" style={sidebarStyle}>
        {sidebar}
      </nav>
      <main style={mainStyle}>
        {children}
      </main>
    </div>
  );
}
